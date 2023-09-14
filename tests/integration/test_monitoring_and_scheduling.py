"""
Tests the ReservationMonitor and CheckInScheduler to ensure flights are correctly scheduled, headers
are set, errors are handled, and integration with the webdriver works.
"""

import copy
import json
from multiprocessing import Lock
from unittest import mock

import pytest
from pytest_mock import MockerFixture
from requests_mock.mocker import Mocker as RequestMocker

from lib.checkin_scheduler import VIEW_RESERVATION_URL
from lib.config import GlobalConfig
from lib.reservation_monitor import AccountMonitor, ReservationMonitor
from lib.utils import BASE_URL
from lib.webdriver import WebDriver

TEST_RESERVATION_URL = BASE_URL + VIEW_RESERVATION_URL + "TEST"

ALL_HEADERS = {
    "Host": "test_host",
    "User-Agent": "test_agent",
    "Accept": "test_accept",
    "Accept-Language": "test_language",
    "Accept-Encoding": "test_encoding",
    "Referer": "test_referer",
    "X-API-Key": "test_key",
    "X-Channel-ID": "test_channel_id",
    "X-User-Experience-ID": "test_ux_id",
    "Content-Type": "test_content",
    "EE30zvQLWf-f": "test_f",
    "EE30zvQLWf-b": "test_b",
    "EE30zvQLWf-c": "test_c",
    "EE30zvQLWf-d": "test_d",
    "EE30zvQLWf-z": "test_q",
    "EE30zvQLWf-a": "test_a",
    "Cookie": "test_cookie",
}

EXPECTED_HEADERS = {
    "User-Agent": "test_agent",
    "X-API-Key": "test_key",
    "X-Channel-ID": "test_channel_id",
    "EE30zvQLWf-f": "test_f",
    "EE30zvQLWf-b": "test_b",
    "EE30zvQLWf-c": "test_c",
    "EE30zvQLWf-d": "test_d",
    "EE30zvQLWf-z": "test_q",
    "EE30zvQLWf-a": "test_a",
}


def test_flight_is_scheduled_checks_in_and_departs(
    requests_mock: RequestMocker, mocker: MockerFixture
) -> None:
    tz_data = {"LAX": "America/Los_Angeles"}

    mocker.patch("pathlib.Path.read_text", return_value=json.dumps(tz_data))
    mock_process = mocker.patch("lib.checkin_handler.Process").return_value
    mock_new_flights_notification = mocker.patch(
        "lib.notification_handler.NotificationHandler.new_flights"
    )
    mocker.patch("os.kill")
    mock_sleep = mocker.patch("time.sleep")

    # Will be checked in a separate integration test
    mock_check_flight_price = mocker.patch("lib.fare_checker.FareChecker.check_flight_price")

    config = GlobalConfig()
    config.create_reservation_config(
        [{"confirmationNumber": "TEST", "firstName": "Berkant", "lastName": "Marika"}]
    )

    def mock_get_driver(self) -> mock.Mock:
        # pylint: disable-next=protected-access
        self.checkin_scheduler.headers = self._get_needed_headers(ALL_HEADERS)
        self.headers_set = True
        return mocker.patch("lib.webdriver.Driver")

    mocker.patch.object(WebDriver, "_get_driver", mock_get_driver)

    reservation1 = {
        "viewReservationViewPage": {
            "bounds": [
                {
                    "arrivalAirport": {"name": "test_inbound"},
                    "arrivalTime": "05:50",
                    "departureAirport": {"code": "LAX", "name": "test_outbound"},
                    "departureDate": "2020-10-13",
                    "departureStatus": None,
                    "departureTime": "14:40",
                },
            ],
        }
    }

    reservation2 = copy.deepcopy(reservation1)
    # Change to departed so the flight is removed
    reservation2["viewReservationViewPage"]["bounds"][0]["departureStatus"] = "DEPARTED"

    requests_mock.get(
        TEST_RESERVATION_URL,
        [{"json": reservation1, "status_code": 200}, {"json": reservation2, "status_code": 200}],
    )

    monitor = ReservationMonitor(config.reservations[0], Lock())
    monitor.monitor()

    scheduler = monitor.checkin_scheduler

    # Ensure the correct headers are set
    assert scheduler.headers == EXPECTED_HEADERS

    # Ensure the flight was scheduled correctly
    mock_process.start.assert_called_once()
    assert mock_new_flights_notification.call_count == 2

    # Ensure the flight was removed after it departed
    assert len(scheduler.checkin_handlers) == 0
    assert len(scheduler.flights) == 0

    mock_check_flight_price.assert_called_once()

    # Validate that it exited before the second sleep
    mock_sleep.assert_called_once()


