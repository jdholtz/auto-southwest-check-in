import signal
from datetime import datetime
from unittest import mock

import pytest
from pytest_mock import MockerFixture

from lib.checkin_handler import MAX_CHECK_IN_ATTEMPTS, CheckInHandler
from lib.utils import AirportCheckInError, DriverTimeoutError, RequestError

# This needs to be accessed to be tested
# pylint: disable=protected-access


class TestCheckInHandler:
    """Contains common tests between the CheckInHandler and the SameDayCheckInHandler"""

    @pytest.fixture(autouse=True)
    def _set_up_handler(self, mocker: MockerFixture) -> None:
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
        assert self.handler.pid is not None, "PID was not set while scheduling a check-in"

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
        mocker.patch(
            "lib.checkin_handler.get_current_time", return_value=datetime(1999, 12, 31, 18, 30)
        )
        self.handler._wait_for_check_in(datetime(1999, 12, 31, 18))
        mock_sleep.assert_not_called()

    def test_wait_for_check_in_sleeps_once_when_check_in_is_less_than_or_equal_to_thirty_mins_away(
        self, mocker: MockerFixture
    ) -> None:
        mock_sleep = mocker.patch("time.sleep")
        mocker.patch(
            "lib.checkin_handler.get_current_time", return_value=datetime(1999, 12, 31, 18, 29, 59)
        )

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
        mock_refresh_headers = mocker.patch.object(
            self.handler.checkin_scheduler, "refresh_headers"
        )
        mocker.patch(
            "lib.checkin_handler.get_current_time",
            side_effect=[
                datetime(1999, 12, 31, 18, 29, 59),
                datetime(1999, 12, 31, 23, 19, 59),
            ],
        )

        self.handler._wait_for_check_in(datetime(1999, 12, 31, 23, 49, 59))

        mock_sleep.assert_has_calls([mock.call(17400), mock.call(1800)])
        mock_refresh_headers.assert_called_once()

    @pytest.mark.filterwarnings(
        # Mocking multiprocessing.Lock causes this warning
        "ignore:Mocks returned by pytest-mock do not need to be used as context managers:"
    )
    def test_wait_for_check_in_handles_timeout_refreshing_headers(
        self, mocker: MockerFixture
    ) -> None:
        mock_sleep = mocker.patch("time.sleep")
        mocker.patch.object(
            self.handler.checkin_scheduler, "refresh_headers", side_effect=DriverTimeoutError
        )
        mock_timeout_before_checkin_notification = mocker.patch.object(
            self.handler.notification_handler, "timeout_before_checkin"
        )
        mocker.patch(
            "lib.checkin_handler.get_current_time",
            side_effect=[
                datetime(1999, 12, 31, 18, 29, 59),
                datetime(1999, 12, 31, 23, 19, 59),
            ],
        )

        self.handler._wait_for_check_in(datetime(1999, 12, 31, 23, 49, 59))
        mock_sleep.assert_has_calls([mock.call(17400), mock.call(1800)])
        mock_timeout_before_checkin_notification.assert_called_once()

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
        mocker.patch.object(CheckInHandler, "_attempt_check_in", side_effect=RequestError(""))
        mock_notification_handler = mocker.patch("lib.notification_handler.NotificationHandler")

        self.handler.notification_handler = mock_notification_handler
        self.handler._check_in()

        mock_notification_handler.failed_checkin.assert_called_once()
        mock_notification_handler.successful_checkin.assert_not_called()

    def test_check_in_sends_airport_check_in_notification_for_airport_check_in_error(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(CheckInHandler, "_attempt_check_in", side_effect=AirportCheckInError)
        mock_notification_handler = mocker.patch("lib.notification_handler.NotificationHandler")

        self.handler.notification_handler = mock_notification_handler
        self.handler._check_in()

        mock_notification_handler.airport_checkin_required.assert_called_once()
        mock_notification_handler.successful_checkin.assert_not_called()

    def test_check_in_sends_success_notification_on_successful_check_in(
        self, mocker: MockerFixture
    ) -> None:
        post_response = {"checkInConfirmationPage": "Checked In!"}
        mock_successful_checkin_notification = mocker.patch.object(
            self.handler.notification_handler, "successful_checkin"
        )
        mocker.patch.object(CheckInHandler, "_attempt_check_in", return_value=post_response)

        self.handler._check_in()

        mock_successful_checkin_notification.assert_called_once_with(
            "Checked In!", self.handler.flight
        )

    def test_attempt_check_in_succeeds_first_time_when_flight_is_not_same_day(
        self, mocker: MockerFixture
    ) -> None:
        post_response = {"checkInConfirmationPage": {"flights": ["flight1"]}}
        mock_check_in_to_flight = mocker.patch.object(
            CheckInHandler, "_check_in_to_flight", return_value=post_response
        )

        self.handler.flight.is_same_day = False
        reservation = self.handler._attempt_check_in()

        mock_check_in_to_flight.assert_called_once()
        assert reservation == post_response

    def test_submit_check_in_succeeds_after_multiple_attempts(self, mocker: MockerFixture) -> None:
        first_post_response = {"checkInConfirmationPage": {"flights": ["flight1"]}}
        second_post_response = {"checkInConfirmationPage": {"flights": ["flight1", "flight2"]}}
        mocker.patch.object(
            CheckInHandler,
            "_check_in_to_flight",
            side_effect=[first_post_response, second_post_response],
        )
        mock_sleep = mocker.patch("time.sleep")

        self.handler.flight.is_same_day = True
        reservation = self.handler._attempt_check_in()

        assert reservation == second_post_response
        mock_sleep.assert_called_once()

    def test_submit_check_in_fails_when_max_attempts_reached(self, mocker: MockerFixture) -> None:
        post_response = {"checkInConfirmationPage": {"flights": ["flight1"]}}
        mock_check_in_to_flight = mocker.patch.object(
            CheckInHandler, "_check_in_to_flight", return_value=post_response
        )
        mocker.patch("time.sleep")

        self.handler.flight.is_same_day = True
        with pytest.raises(RequestError):
            self.handler._attempt_check_in()

        assert mock_check_in_to_flight.call_count == MAX_CHECK_IN_ATTEMPTS

    def test_check_in_to_flight_sends_get_then_post_request(self, mocker: MockerFixture) -> None:
        get_response = {
            "checkInViewReservationPage": {"_links": {"checkIn": {"href": "", "body": ""}}}
        }
        post_response = {"checkInConfirmationPage": "Checked In!"}
        mocker.patch("lib.checkin_handler.make_request", side_effect=[get_response, post_response])

        assert self.handler._check_in_to_flight() == post_response
