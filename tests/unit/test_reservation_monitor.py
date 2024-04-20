import multiprocessing
from datetime import datetime
from unittest import mock

import pytest
from pytest_mock import MockerFixture

from lib.checkin_handler import CheckInHandler
from lib.checkin_scheduler import CheckInScheduler
from lib.config import AccountConfig, ReservationConfig
from lib.fare_checker import FareChecker
from lib.notification_handler import NotificationHandler
from lib.reservation_monitor import TOO_MANY_REQUESTS_CODE, AccountMonitor, ReservationMonitor
from lib.utils import FlightChangeError, LoginError, RequestError
from lib.webdriver import WebDriver

# This needs to be accessed to be tested
# pylint: disable=protected-access


@pytest.fixture
def mock_lock(mocker: MockerFixture) -> None:
    return mocker.patch("multiprocessing.Lock")


@pytest.mark.filterwarnings(
    # Mocking multiprocessing.Lock causes this warning
    "ignore:Mocks returned by pytest-mock do not need to be used as context managers:"
)
class TestReservationMonitor:
    @pytest.fixture(autouse=True)
    def _set_up_monitor(self, mock_lock: mock.Mock, mocker: MockerFixture) -> None:
        # pylint: disable=attribute-defined-outside-init
        self.monitor = ReservationMonitor(ReservationConfig(), mock_lock)
        mocker.patch(
            "lib.reservation_monitor.get_current_time", return_value=datetime(1999, 12, 31)
        )

    def test_start_starts_a_process(self, mocker: MockerFixture) -> None:
        mock_process_start = mocker.patch.object(multiprocessing.Process, "start")

        self.monitor.start()
        mock_process_start.assert_called_once()

    def test_monitor_monitors(self, mocker: MockerFixture) -> None:
        mock_monitor = mocker.patch.object(ReservationMonitor, "_monitor")

        self.monitor.monitor()
        mock_monitor.assert_called_once()

    def test_monitor_handles_keyboard_interrupt(self, mocker: MockerFixture) -> None:
        mocker.patch.object(ReservationMonitor, "_monitor", side_effect=KeyboardInterrupt)
        mock_stop_monitoring = mocker.patch.object(ReservationMonitor, "_stop_monitoring")

        self.monitor.monitor()
        mock_stop_monitoring.assert_called_once()

    def test_monitor_monitors_reservations_continuously(self, mocker: MockerFixture) -> None:
        # Since the monitor function runs in an infinite loop, throw an Exception when the
        # sleep function is called a second time to break out of the loop.
        mocker.patch.object(ReservationMonitor, "_smart_sleep", side_effect=["", StopIteration])
        mock_refresh_headers = mocker.patch.object(CheckInScheduler, "refresh_headers")
        mock_schedule_reservations = mocker.patch.object(
            ReservationMonitor, "_schedule_reservations"
        )
        mock_check_flight_fares = mocker.patch.object(ReservationMonitor, "_check_flight_fares")

        self.monitor.config.confirmation_number = "test_num"
        self.monitor.checkin_scheduler.flights = ["test_flight"]

        with pytest.raises(StopIteration):
            self.monitor._monitor()

        assert mock_refresh_headers.call_count == 2
        assert mock_schedule_reservations.call_count == 2
        mock_schedule_reservations.assert_called_with(
            [{"confirmationNumber": self.monitor.config.confirmation_number}]
        )
        assert mock_check_flight_fares.call_count == 2

    def test_monitor_stops_monitoring_when_no_flights_are_scheduled(
        self, mocker: MockerFixture
    ) -> None:
        mock_smart_sleep = mocker.patch.object(ReservationMonitor, "_smart_sleep")
        mock_refresh_headers = mocker.patch.object(CheckInScheduler, "refresh_headers")
        mock_schedule_reservations = mocker.patch.object(
            ReservationMonitor, "_schedule_reservations"
        )
        mock_check_flight_fares = mocker.patch.object(ReservationMonitor, "_check_flight_fares")

        self.monitor._monitor()

        mock_refresh_headers.assert_called_once()
        mock_schedule_reservations.assert_called_once()
        mock_check_flight_fares.assert_not_called()
        mock_smart_sleep.assert_not_called()

    def test_monitor_monitors_reservations_once_if_retrieval_interval_is_zero(
        self, mocker: MockerFixture
    ) -> None:
        mock_smart_sleep = mocker.patch.object(ReservationMonitor, "_smart_sleep")
        mock_refresh_headers = mocker.patch.object(CheckInScheduler, "refresh_headers")
        mock_schedule_reservations = mocker.patch.object(
            ReservationMonitor, "_schedule_reservations"
        )
        mock_check_flight_fares = mocker.patch.object(ReservationMonitor, "_check_flight_fares")

        self.monitor.config.retrieval_interval = 0
        self.monitor.checkin_scheduler.flights = ["test_flight"]

        self.monitor._monitor()

        mock_refresh_headers.assert_called_once()
        mock_schedule_reservations.assert_called_once()
        mock_check_flight_fares.assert_called_once()
        mock_smart_sleep.assert_not_called()

    def test_schedule_reservations_schedules_reservations_correctly(
        self, mocker: MockerFixture
    ) -> None:
        mock_process_reservations = mocker.patch.object(CheckInScheduler, "process_reservations")
        reservations = [{"confirmationNumber": "Test1"}, {"confirmationNumber": "Test2"}]

        self.monitor._schedule_reservations(reservations)

        mock_process_reservations.assert_called_once_with(["Test1", "Test2"])

    def test_check_flight_fares_does_not_check_fares_if_configuration_is_false(
        self, mocker: MockerFixture
    ) -> None:
        mock_fare_checker = mocker.patch("lib.reservation_monitor.FareChecker")

        self.monitor.config.check_fares = False
        self.monitor._check_flight_fares()

        mock_fare_checker.assert_not_called()

    def test_check_flight_fares_checks_fares_on_all_flights(self, mocker: MockerFixture) -> None:
        test_flight = mocker.patch("lib.checkin_handler.Flight")
        mock_check_flight_price = mocker.patch.object(FareChecker, "check_flight_price")

        self.monitor.config.check_fares = True
        self.monitor.checkin_scheduler.flights = [test_flight, test_flight]
        self.monitor._check_flight_fares()

        assert mock_check_flight_price.call_count == len(self.monitor.checkin_scheduler.flights)

    @pytest.mark.parametrize("exception", [RequestError("", ""), FlightChangeError, Exception])
    def test_check_flight_fares_catches_error_when_checking_fares(
        self, mocker: MockerFixture, exception: Exception
    ) -> None:
        test_flight = mocker.patch("lib.checkin_handler.Flight")
        mock_check_flight_price = mocker.patch.object(
            FareChecker, "check_flight_price", side_effect=[None, exception]
        )

        self.monitor.config.check_fares = True
        self.monitor.checkin_scheduler.flights = [test_flight, test_flight]
        self.monitor._check_flight_fares()

        assert mock_check_flight_price.call_count == len(self.monitor.checkin_scheduler.flights)

    def test_smart_sleep_sleeps_for_correct_time(self, mocker: MockerFixture) -> None:
        mock_sleep = mocker.patch("time.sleep")
        mocker.patch(
            "lib.reservation_monitor.get_current_time", return_value=datetime(1999, 12, 31)
        )

        self.monitor.config.retrieval_interval = 24 * 60 * 60
        self.monitor._smart_sleep(datetime(1999, 12, 30, 12))

        mock_sleep.assert_called_once_with(12 * 60 * 60)

    def test_stop_checkins_stops_all_checkins(self, mocker: MockerFixture) -> None:
        mock_checkin_handler = mocker.patch.object(CheckInHandler, "stop_check_in")

        self.monitor.checkin_scheduler.checkin_handlers = [mock_checkin_handler] * 2
        self.monitor._stop_checkins()

        assert mock_checkin_handler.stop_check_in.call_count == 2

    def test_stop_monitoring_stops_checkins(self, mocker: MockerFixture) -> None:
        mock_stop_checkins = mocker.patch.object(ReservationMonitor, "_stop_checkins")
        self.monitor._stop_monitoring()
        mock_stop_checkins.assert_called_once()