def test_account_schedules_new_flights(requests_mock: RequestMocker, mocker: MockerFixture) -> None:
    config = GlobalConfig()
    config.create_account_config([{"username": "test_user", "password": "test_pass"}])

    tz_data = {"LAX": "America/Los_Angeles", "SYD": "Australia/Sydney"}
    mocker.patch("pathlib.Path.read_text", return_value=json.dumps(tz_data))

    mocker.patch("lib.webdriver.WebDriverWait")
    mock_process = mocker.patch("lib.checkin_handler.Process").return_value
    # Raise a StopIteration to prevent an infinite loop
    mocker.patch("time.sleep", side_effect=[None, None, StopIteration])

    # Will be checked in a separate integration test
    mock_check_flight_price = mocker.patch("lib.fare_checker.FareChecker.check_flight_price")

    login_response = {
        "body": (
            '{"customers.userInformation.firstName": "Forrest", '
            '"customers.userInformation.lastName": "Gump"}'
        )
    }

    trips_response = {
        "body": (
            '{"upcomingTripsPage": [{"tripType": "FLIGHT", "confirmationNumber": "TEST"}, '
            '{"tripType": "CAR"}]}'
        )
    }

    login_attempts = 0

    def mock_get_driver(self) -> mock.Mock:
        """
        Adds login and trips responses. The second login request will be a 429 to test
        that the error is handled correctly.
        """
        nonlocal login_attempts
        login_attempts += 1

        # pylint: disable-next=protected-access
        self.checkin_scheduler.headers = self._get_needed_headers(ALL_HEADERS)
        self.headers_set = True

        if login_attempts == 2:
            # Respond with a 429 error to ensure it is handled correctly
            self.login_status_code = 429
        else:
            self.login_status_code = 200

        self.login_request_id = "login"
        self.trips_request_id = "trips"

        mock_driver = mocker.patch("lib.webdriver.Driver")
        mock_driver.execute_cdp_cmd.side_effect = [login_response, trips_response]
        return mock_driver

    mocker.patch.object(WebDriver, "_get_driver", mock_get_driver)

    reservation = {
        "viewReservationViewPage": {
            "bounds": [
                {
                    "arrivalAirport": {"name": "test_inbound"},
                    "arrivalTime": "05:50",
                    "departureAirport": {"code": "LAX", "name": "test_outbound"},
                    "departureDate": "2020-10-13",
                    "departureStatus": None,
                    "departureTime": "14:40",
                },
                {
                    "arrivalAirport": {"name": "test_outbound"},
                    "arrivalTime": "22:30",
                    "departureAirport": {"code": "SYD", "name": "test_inbound"},
                    "departureDate": "2020-10-16",
                    "departureStatus": None,
                    "departureTime": "07:20",
                },
            ],
        }
    }

    requests_mock.get(TEST_RESERVATION_URL, [{"json": reservation, "status_code": 200}])

    monitor = AccountMonitor(config.accounts[0], Lock())
    with pytest.raises(StopIteration):
        monitor.monitor()

    scheduler = monitor.checkin_scheduler

    # Ensure the correct name and headers are set
    assert scheduler.headers == EXPECTED_HEADERS
    assert monitor.first_name == "Forrest"
    assert monitor.last_name == "Gump"

    # Ensure flights are scheduled correctly
    assert mock_process.start.call_count == 2
    assert len(scheduler.checkin_handlers) == 2
    assert len(scheduler.flights) == 2

    # Ensures the 429 error was handled correctly
    assert mock_check_flight_price.call_count == 2 * len(scheduler.flights)
