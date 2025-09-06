from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import call

import ntplib
import pytest
import requests

from lib import utils
from lib.utils import AirportCheckInError, RequestError

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from requests_mock.mocker import Mocker as RequestMocker


def test_random_sleep_duration_respects_min_and_max_durations(mocker: MockerFixture) -> None:
    mock_uniform = mocker.patch("random.uniform", return_value=12)
    sleep_time = utils.random_sleep_duration(10, 100)

    assert sleep_time == 12
    mock_uniform.assert_called_once_with(10, 100)


def test_make_request_raises_exception_on_failure(
    requests_mock: RequestMocker, mocker: MockerFixture
) -> None:
    mock_sleep = mocker.patch("time.sleep")
    mocker.patch("lib.utils.random_sleep_duration", side_effect=[1.5, 1, 2.2, 3, 2])
    requests_mock.post(utils.BASE_URL + "test", status_code=400, reason="error")

    with pytest.raises(RequestError):
        utils.make_request("POST", "test", {}, {}, max_attempts=5)

    assert mock_sleep.call_count == 5

    expected_calls = [call(1.5), call(1), call(2.2), call(3), call(2)]
    mock_sleep.assert_has_calls(expected_calls)


# Test if make_request is resistant to general Python requests exceptions like SSLError
def test_make_request_handles_request_errors(mocker: MockerFixture) -> None:
    mock_sleep = mocker.patch("time.sleep")
    mocker.patch("lib.utils.random_sleep_duration", side_effect=[1.5, 1, 2.2, 3, 2])
    mocker.patch("requests.post", side_effect=requests.exceptions.SSLError)

    with pytest.raises(RequestError):
        utils.make_request("POST", "test", {}, {}, max_attempts=5)

    assert mock_sleep.call_count == 5

    expected_calls = [call(1.5), call(1), call(2.2), call(3), call(2)]
    mock_sleep.assert_has_calls(expected_calls)


@pytest.mark.parametrize("error", [AirportCheckInError, RequestError])
def test_make_request_stops_early_for_special_southwest_code(
    mocker: MockerFixture,
    requests_mock: RequestMocker,
    error: AirportCheckInError | RequestError,
) -> None:
    requests_mock.get(utils.BASE_URL + "test", status_code=400, reason="Bad Request")
    mock_sleep = mocker.patch("time.sleep")

    # Initialize error with ("") because RequestError has one required parameter. Doesn't
    # affect AirportCheckInError
    mocker.patch("lib.utils._handle_southwest_error_code", side_effect=error(""))

    with pytest.raises(error):
        utils.make_request("GET", "test", {}, {})

    assert mock_sleep.call_count == 0


def test_make_request_does_not_sleep_randomly_on_failures_when_random_sleep_is_false(
    requests_mock: RequestMocker, mocker: MockerFixture
) -> None:
    mock_sleep = mocker.patch("time.sleep")
    mock_rand_sleep_duration = mocker.patch("lib.utils.random_sleep_duration")
    requests_mock.post(utils.BASE_URL + "test", status_code=400, reason="error")

    with pytest.raises(RequestError):
        utils.make_request("POST", "test", {}, {}, max_attempts=2, random_sleep=False)

    assert mock_sleep.call_count == 2
    mock_rand_sleep_duration.assert_not_called()

    expected_calls = [call(0.5), call(0.5)]
    mock_sleep.assert_has_calls(expected_calls)


def test_make_request_handles_malformed_urls(requests_mock: RequestMocker) -> None:
    mock_post = requests_mock.get(utils.BASE_URL + "test/test2", status_code=200, text="{}")
    utils.make_request("GET", "/test//test2", {}, {})
    assert mock_post.last_request.url == utils.BASE_URL + "test/test2"


def test_do_request_correctly_posts_data(requests_mock: RequestMocker) -> None:
    url = utils.BASE_URL + "test"
    mock_post = requests_mock.post(url, status_code=200, text='{"success": "post"}')

    response = utils._do_request("POST", url, {"header": "test"}, {"test": "json"})

    assert response.json() == {"success": "post"}

    last_request = mock_post.last_request
    assert last_request.method == "POST"
    assert last_request.url == url
    assert last_request.headers["header"] == "test"
    assert last_request.json() == {"test": "json"}


def test_do_request_correctly_gets_data(requests_mock: RequestMocker) -> None:
    url = utils.BASE_URL + "test"
    mock_post = requests_mock.get(url, status_code=200, text='{"success": "get"}')

    response = utils._do_request("GET", url, {"header": "test"}, {"test": "params"})

    assert response.json() == {"success": "get"}

    last_request = mock_post.last_request
    assert last_request.method == "GET"
    assert last_request.url == url + "?test=params"
    assert last_request.headers["header"] == "test"


@pytest.mark.parametrize(
    ("code", "error"),
    [
        (utils.AIRPORT_CHECKIN_REQUIRED_CODE, AirportCheckInError),
        (utils.INVALID_CONFIRMATION_NUMBER_LENGTH_CODE, RequestError),
        (utils.PASSENGER_NOT_FOUND_CODE, RequestError),
        (utils.RESERVATION_NOT_FOUND_CODE, RequestError),
        (utils.RESERVATION_CANCELLED_CODE, RequestError),
    ],
)
def test_handle_southwest_error_code_handles_all_special_codes(
    code: int, error: AirportCheckInError | RequestError
) -> None:
    response_body = json.dumps({"code": code})
    request_err = RequestError("", response_body)
    with pytest.raises(error):
        utils._handle_southwest_error_code(request_err)


def test_get_current_time_returns_a_datetime_from_ntp_server(mocker: MockerFixture) -> None:
    ntp_stats = ntplib.NTPStats()
    ntp_stats.tx_timestamp = 3155673599
    mocker.patch("ntplib.NTPClient.request", return_value=ntp_stats)

    assert utils.get_current_time() == datetime(1999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)


def test_get_current_time_returns_a_datetime_from_backup_ntp_server(mocker: MockerFixture) -> None:
    ntp_stats = ntplib.NTPStats()
    ntp_stats.tx_timestamp = 3155673599
    mocker.patch("ntplib.NTPClient.request", side_effect=[ntplib.NTPException, ntp_stats])

    assert utils.get_current_time() == datetime(1999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)


@pytest.mark.parametrize("exception", [socket.gaierror, ntplib.NTPException])
def test_get_current_time_returns_local_datetime_on_failed_requests(
    mocker: MockerFixture, exception: Exception
) -> None:
    expected_time = datetime(1999, 12, 31, 18, 59, 59, tzinfo=timezone.utc)

    mocker.patch("ntplib.NTPClient.request", side_effect=exception)
    mock_datetime = mocker.patch("lib.utils.datetime")
    mock_datetime.now.return_value = expected_time

    assert utils.get_current_time() == expected_time


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("false", False),
        ("True", True),
        ("False", False),
        ("TRUE", True),
        ("FALSE", False),
        ("t", True),
        ("f", False),
        ("T", True),
        ("F", False),
        ("yes", True),
        ("no", False),
        ("Yes", True),
        ("No", False),
        ("YES", True),
        ("NO", False),
        ("y", True),
        ("n", False),
        ("Y", True),
        ("N", False),
        ("1", True),
        ("0", False),
    ],
)
def test_is_truthy(value: Any, expected: bool) -> None:
    assert utils.is_truthy(value) == expected


def test_is_truthy_raises_exception_on_invalid_type() -> None:
    with pytest.raises(ValueError) as excinfo:
        utils.is_truthy("test")

    assert "Invalid truthy value" in str(excinfo.value)
