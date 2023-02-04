from typing import Any, Dict
from unittest import mock

import pytest
from pytest_mock import MockerFixture
from seleniumwire.request import Request, Response

from lib.checkin_scheduler import CheckInScheduler
from lib.general import LoginError
from lib.webdriver import USER_AGENT, WebDriver

# This needs to be accessed to be tested
# pylint: disable=protected-access


@pytest.fixture(autouse=True)
def mock_driver(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch("lib.webdriver.Chrome")


@pytest.fixture()
def mock_flight_retriever(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch("lib.flight_retriever.AccountFlightRetriever")


def test_set_headers_correctly_sets_needed_headers(mocker: MockerFixture) -> None:
    mocker.patch("lib.webdriver.WebDriverWait")
    mock_set_headers_from_request = mocker.patch.object(WebDriver, "_set_headers_from_request")

    WebDriver(None).set_headers()
    mock_set_headers_from_request.assert_called_once()


def test_get_flights_raises_exception_on_failed_login(
    mocker: MockerFixture, mock_driver: mock.Mock, mock_flight_retriever: mock.Mock
) -> None:
    mocker.patch("lib.webdriver.WebDriverWait")
    mocker.patch.object(WebDriver, "_get_driver", return_value=mock_driver)
    mock_set_headers_from_request = mocker.patch.object(WebDriver, "_set_headers_from_request")

    request_one = Request(method="GET", url="", headers={})
    request_one.response = Response(status_code=400, reason="", headers={})

    mock_driver.requests = [request_one]

    with pytest.raises(LoginError):
        WebDriver(None).get_flights(mock_flight_retriever)

    mock_set_headers_from_request.assert_called_once_with(mock_driver)


def test_get_flights_sets_account_name_when_it_is_not_set(
    mocker: MockerFixture, mock_driver: mock.Mock, mock_flight_retriever: mock.Mock
) -> None:
    mocker.patch("lib.webdriver.WebDriverWait")
    mocker.patch.object(WebDriver, "_get_driver", return_value=mock_driver)
    mock_set_headers_from_request = mocker.patch.object(WebDriver, "_set_headers_from_request")
    mock_set_account_name = mocker.patch.object(WebDriver, "_set_account_name")

    request_one = Request(method="GET", url="", headers={})
    request_one.response = Response(status_code=200, reason="", headers={})
    request_one.response.body = '{"name": "John Doe"}'

    request_two = Request(method="GET", url="", headers={})
    request_two.response = Response(status_code=200, reason="", headers={})
    request_two.response.body = '{"upcomingTripsPage": "new flights"}'

    mock_driver.requests = [request_one, request_two]

    mock_flight_retriever.first_name = None
    flights = WebDriver(None).get_flights(mock_flight_retriever)

    mock_set_headers_from_request.assert_called_once_with(mock_driver)
    mock_set_account_name.assert_called_once_with(mock_flight_retriever, {"name": "John Doe"})
    assert flights == "new flights"


def test_get_flights_does_not_set_account_name_when_it_is_already_set(
    mocker: MockerFixture, mock_driver: mock.Mock, mock_flight_retriever: mock.Mock
) -> None:
    mocker.patch("lib.webdriver.WebDriverWait")
    mocker.patch.object(WebDriver, "_get_driver", return_value=mock_driver)
    mock_set_headers_from_request = mocker.patch.object(WebDriver, "_set_headers_from_request")
    mock_set_account_name = mocker.patch.object(WebDriver, "_set_account_name")

    request_one = Request(method="GET", url="", headers={})
    request_one.response = Response(status_code=200, reason="", headers={})

    request_two = Request(method="GET", url="", headers={})
    request_two.response = Response(status_code=200, reason="", headers={})
    request_two.response.body = '{"upcomingTripsPage": "new flights"}'

    mock_driver.requests = [request_one, request_two]

    mock_flight_retriever.first_name = "John"
    flights = WebDriver(None).get_flights(mock_flight_retriever)

    mock_set_headers_from_request.assert_called_once_with(mock_driver)
    mock_set_account_name.assert_not_called()
    assert flights == "new flights"


def test_get_driver_returns_a_webdriver_with_one_request() -> None:
    driver = WebDriver(None)._get_driver()
    assert isinstance(driver, mock.Mock)
    assert driver.get.call_count == 1  # pylint: disable=no-member


def test_set_headers_from_request_sets_the_correct_headers(
    mocker: MockerFixture, mock_driver: mock.Mock
) -> None:
    mocker.patch("time.sleep")
    mocker.patch.object(WebDriver, "_get_needed_headers", return_value={"test": "headers"})
    mock_flight_retriever = mocker.patch("lib.flight_retriever.FlightRetriever")

    checkin_scheduler = CheckInScheduler(mock_flight_retriever)
    webdriver = WebDriver(checkin_scheduler)
    webdriver._set_headers_from_request(mock_driver)

    assert checkin_scheduler.headers == {"test": "headers"}


def test_get_options_adds_the_necessary_options() -> None:
    options = WebDriver._get_options()

    assert "--disable-dev-shm-usage" in options.arguments
    assert "--headless" in options.arguments
    assert "--user-agent=" + USER_AGENT in options.arguments


@pytest.mark.parametrize(
    ["original_headers", "expected_headers"],
    [
        ({"unneccesary": "header"}, {}),
        ({"X-API-Key": "API Key"}, {"X-API-Key": "API Key"}),
        ({"X-Channel-ID": "ID"}, {"X-Channel-ID": "ID"}),
        ({"User-Agent": "Chrome"}, {"User-Agent": "Chrome"}),
        ({"EE30zvQLWf-b": "secret"}, {"EE30zvQLWf-b": "secret"}),
    ],
)
def test_get_needed_headers_returns_matching_headers(
    original_headers: Dict[str, Any], expected_headers: Dict[str, Any]
) -> None:
    headers = WebDriver._get_needed_headers(original_headers)
    assert headers == expected_headers


def test_set_account_name_sets_the_correct_values_for_the_name(
    mock_flight_retriever: mock.Mock,
) -> None:
    WebDriver(None)._set_account_name(
        mock_flight_retriever,
        {
            "customers.userInformation.firstName": "John",
            "customers.userInformation.lastName": "Doe",
        },
    )

    assert mock_flight_retriever.first_name == "John"
    assert mock_flight_retriever.last_name == "Doe"
