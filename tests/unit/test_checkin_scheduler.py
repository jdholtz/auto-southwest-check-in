import json
from datetime import UTC as datetime_utc
from datetime import datetime, timedelta
from typing import List
from unittest import mock

import pytest
from pytest_mock import MockerFixture

from lib.checkin_handler import CheckInHandler
from lib.checkin_scheduler import FLIGHT_IN_PAST_CODE, CheckInScheduler
from lib.config import ReservationConfig
from lib.flight import Flight
from lib.notification_handler import NotificationHandler
from lib.reservation_monitor import ReservationMonitor
from lib.utils import RequestError
from lib.webdriver import WebDriver

# This needs to be accessed to be tested
# pylint: disable=protected-access


@pytest.fixture
def test_flights(mocker: MockerFixture) -> List[Flight]:
    mocker.patch.object(Flight, "_set_flight_time")
    flight_info = {
        "departureAirport": {"name": None},
        "arrivalAirport": {"name": None, "country": None},
        "departureTime": None,
        "flights": [{"number": "100"}],
    }
    return [Flight(flight_info, ""), Flight(flight_info, "")]


class TestCheckInScheduler:
    @pytest.fixture(autouse=True)
    def _set_up_scheduler(self) -> None:
        # pylint: disable=attribute-defined-outside-init
        self.scheduler = CheckInScheduler(ReservationMonitor(ReservationConfig()))

    def test_process_reservations_handles_all_reservations(self, mocker: MockerFixture) -> None:
        mock_get_flights = mocker.patch.object(
            CheckInScheduler, "_get_flights", return_value=["flight"]
        )
        mock_get_new_flights = mocker.patch.object(
            CheckInScheduler, "_get_new_flights", return_value=["flight"]
        )
        mock_schedule_flights = mocker.patch.object(CheckInScheduler, "_schedule_flights")
        mock_remove_old_flights = mocker.patch.object(CheckInScheduler, "_remove_old_flights")

        self.scheduler.process_reservations(["test1", "test2"])

        mock_get_flights.assert_has_calls([mock.call("test1"), mock.call("test2")])
        mock_get_new_flights.assert_called_once_with(["flight", "flight"])
        mock_schedule_flights.assert_called_once_with(["flight"])
        mock_remove_old_flights.assert_called_once_with(["flight", "flight"])

    def test_refresh_headers_sets_new_headers(self, mocker: MockerFixture) -> None:
        mock_webdriver_set_headers = mocker.patch.object(WebDriver, "set_headers")

        self.scheduler.refresh_headers()
        mock_webdriver_set_headers.assert_called_once()

    def test_get_flights_retrieves_all_flights_under_reservation(
        self, mocker: MockerFixture, test_flights: List[Flight]
    ) -> None:
        mocker.patch.object(CheckInScheduler, "_get_reservation_info", return_value=[{}, {}])
        mock_set_same_day_flight = mocker.patch.object(CheckInScheduler, "_set_same_day_flight")

        # Set the departing times to be after the current time
        test_flights[0].departure_time = datetime(1999, 12, 30, 18, 29)
        test_flights[1].departure_time = datetime(1999, 12, 31, 20, 29)
        mocker.patch("lib.checkin_scheduler.Flight", side_effect=test_flights)

        current_time = datetime(1999, 12, 30, 18, 20)
        mocker.patch("lib.checkin_scheduler.get_current_time", return_value=current_time)

        flights = self.scheduler._get_flights("flight1")
        assert len(flights) == 2
        assert mock_set_same_day_flight.call_count == len(flights)

    def test_get_flights_does_not_retrieve_departed_flights(
        self, mocker: MockerFixture, test_flights: List[Flight]
    ) -> None:
        mocker.patch.object(CheckInScheduler, "_get_reservation_info", return_value=[{}, {}])

        # Set the departing time to be before the current time. Only uses the first flight
        test_flights[0].departure_time = datetime(1999, 12, 30, 18, 29)
        mocker.patch("lib.checkin_scheduler.Flight", return_value=test_flights[0])

        current_time = datetime(1999, 12, 30, 19, 29)
        mocker.patch("lib.checkin_scheduler.get_current_time", return_value=current_time)

        flights = self.scheduler._get_flights("flight1")
        assert len(flights) == 0

    def test_get_reservation_info_returns_reservation_info(self, mocker: MockerFixture) -> None:
        reservation_info = {"viewReservationViewPage": {"bounds": [{"test": "reservation"}]}}
        mocker.patch("lib.checkin_scheduler.make_request", return_value=reservation_info)

        reservation_info = self.scheduler._get_reservation_info("flight1")
        assert reservation_info == [{"test": "reservation"}]

    # A reservation has flights in the past and this is the first time attempting to
    # schedule it
    def test_get_reservation_info_sends_error_notification_when_reservation_not_found(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch(
            "lib.checkin_scheduler.make_request",
            side_effect=RequestError("", json.dumps({"code": FLIGHT_IN_PAST_CODE})),
        )
        mock_failed_reservation_retrieval = mocker.patch.object(
            NotificationHandler, "failed_reservation_retrieval"
        )

        self.scheduler.flights = []
        reservation_info = self.scheduler._get_reservation_info("flight1")

        mock_failed_reservation_retrieval.assert_called_once()
        assert reservation_info == []

    # A reservation is already scheduled but fails for a retrieval resulting in another error than
    # all flights being old
    def test_get_reservation_info_sends_error_when_reservation_retrieval_fails_and_flight_scheduled(
        self, mocker: MockerFixture, test_flights: List[Flight]
    ) -> None:
        mocker.patch("lib.checkin_scheduler.make_request", side_effect=RequestError("", ""))
        mock_failed_reservation_retrieval = mocker.patch.object(
            NotificationHandler, "failed_reservation_retrieval"
        )

        self.scheduler.flights = test_flights
        reservation_info = self.scheduler._get_reservation_info("flight1")

        mock_failed_reservation_retrieval.assert_called_once()
        assert reservation_info == []

    # A reservation is already scheduled and the flights are in the past
    def test_get_reservation_info_does_not_send_error_notification_when_reservation_is_old(
        self, mocker: MockerFixture, test_flights: List[Flight]
    ) -> None:
        mocker.patch(
            "lib.checkin_scheduler.make_request",
            side_effect=RequestError("", json.dumps({"code": FLIGHT_IN_PAST_CODE})),
        )
        mock_failed_reservation_retrieval = mocker.patch.object(
            NotificationHandler, "failed_reservation_retrieval"
        )

        self.scheduler.flights = test_flights
        reservation_info = self.scheduler._get_reservation_info("flight1")

        mock_failed_reservation_retrieval.assert_not_called()
        assert reservation_info == []

    @pytest.mark.parametrize(["hour_diff", "same_day"], [(23, True), (24, True), (25, False)])
    def test_set_same_day_flight_sets_flight_as_same_day_correctly(
        self, hour_diff: int, same_day: bool, test_flights: List[Flight]
    ) -> None:
        prev_flight, new_flight = test_flights
        prev_flight.departure_time = datetime.now(datetime_utc)
        new_flight.departure_time = prev_flight.departure_time + timedelta(hours=hour_diff)

        self.scheduler._set_same_day_flight(new_flight, [prev_flight])

        assert new_flight.is_same_day == same_day

    def test_get_new_flights_gets_flights_not_already_scheduled(
        self, test_flights: List[Flight]
    ) -> None:
        flight1 = test_flights[0]
        flight2 = test_flights[1]
        # Change the flight number so it is seen as a new flight
        flight2.flight_number = "101"

        self.scheduler.flights = [flight1]
        new_flights = self.scheduler._get_new_flights([flight1, flight2])

        assert new_flights == [flight2]

    def test_schedule_flights_schedules_all_flights(
        self, mocker: MockerFixture, test_flights: List[Flight]
    ) -> None:
        mock_schedule_check_in = mocker.patch.object(CheckInHandler, "schedule_check_in")
        mock_new_flights_notification = mocker.patch.object(NotificationHandler, "new_flights")

        self.scheduler._schedule_flights(test_flights)

        assert len(self.scheduler.flights) == 2
        assert len(self.scheduler.checkin_handlers) == 2
        assert mock_schedule_check_in.call_count == 2
        mock_new_flights_notification.assert_called_once_with(test_flights)

    def test_remove_old_flights_removes_flights_not_currently_scheduled(
        self, mocker: MockerFixture, test_flights: List[Flight]
    ) -> None:
        test_flights[0].flight_number = "101"
        mock_stop_check_in = mocker.patch.object(CheckInHandler, "stop_check_in")
        self.scheduler.flights = test_flights
        self.scheduler.checkin_handlers = [
            CheckInHandler(self.scheduler, test_flights[0], None),
            CheckInHandler(self.scheduler, test_flights[1], None),
        ]

        self.scheduler._remove_old_flights([test_flights[1]])

        assert len(self.scheduler.flights) == 1
        assert len(self.scheduler.checkin_handlers) == 1
        mock_stop_check_in.assert_called_once()
