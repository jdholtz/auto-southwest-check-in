import os
from datetime import datetime
from unittest import mock

import pytest
import pytz
from pytest_mock import MockerFixture

from lib.account import Account
from lib.flight import TZ_FILE_PATH, Flight
from lib.general import CheckInError, NotificationLevel

# This needs to be accessed to be tested
# pylint: disable=protected-access


@pytest.fixture
def test_flight(mocker: MockerFixture) -> Flight:
    mocker.patch("multiprocessing.Process.start")
    account = Account()

    # Needs to be mocked so it isn't run when Flight is instantiated
    with mock.patch.object(Flight, "_get_flight_info"):
        return Flight(account, "test_num", {})


def test_get_flight_info_sets_the_correct_info(mocker: MockerFixture, test_flight: Flight) -> None:
    mocker.patch.object(Flight, "_get_flight_time", return_value="12:31:05")
    test_flight._get_flight_info(
        {"departureAirport": {"name": "LAX"}, "arrivalAirport": {"name": "LHR"}}
    )

    assert test_flight.departure_airport == "LAX"
    assert test_flight.destination_airport == "LHR"
    assert test_flight.departure_time == "12:31:05"


def test_get_flight_time_returns_the_correct_time(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    mock_get_airport_tz = mocker.patch.object(
        Flight, "_get_airport_timezone", return_value="Asia/Calcutta"
    )
    mock_convert_to_utc = mocker.patch.object(Flight, "_convert_to_utc", return_value="12:31:05")

    flight_info = {
        "departureDate": "12-31-99",
        "departureTime": "23:59:59",
        "departureAirport": {"code": "999"},
    }
    flight_time = test_flight._get_flight_time(flight_info)

    mock_get_airport_tz.assert_called_once_with("999")
    mock_convert_to_utc.assert_called_once_with("12-31-99 23:59:59", "Asia/Calcutta")
    assert flight_time == "12:31:05"


def test_get_airport_timezone_returns_the_correct_timezone(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    # Needs to be mocked within the flight module because pytz opens a file as well
    mock_open = mocker.patch(
        "lib.flight.open", mock.mock_open(read_data='{"test_code": "Asia/Calcutta"}')
    )
    timezone = test_flight._get_airport_timezone("test_code")

    assert timezone == pytz.timezone("Asia/Calcutta")
    mock_open.assert_called_once_with(
        os.path.dirname(os.path.dirname(__file__)) + "/" + TZ_FILE_PATH
    )


def test_convert_to_utc_converts_local_time_to_utc(test_flight: Flight) -> None:
    tz = pytz.timezone("Asia/Calcutta")
    utc_flight_time = test_flight._convert_to_utc("1999-12-31 23:59", tz)

    assert utc_flight_time == datetime(1999, 12, 31, 18, 29)


def test_set_check_in_correctly_sets_up_check_in_process(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    test_flight.departure_time = datetime(1999, 12, 31, 18, 29)
    mock_wait_for_check_in = mocker.patch.object(Flight, "_wait_for_check_in")
    mock_check_in = mocker.patch.object(Flight, "_check_in")

    test_flight._set_check_in()

    mock_wait_for_check_in.assert_called_once_with(datetime(1999, 12, 30, 18, 28, 55))
    mock_check_in.assert_called_once()


def test_wait_for_check_in_exits_immediately_if_checkin_time_has_passed(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    mock_sleep = mocker.patch("time.sleep")
    test_flight._wait_for_check_in(datetime(1999, 12, 31))
    mock_sleep.assert_not_called()


def test_wait_for_check_in_sleeps_once_when_check_in_is_less_than_ten_minutes_away(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    mock_sleep = mocker.patch("time.sleep")
    mock_datetime = mocker.patch("lib.flight.datetime")
    mock_datetime.utcnow.return_value = datetime(1999, 12, 31, 18, 29, 59)

    test_flight._wait_for_check_in(datetime(1999, 12, 31, 18, 39, 59))

    mock_sleep.assert_called_once_with(600)


def test_wait_for_check_in_refreshes_headers_ten_minutes_before_check_in(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    mock_sleep = mocker.patch("time.sleep")
    mock_refresh_headers = mocker.patch.object(Account, "refresh_headers")
    mock_datetime = mocker.patch("lib.flight.datetime")
    mock_datetime.utcnow.side_effect = [
        datetime(1999, 12, 31, 18, 29, 59),
        datetime(1999, 12, 31, 23, 19, 59),
    ]

    test_flight._wait_for_check_in(datetime(1999, 12, 31, 23, 29, 59))

    mock_sleep.assert_has_calls([mock.call(17400), mock.call(600)])
    mock_refresh_headers.assert_called_once()


def test_check_in_sends_error_notification_when_check_in_fails(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    mocker.patch("lib.flight.make_request", side_effect=CheckInError())
    mock_send_notification = mocker.patch.object(Account, "send_notification")

    test_flight._check_in()

    mock_send_notification.assert_called_once()
    assert mock_send_notification.call_args[0][1] == NotificationLevel.ERROR


def test_check_in_sends_results_on_successful_check_in(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    get_response = {"checkInViewReservationPage": {"_links": {"checkIn": {"href": "", "body": ""}}}}
    post_response = {"checkInConfirmationPage": "Checked In!"}
    mock_send_results = mocker.patch.object(Flight, "_send_results")
    mocker.patch("lib.flight.make_request", side_effect=[get_response, post_response])

    test_flight._check_in()

    mock_send_results.assert_called_once_with("Checked In!")


def test_send_results_sends_a_notification_and_prints_the_message(
    mocker: MockerFixture, test_flight: Flight, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_send_notification = mocker.patch.object(Account, "send_notification")
    test_flight._send_results(
        {
            "flights": [
                {"passengers": [{"name": "John", "boardingGroup": "A", "boardingPosition": "1"}]}
            ]
        }
    )

    assert mock_send_notification.call_args[0][1] == NotificationLevel.INFO
    # None is in place for the flight info because it was never set
    assert (
        capsys.readouterr().out
        == "Successfully checked in to flight from 'None' to 'None' for None None!\nJohn got A1!\n\n"
    )
