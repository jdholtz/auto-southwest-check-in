from typing import Any, Dict, List
from unittest import mock

import pytest
from pytest_mock import MockerFixture
from seleniumwire.request import Request, Response

from lib.checkin_scheduler import CheckInScheduler
from lib.utils import LoginError
from lib.webdriver import INVALID_CREDENTIALS_CODE, WebDriver

# This needs to be accessed to be tested
# pylint: disable=protected-access


@pytest.fixture(autouse=True)
def mock_driver(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch("lib.webdriver.Chrome")


@pytest.fixture()
def mock_flight_retriever(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch("lib.flight_retriever.AccountFlightRetriever")


@pytest.fixture()
def mock_get_options(mocker: MockerFixture):
    mocker.patch.object(WebDriver, "_get_options")


@pytest.mark.usefixtures("mock_get_options")
def test_set_headers_correctly_sets_needed_headers(mocker: MockerFixture) -> None:
    mocker.patch("lib.webdriver.WebDriverWait")
    mock_wait_for_response = mocker.patch.object(WebDriver, "_wait_for_response")
    mock_set_headers_from_request = mocker.patch.object(WebDriver, "_set_headers_from_request")

    mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
    WebDriver(mock_checkin_scheduler).set_headers()
    mock_wait_for_response.assert_called_once()
    mock_set_headers_from_request.assert_called_once()


@pytest.mark.usefixtures("mock_get_options")
def test_get_flights_raises_exception_on_failed_login(
    mocker: MockerFixture, mock_driver: mock.Mock, mock_flight_retriever: mock.Mock
) -> None:
    request_one = Request(method="GET", url="", headers={})
    request_one.response = Response(status_code=400, reason="", headers={})

    mocker.patch("lib.webdriver.WebDriverWait")
    mocker.patch.object(WebDriver, "_get_driver", return_value=mock_driver)
    mocker.patch.object(WebDriver, "_handle_login_error", return_value=LoginError())
    mock_wait_for_response = mocker.patch.object(
        WebDriver, "_wait_for_response", return_value=request_one.response
    )
    mock_set_headers_from_request = mocker.patch.object(WebDriver, "_set_headers_from_request")

    mock_driver.requests = [request_one]

    with pytest.raises(LoginError):
        WebDriver(None).get_flights(mock_flight_retriever)

    mock_wait_for_response.assert_called_once()
    mock_set_headers_from_request.assert_not_called()


@pytest.mark.usefixtures("mock_get_options")
def test_get_flights_sets_account_name_when_it_is_not_set(
    mocker: MockerFixture, mock_driver: mock.Mock, mock_flight_retriever: mock.Mock
) -> None:
    request_one = Request(method="GET", url="", headers={})
    request_one.response = Response(status_code=200, reason="", headers={})
    request_one.response.body = '{"name": "John Doe"}'

    request_two = Request(method="GET", url="", headers={})
    request_two.response = Response(status_code=200, reason="", headers={})
    request_two.response.body = '{"upcomingTripsPage": [{"tripType": "FLIGHT"}]}'

    mocker.patch("lib.webdriver.WebDriverWait")
    mocker.patch.object(WebDriver, "_get_driver", return_value=mock_driver)
    mock_set_headers_from_request = mocker.patch.object(WebDriver, "_set_headers_from_request")
    mock_set_account_name = mocker.patch.object(WebDriver, "_set_account_name")
    mocker.patch.object(
        WebDriver, "_wait_for_response", side_effect=[request_one.response, request_two.response]
    )

    mock_driver.requests = [request_one, request_two]

    mock_flight_retriever.first_name = None
    flights = WebDriver(None).get_flights(mock_flight_retriever)

    mock_set_headers_from_request.assert_called_once_with(mock_driver)
    mock_set_account_name.assert_called_once_with(mock_flight_retriever, {"name": "John Doe"})
    assert flights == [{"tripType": "FLIGHT"}]


@pytest.mark.usefixtures("mock_get_options")
def test_get_flights_does_not_set_account_name_when_it_is_already_set(
    mocker: MockerFixture, mock_driver: mock.Mock, mock_flight_retriever: mock.Mock
) -> None:
    request_one = Request(method="GET", url="", headers={})
    request_one.response = Response(status_code=200, reason="", headers={})

    request_two = Request(method="GET", url="", headers={})
    request_two.response = Response(status_code=200, reason="", headers={})
    request_two.response.body = '{"upcomingTripsPage": [{"tripType": "FLIGHT"}]}'

    mocker.patch("lib.webdriver.WebDriverWait")
    mocker.patch.object(WebDriver, "_get_driver", return_value=mock_driver)
    mock_set_headers_from_request = mocker.patch.object(WebDriver, "_set_headers_from_request")
    mock_set_account_name = mocker.patch.object(WebDriver, "_set_account_name")
    mocker.patch.object(
        WebDriver, "_wait_for_response", side_effect=[request_one.response, request_two.response]
    )

    mock_driver.requests = [request_one, request_two]

    mock_flight_retriever.first_name = "John"
    flights = WebDriver(None).get_flights(mock_flight_retriever)

    mock_set_headers_from_request.assert_called_once_with(mock_driver)
    mock_set_account_name.assert_not_called()
    assert flights == [{"tripType": "FLIGHT"}]


@pytest.mark.usefixtures("mock_get_options")
def test_get_flights_only_returns_flight_trip_type(
    mocker: MockerFixture, mock_driver: mock.Mock, mock_flight_retriever: mock.Mock
) -> None:
    request_one = Request(method="GET", url="", headers={})
    request_one.response = Response(status_code=200, reason="", headers={})

    request_two = Request(method="GET", url="", headers={})
    request_two.response = Response(status_code=200, reason="", headers={})
    request_two.response.body = (
        '{"upcomingTripsPage": [{"tripType": "FLIGHT"}, '
        '{"tripType": "FLIGHT"}, {"tripType": "CAR"}]}'
    )

    mocker.patch("lib.webdriver.WebDriverWait")
    mocker.patch.object(WebDriver, "_get_driver", return_value=mock_driver)
    mocker.patch.object(WebDriver, "_set_headers_from_request")
    mocker.patch.object(
        WebDriver, "_wait_for_response", side_effect=[request_one.response, request_two.response]
    )

    mock_driver.requests = [request_one, request_two]

    mock_flight_retriever.first_name = "John"
    flights = WebDriver(None).get_flights(mock_flight_retriever)
    assert len(flights) == 2


@pytest.mark.usefixtures("mock_get_options")
def test_get_driver_returns_a_webdriver_with_one_request(mocker: MockerFixture) -> None:
    mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
    driver = WebDriver(mock_checkin_scheduler)._get_driver()
    assert isinstance(driver, mock.Mock)
    assert driver.get.call_count == 1


@pytest.mark.usefixtures("mock_get_options")
@pytest.mark.parametrize(
    ["driver_requests", "request_num"],
    [
        (None, 0),
        ([Request(method="GET", url="", headers={})], 1),
        ([Request(method="GET", url="", headers={}), Request(method="GET", url="", headers={})], 1),
    ],
)
def test_wait_for_response_waits_continuously_for_response(
    mocker: MockerFixture, mock_driver: mock.Mock, driver_requests: List[Request], request_num: int
) -> None:
    # Since the wait_for_response function runs in an infinite loop, throw an Exception
    # when the sleep function is called a second time to break out of the loop.
    mocker.patch("time.sleep", side_effect=["", KeyboardInterrupt])
    mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")

    mock_driver.requests = driver_requests
    webdriver = WebDriver(mock_checkin_scheduler)

    # It should throw an exception if sleep is called multiple times
    with pytest.raises(KeyboardInterrupt):
        webdriver._wait_for_response(mock_driver, request_num)


@pytest.mark.usefixtures("mock_get_options")
def test_wait_for_response_waits_for_correct_response(
    mocker: MockerFixture, mock_driver: mock.Mock
) -> None:
    mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")

    request_one = Request(method="GET", url="", headers={})
    request_one.response = Response(status_code=200, reason="", headers={})
    request_two = Request(method="GET", url="", headers={})
    request_two.response = Response(status_code=200, reason="", headers={})
    mock_driver.requests = [request_one, request_two]

    webdriver = WebDriver(mock_checkin_scheduler)
    response = webdriver._wait_for_response(mock_driver, 1)
    assert response == request_two.response


@pytest.mark.usefixtures("mock_get_options")
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


@pytest.mark.parametrize(
    ["chrome_version", "option"],
    [
        (None, "new"),
        (109, "new"),
        (108, "chrome"),
    ],
)
def test_get_options_adds_the_correct_headless_option(
    mocker: MockerFixture, chrome_version: int, option: str
) -> None:
    mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
    mock_checkin_scheduler.flight_retriever.config.chrome_version = chrome_version

    webdriver = WebDriver(mock_checkin_scheduler)
    options = webdriver._get_options()

    assert "--disable-dev-shm-usage" in options.arguments
    assert f"--headless={option}" in options.arguments


def test_handle_login_error_handles_invalid_credentials() -> None:
    response = Response(
        status_code=400,
        reason="",
        headers={},
        body=f'{{"code": {INVALID_CREDENTIALS_CODE}}}',
    )

    error = WebDriver._handle_login_error(response)
    assert "Reason: Invalid credentials" in str(error)
    assert "Status code: 400" in str(error)


def test_handle_login_error_handles_unknown_errors() -> None:
    response = Response(
        status_code=429,
        reason="",
        headers={},
        body="{}",
    )

    error = WebDriver._handle_login_error(response)
    assert "Reason: Unknown" in str(error)
    assert "Status code: 429" in str(error)


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


@pytest.mark.usefixtures("mock_get_options")
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
