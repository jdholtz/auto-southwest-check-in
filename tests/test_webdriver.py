from typing import Any, Dict, List
from unittest import mock

import pytest
from pytest_mock import MockerFixture
from selenium.common.exceptions import WebDriverException
from seleniumwire.request import Request, Response

from lib.checkin_scheduler import CheckInScheduler
from lib.utils import LoginError
from lib.webdriver import INVALID_CREDENTIALS_CODE, WebDriver

# This needs to be accessed to be tested
# pylint: disable=protected-access


@pytest.fixture(autouse=True)
def mock_driver(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch("lib.webdriver.Chrome")


@pytest.fixture
def mock_reservation_monitor(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch("lib.reservation_monitor.AccountMonitor")


@pytest.fixture
def mock_get_options(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch.object(WebDriver, "_get_options")


@pytest.mark.usefixtures("mock_get_options")
def test_set_headers_correctly_sets_needed_headers(mocker: MockerFixture) -> None:
    mocker.patch("lib.webdriver.WebDriverWait")
    mock_wait_for_response = mocker.patch.object(WebDriver, "_wait_for_response")
    mock_set_headers_from_request = mocker.patch.object(WebDriver, "_set_headers_from_request")
    mock_quit_browser = mocker.patch.object(WebDriver, "_quit_browser")

    mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
    WebDriver(mock_checkin_scheduler).set_headers()

    mock_wait_for_response.assert_called_once()
    mock_set_headers_from_request.assert_called_once()
    mock_quit_browser.assert_called_once()


def test_get_reservations_raises_exception_on_failed_login(
    mocker: MockerFixture, mock_driver: mock.Mock, mock_reservation_monitor: mock.Mock
) -> None:
    request_one = Request(method="GET", url="", headers={})
    request_one.response = Response(status_code=400, reason="", headers={})

    mocker.patch("lib.webdriver.WebDriverWait")
    mocker.patch.object(WebDriver, "_get_driver", return_value=mock_driver)
    mocker.patch.object(WebDriver, "_handle_login_error", return_value=LoginError("", 400))
    mock_wait_for_response = mocker.patch.object(
        WebDriver, "_wait_for_response", return_value=request_one.response
    )
    mock_set_headers_from_request = mocker.patch.object(WebDriver, "_set_headers_from_request")
    mock_quit_browser = mocker.patch.object(WebDriver, "_quit_browser")

    mock_driver.requests = [request_one]

    with pytest.raises(LoginError):
        WebDriver(None).get_reservations(mock_reservation_monitor)

    mock_wait_for_response.assert_called_once()
    mock_set_headers_from_request.assert_not_called()
    mock_quit_browser.assert_called_once_with(mock_driver)


def test_get_reservations_sets_account_name_when_it_is_not_set(
    mocker: MockerFixture, mock_driver: mock.Mock, mock_reservation_monitor: mock.Mock
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
    mock_quit_browser = mocker.patch.object(WebDriver, "_quit_browser")

    mock_driver.requests = [request_one, request_two]

    mock_reservation_monitor.first_name = None
    flights = WebDriver(None).get_reservations(mock_reservation_monitor)

    mock_set_headers_from_request.assert_called_once_with(mock_driver)
    mock_set_account_name.assert_called_once_with(mock_reservation_monitor, {"name": "John Doe"})
    mock_quit_browser.assert_called_once_with(mock_driver)
    assert flights == [{"tripType": "FLIGHT"}]


def test_get_reservations_does_not_set_account_name_when_it_is_already_set(
    mocker: MockerFixture, mock_driver: mock.Mock, mock_reservation_monitor: mock.Mock
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
    mock_quit_browser = mocker.patch.object(WebDriver, "_quit_browser")

    mock_driver.requests = [request_one, request_two]

    mock_reservation_monitor.first_name = "John"
    flights = WebDriver(None).get_reservations(mock_reservation_monitor)

    mock_set_headers_from_request.assert_called_once_with(mock_driver)
    mock_set_account_name.assert_not_called()
    mock_quit_browser.assert_called_once_with(mock_driver)
    assert flights == [{"tripType": "FLIGHT"}]


def test_get_reservations_only_returns_flight_reservations(
    mocker: MockerFixture, mock_driver: mock.Mock, mock_reservation_monitor: mock.Mock
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
    mock_quit_browser = mocker.patch.object(WebDriver, "_quit_browser")

    mock_driver.requests = [request_one, request_two]

    mock_reservation_monitor.first_name = "John"
    flights = WebDriver(None).get_reservations(mock_reservation_monitor)
    assert len(flights) == 2
    mock_quit_browser.assert_called_once_with(mock_driver)


def test_get_driver_returns_a_webdriver_with_one_request(mocker: MockerFixture) -> None:
    mock_init_driver = mocker.patch.object(WebDriver, "_init_driver")
    mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
    driver = WebDriver(mock_checkin_scheduler)._get_driver()

    mock_init_driver.assert_called_once()
    assert driver.get.call_count == 1


@pytest.mark.usefixtures("mock_get_options")
def test_init_driver_initializes_the_webdriver_correctly(mocker: MockerFixture) -> None:
    mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
    driver = WebDriver(mock_checkin_scheduler)._init_driver()
    assert isinstance(driver, mock.Mock)


def test_init_driver_raises_error_when_webdriver_fails_to_initialize(
    mocker: MockerFixture, mock_get_options: mock.Mock
) -> None:
    mock_chrome = mocker.patch("lib.webdriver.Chrome", side_effect=WebDriverException)
    mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
    with pytest.raises(RuntimeError):
        WebDriver(mock_checkin_scheduler)._init_driver()

    assert mock_chrome.call_count == 3
    assert mock_get_options.call_count == 3


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


def test_set_headers_from_request_sets_the_correct_headers(
    mocker: MockerFixture, mock_driver: mock.Mock
) -> None:
    mocker.patch("time.sleep")
    mocker.patch.object(WebDriver, "_get_needed_headers", return_value={"test": "headers"})
    mock_reservation_monitor = mocker.patch("lib.reservation_monitor.ReservationMonitor")

    checkin_scheduler = CheckInScheduler(mock_reservation_monitor)
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
    mock_checkin_scheduler.reservation_monitor.config.chrome_version = chrome_version

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

    error = WebDriver(None)._handle_login_error(response)
    assert "Reason: Invalid credentials" in str(error)
    assert "Status code: 400" in str(error)


def test_handle_login_error_handles_unknown_errors() -> None:
    response = Response(
        status_code=429,
        reason="",
        headers={},
        body="{}",
    )

    error = WebDriver(None)._handle_login_error(response)
    assert "Reason: Unknown" in str(error)
    assert "Status code: 429" in str(error)


@pytest.mark.parametrize(
    ["original_headers", "expected_headers"],
    [
        ({"unnecessary": "header"}, {}),
        ({"X-API-Key": "API Key"}, {"X-API-Key": "API Key"}),
        ({"X-Channel-ID": "ID"}, {"X-Channel-ID": "ID"}),
        ({"User-Agent": "Chrome"}, {"User-Agent": "Chrome"}),
        ({"EE30zvQLWf-b": "secret"}, {"EE30zvQLWf-b": "secret"}),
    ],
)
def test_get_needed_headers_returns_matching_headers(
    original_headers: Dict[str, Any], expected_headers: Dict[str, Any]
) -> None:
    headers = WebDriver(None)._get_needed_headers(original_headers)
    assert headers == expected_headers


@pytest.mark.usefixtures("mock_get_options")
def test_set_account_name_sets_the_correct_values_for_the_name(
    mock_reservation_monitor: mock.Mock,
) -> None:
    WebDriver(None)._set_account_name(
        mock_reservation_monitor,
        {
            "customers.userInformation.firstName": "John",
            "customers.userInformation.lastName": "Doe",
        },
    )

    assert mock_reservation_monitor.first_name == "John"
    assert mock_reservation_monitor.last_name == "Doe"


def test_quit_browser_quits_driver_successfully(
    mocker: MockerFixture, mock_driver: mock.Mock
) -> None:
    mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
    mock_os_waitpid = mocker.patch("os.waitpid")

    webdriver = WebDriver(mock_checkin_scheduler)
    webdriver._quit_browser(mock_driver)

    expected_calls = [
        mock.call(mock_driver.browser_pid, 0),
        mock.call(mock_driver.service.process.pid, 0),
    ]
    mock_driver.quit.assert_called_once()
    mock_os_waitpid.assert_has_calls(expected_calls)


def test_quit_browser_handles_child_process_error(
    mocker: MockerFixture, mock_driver: mock.Mock
) -> None:
    mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
    mock_os_waitpid = mocker.patch("os.waitpid", side_effect=ChildProcessError)

    webdriver = WebDriver(mock_checkin_scheduler)
    webdriver._quit_browser(mock_driver)

    mock_driver.quit.assert_called_once()
    mock_os_waitpid.assert_called_once_with(mock_driver.browser_pid, 0)
