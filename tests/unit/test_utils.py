import json
import socket
from datetime import datetime
from typing import Any

import ntplib
import pytest
from pytest_mock import MockerFixture
from requests_mock.mocker import Mocker as RequestMocker

from lib import utils


def test_make_request_raises_exception_on_failure(
    requests_mock: RequestMocker, mocker: MockerFixture
) -> None:
    mock_sleep = mocker.patch("time.sleep")
    requests_mock.post(utils.BASE_URL + "test", status_code=400, reason="error")

    with pytest.raises(utils.RequestError):
        utils.make_request("POST", "test", {}, {}, max_attempts=5)

    assert mock_sleep.call_count == 5


def test_make_request_stops_early_when_reservation_not_found(
    mocker: MockerFixture, requests_mock: RequestMocker
) -> None:
    response_body = {"code": utils.RESERVATION_NOT_FOUND_CODE}
    requests_mock.get(
        utils.BASE_URL + "test",
        status_code=400,
        text=json.dumps(response_body),
        reason="Bad Request",
    )
    mock_sleep = mocker.patch("time.sleep")

    with pytest.raises(utils.RequestError):
        utils.make_request("GET", "test", {}, {})

    assert mock_sleep.call_count == 0


def test_make_request_correctly_posts_data(requests_mock: RequestMocker) -> None:
    mock_post = requests_mock.post(
        utils.BASE_URL + "test", status_code=200, text='{"success": "post"}'
    )

    response = utils.make_request("POST", "test", {"header": "test"}, {"test": "json"})

    assert response == {"success": "post"}

    last_request = mock_post.last_request
    assert last_request.method == "POST"
    assert last_request.url == utils.BASE_URL + "test"
    assert last_request.headers["header"] == "test"
    assert last_request.json() == {"test": "json"}


def test_make_request_correctly_gets_data(requests_mock: RequestMocker) -> None:
    mock_post = requests_mock.get(
        utils.BASE_URL + "test", status_code=200, text='{"success": "get"}'
    )

    response = utils.make_request("GET", "test", {"header": "test"}, {"test": "params"})

    assert response == {"success": "get"}

    last_request = mock_post.last_request
    assert last_request.method == "GET"
    assert last_request.url == utils.BASE_URL + "test?test=params"
    assert last_request.headers["header"] == "test"


def test_make_request_handles_malformed_URLs(requests_mock: RequestMocker) -> None:
    mock_post = requests_mock.get(utils.BASE_URL + "test/test2", status_code=200, text="{}")
    utils.make_request("GET", "/test//test2", {}, {})
    assert mock_post.last_request.url == utils.BASE_URL + "test/test2"


def test_get_current_time_returns_a_datetime_from_ntp_server(mocker: MockerFixture) -> None:
    ntp_stats = ntplib.NTPStats()
    ntp_stats.tx_timestamp = 3155673599
    mocker.patch("ntplib.NTPClient.request", return_value=ntp_stats)

    assert utils.get_current_time() == datetime(1999, 12, 31, 23, 59, 59)


@pytest.mark.parametrize("exception", [socket.gaierror, ntplib.NTPException])
def test_get_current_time_returns_local_datetime_on_failed_request(
    mocker: MockerFixture, exception: Exception
) -> None:
    mocker.patch("ntplib.NTPClient.request", side_effect=exception)
    mock_datetime = mocker.patch("lib.utils.datetime")
    mock_datetime.now.return_value = datetime(1999, 12, 31, 18, 59, 59)

    assert utils.get_current_time() == datetime(1999, 12, 31, 18, 59, 59)


@pytest.mark.parametrize(
    "value, expected",
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
