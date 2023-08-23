import json
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
    mocker.patch.object(Flight, "_get_flight_time")
    flight_info = {
        "departureAirport": {"name": None},
        "arrivalAirport": {"name": None},
        "departureTime": None,
        "arrivalTime": None,
    }
    return [Flight(flight_info, ""), Flight(flight_info, "")]


def test_process_reservations_handles_all_reservations(mocker: MockerFixture) -> None:
    mock_get_flights = mocker.patch.object(
        CheckInScheduler, "_get_flights", return_value=["flight"]
    )
    mock_get_new_flights = mocker.patch.object(
        CheckInScheduler, "_get_new_flights", return_value=["flight"]
    )
    mock_schedule_flights = mocker.patch.object(CheckInScheduler, "_schedule_flights")
    mock_remove_old_flights = mocker.patch.object(CheckInScheduler, "_remove_old_flights")

    checkin_scheduler = CheckInScheduler(ReservationMonitor(ReservationConfig()))
    checkin_scheduler.process_reservations(["test1", "test2"])

    mock_get_flights.assert_has_calls([mock.call("test1"), mock.call("test2")])
    mock_get_new_flights.assert_called_once_with(["flight", "flight"])
    mock_schedule_flights.assert_called_once_with(["flight"])
    mock_remove_old_flights.assert_called_once_with(["flight", "flight"])


def test_refresh_headers_sets_new_headers(mocker: MockerFixture) -> None:
    mock_webdriver_set_headers = mocker.patch.object(WebDriver, "set_headers")

    checkin_scheduler = CheckInScheduler(ReservationMonitor(ReservationConfig()))
    checkin_scheduler.refresh_headers()
    mock_webdriver_set_headers.assert_called_once()


def test_get_flights_retrieves_all_flights_under_reservation(
    mocker: MockerFixture,
) -> None:
    reservation_info = [{"departureStatus": "WAITING"}, {"departureStatus": "WAITING"}]
    mocker.patch.object(CheckInScheduler, "_get_reservation_info", return_value=reservation_info)

    mocker.patch("lib.checkin_scheduler.Flight")
    checkin_scheduler = CheckInScheduler(ReservationMonitor(ReservationConfig()))
    flights = checkin_scheduler._get_flights("flight1")

    assert len(flights) == 2


def test_get_flights_does_not_retrieve_departed_flights(mocker: MockerFixture) -> None:
    reservation_info = [{"departureStatus": "DEPARTED"}]
    mocker.patch.object(CheckInScheduler, "_get_reservation_info", return_value=reservation_info)

    checkin_scheduler = CheckInScheduler(ReservationMonitor(ReservationConfig()))
    flights = checkin_scheduler._get_flights("flight1")

    assert len(flights) == 0


def test_get_reservation_info_returns_reservation_info(mocker: MockerFixture) -> None:
    reservation_info = {"viewReservationViewPage": {"bounds": [{"test": "reservation"}]}}
    mocker.patch("lib.checkin_scheduler.make_request", return_value=reservation_info)

    checkin_scheduler = CheckInScheduler(ReservationMonitor(ReservationConfig()))
    reservation_info = checkin_scheduler._get_reservation_info("flight1")

    assert reservation_info == [{"test": "reservation"}]


# A reservation has flights in the past and this is the first time attempting to
# schedule it
def test_get_reservation_info_sends_error_notification_when_reservation_not_found(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "lib.checkin_scheduler.make_request",
        side_effect=RequestError("", json.dumps({"code": FLIGHT_IN_PAST_CODE})),
    )
    mock_failed_reservation_retrieval = mocker.patch.object(
        NotificationHandler, "failed_reservation_retrieval"
    )

    checkin_scheduler = CheckInScheduler(ReservationMonitor(ReservationConfig()))
    checkin_scheduler.flights = []
    reservation_info = checkin_scheduler._get_reservation_info("flight1")

    mock_failed_reservation_retrieval.assert_called_once()
    assert reservation_info == []


# A reservation is already scheduled but fails for a retrieval resulting in another error than
# all flights being old
def test_get_reservation_info_sends_error_when_reservation_retrieval_fails_and_flights_scheduled(
    mocker: MockerFixture, test_flights: List[Flight]
) -> None:
    mocker.patch("lib.checkin_scheduler.make_request", side_effect=RequestError("", ""))
    mock_failed_reservation_retrieval = mocker.patch.object(
        NotificationHandler, "failed_reservation_retrieval"
    )

    checkin_scheduler = CheckInScheduler(ReservationMonitor(ReservationConfig()))
    checkin_scheduler.flights = test_flights
    reservation_info = checkin_scheduler._get_reservation_info("flight1")

    mock_failed_reservation_retrieval.assert_called_once()
    assert reservation_info == []


# A reservation is already scheduled and the flights are in the past
def test_get_reservation_info_does_not_send_error_notification_when_reservation_is_old(
    mocker: MockerFixture, test_flights: List[Flight]
) -> None:
    mocker.patch(
        "lib.checkin_scheduler.make_request",
        side_effect=RequestError("", json.dumps({"code": FLIGHT_IN_PAST_CODE})),
    )
    mock_failed_reservation_retrieval = mocker.patch.object(
        NotificationHandler, "failed_reservation_retrieval"
    )

    checkin_scheduler = CheckInScheduler(ReservationMonitor(ReservationConfig()))
    checkin_scheduler.flights = test_flights
    reservation_info = checkin_scheduler._get_reservation_info("flight1")

    mock_failed_reservation_retrieval.assert_not_called()
    assert reservation_info == []


def test_get_new_flights_gets_flights_not_already_scheduled(
    mocker: MockerFixture, test_flights: List[Flight]
) -> None:
    flight1 = test_flights[0]
    flight2 = test_flights[1]
    # Change the airport so it is seen as a new flight
    flight2.departure_airport = "LAX"

    checkin_scheduler = CheckInScheduler(ReservationMonitor(ReservationConfig()))
    checkin_scheduler.flights = [flight1]

    new_flights = checkin_scheduler._get_new_flights([flight1, flight2])

    assert new_flights == [flight2]


def test_schedule_flights_schedules_all_flights(
    mocker: MockerFixture, test_flights: List[Flight]
) -> None:
    mock_schedule_check_in = mocker.patch.object(CheckInHandler, "schedule_check_in")
    mock_new_flights_notification = mocker.patch.object(NotificationHandler, "new_flights")

    checkin_scheduler = CheckInScheduler(ReservationMonitor(ReservationConfig()))
    checkin_scheduler._schedule_flights(test_flights)

    assert len(checkin_scheduler.flights) == 2
    assert len(checkin_scheduler.checkin_handlers) == 2
    assert mock_schedule_check_in.call_count == 2
    mock_new_flights_notification.assert_called_once_with(test_flights)


def test_remove_old_flights_removes_flights_not_currently_scheduled(
    mocker: MockerFixture, test_flights: List[Flight]
) -> None:
    test_flights[0].departure_airport = "LAX"
    mock_stop_check_in = mocker.patch.object(CheckInHandler, "stop_check_in")
    checkin_scheduler = CheckInScheduler(ReservationMonitor(ReservationConfig()))
    checkin_scheduler.flights = test_flights
    checkin_scheduler.checkin_handlers = [
        CheckInHandler(checkin_scheduler, test_flights[0], None),
        CheckInHandler(checkin_scheduler, test_flights[1], None),
    ]

    checkin_scheduler._remove_old_flights([test_flights[1]])

    assert len(checkin_scheduler.flights) == 1
    assert len(checkin_scheduler.checkin_handlers) == 1
    mock_stop_check_in.assert_called_once()
