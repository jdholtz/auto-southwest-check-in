import signal
from datetime import datetime
from unittest import mock

import pytest
from pytest_mock import MockerFixture

from lib.checkin_handler import CheckInHandler
from lib.utils import RequestError

# This needs to be accessed to be tested
# pylint: disable=protected-access


class TestCheckInHandler:
    @pytest.fixture(autouse=True)
    def _set_up_checkin_handler(self, mocker: MockerFixture) -> None:
        test_flight = mocker.patch("lib.checkin_handler.Flight")
        mock_checkin_scheduler = mocker.patch("lib.checkin_scheduler.CheckInScheduler")
        mock_lock = mocker.patch("multiprocessing.Lock")

        # pylint: disable=attribute-defined-outside-init
        self.handler = CheckInHandler(mock_checkin_scheduler, test_flight, mock_lock)
        # This would usually be set in schedule_check_in, but that won't be run for every test
        self.handler.pid = 0

    def test_schedule_check_in_starts_a_process(self, mocker: MockerFixture) -> None:
        mock_process = mocker.patch("lib.checkin_handler.Process")

        self.handler.schedule_check_in()

        mock_process.return_value.start.assert_called_once()
        assert self.handler.pid is not None

    def test_stop_check_in_stops_a_process_by_killing_its_pid(self, mocker: MockerFixture) -> None:
        mock_os_kill = mocker.patch("os.kill")
        mock_os_waitpid = mocker.patch("os.waitpid")

        self.handler.stop_check_in()

        mock_os_kill.assert_called_once_with(self.handler.pid, signal.SIGTERM)
        mock_os_waitpid.assert_called_once_with(self.handler.pid, 0)

    def test_stop_check_in_handles_permission_error(self, mocker: MockerFixture) -> None:
        mock_os_kill = mocker.patch("os.kill", side_effect=PermissionError)
        mock_os_waitpid = mocker.patch("os.waitpid")

        self.handler.stop_check_in()

        mock_os_kill.assert_called_once_with(self.handler.pid, signal.SIGTERM)
        mock_os_waitpid.assert_not_called()

    def test_stop_check_in_handles_child_process_error(self, mocker: MockerFixture) -> None:
        mock_os_kill = mocker.patch("os.kill")
        mock_os_waitpid = mocker.patch("os.waitpid", side_effect=ChildProcessError)

        self.handler.stop_check_in()

        mock_os_kill.assert_called_once_with(self.handler.pid, signal.SIGTERM)
        mock_os_waitpid.assert_called_once_with(self.handler.pid, 0)

    def test_set_check_in_correctly_sets_up_check_in_process(self, mocker: MockerFixture) -> None:
        self.handler.flight.departure_time = datetime(1999, 12, 31, 18, 29)
        mock_wait_for_check_in = mocker.patch.object(CheckInHandler, "_wait_for_check_in")
        mock_check_in = mocker.patch.object(CheckInHandler, "_check_in")

        self.handler._set_check_in()

        mock_wait_for_check_in.assert_called_once_with(datetime(1999, 12, 30, 18, 28, 55))
        mock_check_in.assert_called_once()

    def test_set_check_in_passes_on_keyboard_interrupt(self, mocker: MockerFixture) -> None:
        mocker.patch.object(CheckInHandler, "_wait_for_check_in", side_effect=KeyboardInterrupt)
        self.handler._set_check_in()

    def test_wait_for_check_in_exits_immediately_if_checkin_time_has_passed(
        self, mocker: MockerFixture
    ) -> None:
        mock_sleep = mocker.patch("time.sleep")
        self.handler._wait_for_check_in(datetime(1999, 12, 31))
        mock_sleep.assert_not_called()

    def test_wait_for_check_in_sleeps_once_when_check_in_is_less_than_thirty_minutes_away(
        self, mocker: MockerFixture
    ) -> None:
        mock_sleep = mocker.patch("time.sleep")
        mock_datetime = mocker.patch("lib.checkin_handler.datetime")
        mock_datetime.utcnow.return_value = datetime(1999, 12, 31, 18, 29, 59)

        self.handler._wait_for_check_in(datetime(1999, 12, 31, 18, 59, 59))

        mock_sleep.assert_called_once_with(1800)

    @pytest.mark.filterwarnings(
        # Mocking multiprocessing.Lock causes this warning
        "ignore:Mocks returned by pytest-mock do not need to be used as context managers:"
    )
    def test_wait_for_check_in_refreshes_headers_thirty_minutes_before_check_in(
        self, mocker: MockerFixture
    ) -> None:
        mock_sleep = mocker.patch("time.sleep")
        mock_refresh_headers = self.handler.checkin_scheduler.refresh_headers
        mock_datetime = mocker.patch("lib.checkin_handler.datetime")
        mock_datetime.utcnow.side_effect = [
            datetime(1999, 12, 31, 18, 29, 59),
            datetime(1999, 12, 31, 23, 19, 59),
        ]

        self.handler._wait_for_check_in(datetime(1999, 12, 31, 23, 49, 59))

        mock_sleep.assert_has_calls([mock.call(17400), mock.call(1800)])
        mock_refresh_headers.assert_called_once()

    @pytest.mark.parametrize(["weeks", "expected_sleep_calls"], [(0, 0), (1, 1), (3, 2)])
    def test_safe_sleep_sleeps_in_intervals(
        self, mocker: MockerFixture, weeks: int, expected_sleep_calls: int
    ) -> None:
        mock_sleep = mocker.patch("time.sleep")

        total_sleep_time = weeks * 7 * 24 * 60 * 60
        self.handler._safe_sleep(total_sleep_time)

        assert mock_sleep.call_count == expected_sleep_calls

    def test_check_in_sends_error_notification_when_check_in_fails(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch("lib.checkin_handler.make_request", side_effect=RequestError("", ""))
        mock_notification_handler = mocker.patch("lib.notification_handler.NotificationHandler")

        self.handler.notification_handler = mock_notification_handler
        self.handler._check_in()

        mock_notification_handler.failed_checkin.assert_called_once()

    def test_check_in_sends_success_notification_on_successful_check_in(
        self, mocker: MockerFixture
    ) -> None:
        get_response = {
            "checkInViewReservationPage": {"_links": {"checkIn": {"href": "", "body": ""}}}
        }
        post_response = {"checkInConfirmationPage": "Checked In!"}
        mock_notification_handler = mocker.patch("lib.notification_handler.NotificationHandler")
        mocker.patch("lib.checkin_handler.make_request", side_effect=[get_response, post_response])

        self.handler.notification_handler = mock_notification_handler
        self.handler._check_in()

        mock_notification_handler.successful_checkin.assert_called_once_with(
            "Checked In!", self.handler.flight
        )