@pytest.mark.filterwarnings(
    # Mocking multiprocessing.Lock causes this warning
    "ignore:Mocks returned by pytest-mock do not need to be used as context managers:"
)
class TestAccountMonitor:
    @pytest.fixture(autouse=True)
    def _set_up_monitor(self, mock_lock: mock.Mock, mocker: MockerFixture) -> None:
        # pylint: disable=attribute-defined-outside-init
        self.monitor = AccountMonitor(AccountConfig(), mock_lock)
        mocker.patch(
            "lib.reservation_monitor.get_current_time", return_value=datetime(1999, 12, 31)
        )

    def test_monitor_monitors_the_account_continuously(self, mocker: MockerFixture) -> None:
        # Since the monitor function runs in an infinite loop, throw an Exception
        # when the sleep function is called a second time to break out of the loop.
        mocker.patch.object(AccountMonitor, "_smart_sleep", side_effect=["", StopIteration])
        mock_get_reservations = mocker.patch.object(
            AccountMonitor, "_get_reservations", return_value=([], False)
        )
        mock_schedule_reservations = mocker.patch.object(AccountMonitor, "_schedule_reservations")
        mock_check_flight_fares = mocker.patch.object(AccountMonitor, "_check_flight_fares")

        with pytest.raises(StopIteration):
            self.monitor._monitor()

        assert mock_get_reservations.call_count == 2
        assert mock_schedule_reservations.call_count == 2
        assert mock_check_flight_fares.call_count == 2

    def test_monitor_skips_scheduling_on_too_many_requests_error(
        self, mocker: MockerFixture
    ) -> None:
        # Since the monitor function runs in an infinite loop, throw an Exception
        # when the sleep function is called a second time to break out of the loop.
        mocker.patch.object(AccountMonitor, "_smart_sleep", side_effect=[StopIteration])
        mock_get_reservations = mocker.patch.object(
            AccountMonitor, "_get_reservations", return_value=([], True)
        )
        mock_schedule_reservations = mocker.patch.object(AccountMonitor, "_schedule_reservations")
        mock_check_flight_fares = mocker.patch.object(AccountMonitor, "_check_flight_fares")

        with pytest.raises(StopIteration):
            self.monitor._monitor()

        assert mock_get_reservations.call_count == 1
        assert mock_schedule_reservations.call_count == 0
        assert mock_check_flight_fares.call_count == 0

    def test_monitor_checks_reservations_once_if_retrieval_interval_is_zero(
        self,
        mocker: MockerFixture,
    ) -> None:
        mock_smart_sleep = mocker.patch.object(AccountMonitor, "_smart_sleep")
        mock_get_reservations = mocker.patch.object(
            AccountMonitor, "_get_reservations", return_value=([], False)
        )
        mock_schedule_reservations = mocker.patch.object(AccountMonitor, "_schedule_reservations")
        mock_check_flight_fares = mocker.patch.object(AccountMonitor, "_check_flight_fares")

        self.monitor.config.retrieval_interval = 0
        self.monitor._monitor()

        mock_smart_sleep.assert_not_called()
        mock_get_reservations.assert_called_once()
        mock_schedule_reservations.assert_called_once()
        mock_check_flight_fares.assert_called_once()

    def test_get_reservations_skips_retrieval_on_too_many_requests_error(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(
            WebDriver, "get_reservations", side_effect=LoginError("", TOO_MANY_REQUESTS_CODE)
        )
        reservations, skip_scheduling = self.monitor._get_reservations()
        assert len(reservations) == 0
        assert skip_scheduling

    def test_get_reservations_exits_on_login_error(self, mocker: MockerFixture) -> None:
        mocker.patch.object(WebDriver, "get_reservations", side_effect=LoginError("", 400))
        mock_failed_login = mocker.patch.object(NotificationHandler, "failed_login")

        with pytest.raises(SystemExit):
            self.monitor._get_reservations()

        mock_failed_login.assert_called_once()

    def test_get_reservations_returns_the_correct_reservations(self, mocker: MockerFixture) -> None:
        reservations = [{"reservation1": "test1"}, {"reservation2": "test2"}]
        mocker.patch.object(WebDriver, "get_reservations", return_value=reservations)

        new_reservations, skip_scheduling = self.monitor._get_reservations()

        assert new_reservations == reservations
        assert not skip_scheduling

    def test_stop_monitoring_stops_checkins(self, mocker: MockerFixture) -> None:
        mock_stop_checkins = mocker.patch.object(AccountMonitor, "_stop_checkins")
        self.monitor._stop_monitoring()
        mock_stop_checkins.assert_called_once()
