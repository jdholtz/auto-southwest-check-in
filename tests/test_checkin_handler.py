import signal
from datetime import datetime
from unittest import mock

import pytest
from pytest_mock import MockerFixture

from lib.checkin_handler import CheckInHandler
from lib.utils import RequestError

# This needs to be accessed to be tested
# pylint: disable=protected-access


@pytest.fixture
def checkin_handler(mocker: MockerFixture) -> CheckInHandler:
    test_flight = mocker.patch("lib.checkin_handler.Flight")

    mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
    return CheckInHandler(mock_checkin_scheduler, test_flight)


def test_schedule_check_in_starts_a_process(
    mocker: MockerFixture, checkin_handler: CheckInHandler
) -> None:
    mock_process = mocker.patch("lib.checkin_handler.Process")
    mock_process.start = mock.Mock()

    checkin_handler.schedule_check_in()

    mock_process.return_value.start.assert_called_once()
    assert checkin_handler.pid is not None


def test_stop_check_in_stops_a_process_by_killing_its_pid(
    mocker: MockerFixture, checkin_handler: CheckInHandler
) -> None:
    mock_os_kill = mocker.patch("os.kill")
    mock_os_waitpid = mocker.patch("os.waitpid")

    checkin_handler.stop_check_in()

    mock_os_kill.assert_called_once_with(checkin_handler.pid, signal.SIGTERM)
    mock_os_waitpid.assert_called_once_with(checkin_handler.pid, 0)


def test_stop_check_in_handles_child_process_error(
    mocker: MockerFixture, checkin_handler: CheckInHandler
) -> None:
    mock_os_kill = mocker.patch("os.kill")
    mock_os_waitpid = mocker.patch("os.waitpid", side_effect=ChildProcessError)

    checkin_handler.stop_check_in()

    mock_os_kill.assert_called_once_with(checkin_handler.pid, signal.SIGTERM)
    mock_os_waitpid.assert_called_once_with(checkin_handler.pid, 0)


def test_set_check_in_correctly_sets_up_check_in_process(
    mocker: MockerFixture, checkin_handler: CheckInHandler
) -> None:
    checkin_handler.flight.departure_time = datetime(1999, 12, 31, 18, 29)
    mock_wait_for_check_in = mocker.patch.object(CheckInHandler, "_wait_for_check_in")
    mock_check_in = mocker.patch.object(CheckInHandler, "_check_in")

    checkin_handler._set_check_in()

    mock_wait_for_check_in.assert_called_once_with(datetime(1999, 12, 30, 18, 28, 55))
    mock_check_in.assert_called_once()


def test_set_check_in_passes_on_keyboard_interrupt(
    mocker: MockerFixture, checkin_handler: CheckInHandler
) -> None:
    mocker.patch.object(CheckInHandler, "_wait_for_check_in", side_effect=KeyboardInterrupt)
    checkin_handler._set_check_in()


def test_wait_for_check_in_exits_immediately_if_checkin_time_has_passed(
    mocker: MockerFixture, checkin_handler: CheckInHandler
) -> None:
    mock_sleep = mocker.patch("time.sleep")
    checkin_handler._wait_for_check_in(datetime(1999, 12, 31))
    mock_sleep.assert_not_called()


def test_wait_for_check_in_sleeps_once_when_check_in_is_less_than_ten_minutes_away(
    mocker: MockerFixture, checkin_handler: CheckInHandler
) -> None:
    mock_sleep = mocker.patch("time.sleep")
    mock_datetime = mocker.patch("lib.checkin_handler.datetime")
    mock_datetime.utcnow.return_value = datetime(1999, 12, 31, 18, 29, 59)

    checkin_handler._wait_for_check_in(datetime(1999, 12, 31, 18, 39, 59))

    mock_sleep.assert_called_once_with(600)


def test_wait_for_check_in_refreshes_headers_ten_minutes_before_check_in(
    mocker: MockerFixture, checkin_handler: CheckInHandler
) -> None:
    mock_sleep = mocker.patch("time.sleep")
    mock_refresh_headers = checkin_handler.checkin_scheduler.refresh_headers
    mock_datetime = mocker.patch("lib.checkin_handler.datetime")
    mock_datetime.utcnow.side_effect = [
        datetime(1999, 12, 31, 18, 29, 59),
        datetime(1999, 12, 31, 23, 19, 59),
    ]

    checkin_handler._wait_for_check_in(datetime(1999, 12, 31, 23, 29, 59))

    mock_sleep.assert_has_calls([mock.call(17400), mock.call(600)])
    mock_refresh_headers.assert_called_once()


@pytest.mark.parametrize(["weeks", "expected_sleep_calls"], [(0, 0), (1, 1), (3, 2)])
def test_safe_sleep_sleeps_in_intervals(
    mocker: MockerFixture, checkin_handler: CheckInHandler, weeks: int, expected_sleep_calls: int
) -> None:
    mock_sleep = mocker.patch("time.sleep")

    total_sleep_time = weeks * 7 * 24 * 60 * 60
    checkin_handler._safe_sleep(total_sleep_time)

    assert mock_sleep.call_count == expected_sleep_calls


def test_check_in_sends_error_notification_when_check_in_fails(
    mocker: MockerFixture, checkin_handler: CheckInHandler
) -> None:
    mocker.patch("lib.checkin_handler.make_request", side_effect=RequestError("", ""))
    mock_notification_handler = mocker.patch("lib.notification_handler.NotificationHandler")

    checkin_handler.notification_handler = mock_notification_handler
    checkin_handler._check_in()

    mock_notification_handler.failed_checkin.assert_called_once()


def test_check_in_sends_success_notification_on_successful_check_in(
    mocker: MockerFixture, checkin_handler: CheckInHandler
) -> None:
    get_response = {"checkInViewReservationPage": {"_links": {"checkIn": {"href": "", "body": ""}}}}
    post_response = {"checkInConfirmationPage": "Checked In!"}
    mock_notification_handler = mocker.patch("lib.notification_handler.NotificationHandler")
    mocker.patch("lib.checkin_handler.make_request", side_effect=[get_response, post_response])

    checkin_handler.notification_handler = mock_notification_handler
    checkin_handler._check_in()

    mock_notification_handler.successful_checkin.assert_called_once_with(
        "Checked In!", checkin_handler.flight
    )
