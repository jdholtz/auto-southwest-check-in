from typing import Any, Dict
from unittest import mock

import pytest
from pytest_mock import MockerFixture

from lib.utils import LoginError
from lib.webdriver import (
    CHECKIN_HEADERS_URL,
    INVALID_CREDENTIALS_CODE,
    LOGIN_URL,
    TRIPS_URL,
    WebDriver,
)

# This needs to be accessed to be tested
# pylint: disable=protected-access


@pytest.fixture(autouse=True)
def mock_chrome(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch("lib.webdriver.Driver")


@pytest.fixture
def mock_account_monitor(mocker: MockerFixture) -> mock.Mock:
    mock_monitor = mocker.patch("lib.reservation_monitor.AccountMonitor")
    mock_monitor.username = "test_user"
    mock_monitor.password = "test_password"
    return mock_monitor


class TestWebDriver:
    @pytest.fixture(autouse=True)
    def _set_up_webdriver(self, mocker: MockerFixture) -> None:
        mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
        mock_checkin_scheduler.headers = {}
        # pylint: disable=attribute-defined-outside-init
        self.driver = WebDriver(mock_checkin_scheduler)

    def test_set_headers_correctly_sets_needed_headers(
        self, mocker: MockerFixture, mock_chrome: mock.Mock
    ) -> None:
        mocker.patch.object(self.driver, "_get_driver", return_value=mock_chrome)
        mock_wait_for_attribute = mocker.patch.object(self.driver, "_wait_for_attribute")

        self.driver.set_headers()

        mock_wait_for_attribute.assert_called_once_with("headers_set")
        mock_chrome.quit.assert_called_once()

    def test_get_reservations_fetches_reservations(
        self, mocker: MockerFixture, mock_chrome: mock.Mock, mock_account_monitor: mock.Mock
    ) -> None:
        mocker.patch("lib.webdriver.seleniumbase_actions.wait_for_element_not_visible")
        mocker.patch.object(WebDriver, "_get_driver", return_value=mock_chrome)
        mock_wait_for_attribute = mocker.patch.object(self.driver, "_wait_for_attribute")
        mock_wait_for_login = mocker.patch.object(WebDriver, "_wait_for_login")
        mocker.patch.object(self.driver, "_fetch_reservations", return_value=["res1", "res2"])

        reservations = self.driver.get_reservations(mock_account_monitor)

        assert reservations == ["res1", "res2"]

        mock_wait_for_attribute.assert_called_once()
        mock_wait_for_login.assert_called_once()
        mock_chrome.add_cdp_listener.assert_called_once()
        mock_chrome.quit.assert_called_once()

    def test_get_driver_returns_a_webdriver_with_one_request(self) -> None:
        driver = self.driver._get_driver()

        driver.add_cdp_listener.assert_called_once()
        driver.get.assert_called_once()

    def test_headers_listener_sets_headers_when_correct_url(self, mocker: MockerFixture) -> None:
        mocker.patch.object(self.driver, "_get_needed_headers", return_value={"test": "headers"})
        data = {"params": {"request": {"url": CHECKIN_HEADERS_URL, "headers": {}}}}

        self.driver._headers_listener(data)

        assert self.driver.headers_set
        assert self.driver.checkin_scheduler.headers == {"test": "headers"}

    def test_headers_listener_does_not_set_headers_when_wrong_url(self) -> None:
        data = {"params": {"request": {"url": "fake_url", "headers": {}}}}
        self.driver._headers_listener(data)

        assert not self.driver.headers_set
        assert self.driver.checkin_scheduler.headers == {}

    def test_login_listener_sets_login_information(self) -> None:
        data = {"params": {"response": {"url": LOGIN_URL, "status": 200}, "requestId": "test_id"}}
        self.driver._login_listener(data)

        assert self.driver.login_status_code == 200
        assert self.driver.login_request_id == "test_id"

    def test_login_listener_sets_trip_information(self) -> None:
        data = {"params": {"response": {"url": TRIPS_URL}, "requestId": "test_id"}}
        self.driver._login_listener(data)

        assert self.driver.trips_request_id == "test_id"

    def test_login_listener_sets_no_information_when_wrong_url(self) -> None:
        data = {"params": {"response": {"url": "fake_url"}}}
        self.driver._login_listener(data)

        assert self.driver.login_status_code is None
        assert self.driver.login_request_id is None
        assert self.driver.trips_request_id is None

    def test_wait_for_attribute_waits_for_attribute_to_be_set(self, mocker: MockerFixture) -> None:
        call_count = 0

        def mock_sleep(_: int) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                self.driver.headers_set = True

        mocker.patch("time.sleep", side_effect=mock_sleep)

        self.driver._wait_for_attribute("headers_set")

    def test_wait_for_login_raises_error_on_failed_login(
        self, mocker: MockerFixture, mock_chrome: mock.Mock
    ) -> None:
        mocker.patch.object(WebDriver, "_click_login_button")
        mocker.patch.object(WebDriver, "_wait_for_attribute")
        mocker.patch.object(WebDriver, "_get_response_body")
        mocker.patch.object(WebDriver, "_handle_login_error", return_value=LoginError("", 400))
        mock_set_account_name = mocker.patch.object(WebDriver, "_set_account_name")

        self.driver.login_status_code = 400
        with pytest.raises(LoginError):
            self.driver._wait_for_login(mock_chrome, None)

        mock_set_account_name.assert_not_called()
        mock_chrome.quit.assert_called_once()

    def test_wait_for_login_sets_account_name(self, mocker: MockerFixture) -> None:
        mocker.patch.object(WebDriver, "_click_login_button")
        mocker.patch.object(WebDriver, "_wait_for_attribute")
        mocker.patch.object(WebDriver, "_get_response_body")
        mock_set_account_name = mocker.patch.object(WebDriver, "_set_account_name")

        self.driver.login_status_code = 200
        self.driver._wait_for_login(mock_chrome, None)

        mock_set_account_name.assert_called_once()

    def test_click_login_button_does_not_click_when_form_submits(
        self, mocker: MockerFixture, mock_chrome: mock.Mock
    ) -> None:
        mocker.patch("seleniumbase.fixtures.page_actions.wait_for_element_not_visible")
        self.driver._click_login_button(mock_chrome)
        mock_chrome.click.assert_not_called()

    def test_click_login_button_clicks_when_form_fails_to_submit(
        self, mocker: MockerFixture, mock_chrome: mock.Mock
    ) -> None:
        mocker.patch(
            "seleniumbase.fixtures.page_actions.wait_for_element_not_visible",
            side_effect=[None, Exception],
        )
        self.driver._click_login_button(mock_chrome)
        mock_chrome.click.assert_called_once()

    def test_fetch_reservations_fetches_only_flight_reservations(
        self, mocker: MockerFixture
    ) -> None:
        trips_response = {"upcomingTripsPage": [{"tripType": "FLIGHT"}, {"tripType": "CAR"}]}

        mocker.patch.object(WebDriver, "_wait_for_attribute")
        mocker.patch.object(WebDriver, "_get_response_body", return_value=trips_response)

        assert self.driver._fetch_reservations(None) == [{"tripType": "FLIGHT"}]

    def test_get_response_body_loads_body_from_response(self, mock_chrome: mock.Mock) -> None:
        mock_chrome.execute_cdp_cmd.return_value = {"body": '{"response": "body"}'}
        assert self.driver._get_response_body(mock_chrome, "") == {"response": "body"}

    def test_handle_login_error_handles_invalid_credentials(self) -> None:
        response = {"code": INVALID_CREDENTIALS_CODE}
        self.driver.login_status_code = 400
        error = self.driver._handle_login_error(response)

        assert "Reason: Invalid credentials" in str(error)
        assert "Status code: 400" in str(error)

    def test_handle_login_error_handles_unknown_errors(self) -> None:
        self.driver.login_status_code = 429
        error = self.driver._handle_login_error({})

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
        self, original_headers: Dict[str, Any], expected_headers: Dict[str, Any]
    ) -> None:
        headers = self.driver._get_needed_headers(original_headers)
        assert headers == expected_headers

    def test_set_account_name_does_not_set_name_if_already_set(
        self, mock_account_monitor: mock.Mock
    ) -> None:
        mock_account_monitor.first_name = "Jane"
        self.driver._set_account_name(mock_account_monitor, {})
        assert mock_account_monitor.first_name == "Jane"

    def test_set_account_name_sets_the_correct_values_for_the_name(
        self, mock_account_monitor: mock.Mock
    ) -> None:
        mock_account_monitor.first_name = None
        self.driver._set_account_name(
            mock_account_monitor,
            {
                "customers.userInformation.firstName": "John",
                "customers.userInformation.lastName": "Doe",
            },
        )

        assert mock_account_monitor.first_name == "John"
        assert mock_account_monitor.last_name == "Doe"
