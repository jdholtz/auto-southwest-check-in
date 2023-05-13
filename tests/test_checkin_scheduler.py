from datetime import datetime
from typing import Any, Dict
from unittest import mock

import pytest
from pytest_mock import MockerFixture

from lib.checkin_handler import CheckInHandler
from lib.checkin_scheduler import CheckInScheduler
from lib.config import Config
from lib.flight import Flight
from lib.flight_retriever import FlightRetriever
from lib.notification_handler import NotificationHandler
from lib.utils import RequestError
from lib.webdriver import WebDriver

# This needs to be accessed to be tested
# pylint: disable=protected-access


# Don't read the config file
@pytest.fixture(autouse=True)
def mock_config(mocker: MockerFixture) -> None:
    mocker.patch.object(Config, "_read_config")


@pytest.fixture
def test_flight(mocker: MockerFixture) -> Flight:
    mocker.patch.object(Flight, "_get_flight_time")
    flight_info = {
        "departureAirport": {"name": None},
        "arrivalAirport": {"name": None},
        "departureTime": None,
        "arrivalTime": None,
    }
    return Flight(flight_info, "")


def test_schedule_refreshes_headers_when_empty(mocker: MockerFixture) -> None:
    mock_refresh_headers = mocker.patch.object(CheckInScheduler, "refresh_headers")
    mock_schedule_flights = mocker.patch.object(CheckInScheduler, "_schedule_flights")
    mock_new_flight_notifications = mocker.patch.object(NotificationHandler, "new_flights")

    checkin_scheduler = CheckInScheduler(FlightRetriever(Config()))
    checkin_scheduler.schedule([])

    mock_refresh_headers.assert_called_once()
    mock_schedule_flights.assert_not_called()
    mock_new_flight_notifications.assert_called_once()


def test_schedule_does_not_refresh_headers_when_populated(mocker: MockerFixture) -> None:
    mock_refresh_headers = mocker.patch.object(CheckInScheduler, "refresh_headers")
    mock_schedule_flights = mocker.patch.object(CheckInScheduler, "_schedule_flights")
    mock_new_flight_notifications = mocker.patch.object(NotificationHandler, "new_flights")

    checkin_scheduler = CheckInScheduler(FlightRetriever(Config()))
    checkin_scheduler.headers = {"test": "headers"}
    checkin_scheduler.schedule([])

    mock_refresh_headers.assert_not_called()
    mock_schedule_flights.assert_not_called()
    mock_new_flight_notifications.assert_called_once()


def test_schedule_schedules_all_reservations(mocker: MockerFixture) -> None:
    mocker.patch.object(CheckInScheduler, "refresh_headers")
    mock_schedule_flights = mocker.patch.object(CheckInScheduler, "_schedule_flights")
    mock_new_flight_notifications = mocker.patch.object(NotificationHandler, "new_flights")

    checkin_scheduler = CheckInScheduler(FlightRetriever(Config()))
    checkin_scheduler.schedule(["test1", "test2"])

    mock_schedule_flights.assert_has_calls([mock.call("test1"), mock.call("test2")])
    mock_new_flight_notifications.assert_called_once()


def test_refresh_headers_sets_new_headers(mocker: MockerFixture) -> None:
    mock_webdriver_set_headers = mocker.patch.object(WebDriver, "set_headers")

    checkin_scheduler = CheckInScheduler(FlightRetriever(Config()))
    checkin_scheduler.refresh_headers()
    mock_webdriver_set_headers.assert_called_once()


@pytest.mark.parametrize(
    ["flight_time", "expected_len"],
    [
        (datetime(2000, 1, 1), 1),
        (datetime(1999, 12, 30), 0),
    ],
)
def test_remove_departed_flights_removes_only_departed_flights(
    mocker: MockerFixture, test_flight: Flight, flight_time: datetime, expected_len: int
) -> None:
    mock_datetime = mocker.patch("lib.checkin_scheduler.datetime")
    mock_datetime.utcnow.return_value = datetime(1999, 12, 31)

    checkin_scheduler = CheckInScheduler(FlightRetriever(Config()))
    test_flight.departure_time = flight_time
    checkin_scheduler.flights.append(test_flight)

    checkin_scheduler.remove_departed_flights()

    assert len(checkin_scheduler.flights) == expected_len


def test_schedule_flights_schedules_all_flights_under_reservation(
    mocker: MockerFixture,
) -> None:
    reservation_info = [{"departureStatus": "WAITING"}, {"departureStatus": "WAITING"}]
    mocker.patch.object(CheckInScheduler, "_get_reservation_info", return_value=reservation_info)

    mocker.patch.object(CheckInScheduler, "_flight_is_scheduled", return_value=False)
    mocker.patch("lib.checkin_scheduler.Flight")
    mock_schedule_check_in = mocker.patch.object(CheckInHandler, "schedule_check_in")

    checkin_scheduler = CheckInScheduler(FlightRetriever(Config()))
    checkin_scheduler._schedule_flights("flight1")

    assert len(checkin_scheduler.flights) == 2
    assert mock_schedule_check_in.call_count == 2


def test_schedule_flights_does_not_schedule_already_scheduled_flights(
    mocker: MockerFixture,
) -> None:
    reservation_info = [{"departureStatus": "WAITING"}]
    mocker.patch.object(CheckInScheduler, "_get_reservation_info", return_value=reservation_info)

    mocker.patch.object(CheckInScheduler, "_flight_is_scheduled", return_value=True)
    mocker.patch("lib.checkin_scheduler.Flight")

    checkin_scheduler = CheckInScheduler(FlightRetriever(Config()))
    checkin_scheduler._schedule_flights("flight1")

    assert len(checkin_scheduler.flights) == 0


def test_schedule_flights_does_not_schedule_departed_flights(mocker: MockerFixture) -> None:
    reservation_info = [{"departureStatus": "DEPARTED"}]
    mocker.patch.object(CheckInScheduler, "_get_reservation_info", return_value=reservation_info)
    mocker.patch("lib.checkin_scheduler.Flight")

    checkin_scheduler = CheckInScheduler(FlightRetriever(Config()))
    checkin_scheduler._schedule_flights("flight1")

    assert len(checkin_scheduler.flights) == 0


def test_get_reservation_info_returns_reservation_info(mocker: MockerFixture) -> None:
    reservation_info = {"viewReservationViewPage": {"bounds": [{"test": "reservation"}]}}
    mocker.patch("lib.checkin_scheduler.make_request", return_value=reservation_info)

    checkin_scheduler = CheckInScheduler(FlightRetriever(Config()))
    reservation_info = checkin_scheduler._get_reservation_info("flight1")

    assert reservation_info == [{"test": "reservation"}]


def test_get_reservation_info_sends_error_notification_when_reservation_retrieval_fails(
    mocker: MockerFixture,
) -> None:
    mocker.patch("lib.checkin_scheduler.make_request", side_effect=RequestError())
    mock_failed_reservation_retrieval = mocker.patch.object(
        NotificationHandler, "failed_reservation_retrieval"
    )

    checkin_scheduler = CheckInScheduler(FlightRetriever(Config()))
    reservation_info = checkin_scheduler._get_reservation_info("flight1")

    mock_failed_reservation_retrieval.assert_called_once()
    assert reservation_info == []


def test_flight_is_scheduled_returns_true_if_flight_is_already_scheduled(
    test_flight: Flight,
) -> None:
    checkin_scheduler = CheckInScheduler(FlightRetriever(Config()))

    test_flight.departure_time = datetime(1999, 12, 31)
    test_flight.departure_airport = "test_departure"
    test_flight.destination_airport = "test_destination"
    checkin_scheduler.flights.append(test_flight)

    assert checkin_scheduler._flight_is_scheduled(test_flight) is True


@pytest.mark.parametrize(
    ["flight_info", "flight_time"],
    [
        (
            {
                "departureAirport": {"name": None},
                "arrivalAirport": {"name": None},
                "departureTime": None,
                "arrivalTime": None,
            },
            datetime(1999, 12, 30),
        ),
        (
            {
                "departureAirport": {"name": "test"},
                "arrivalAirport": {"name": None},
                "departureTime": None,
                "arrivalTime": None,
            },
            datetime(1999, 12, 31),
        ),
        (
            {
                "departureAirport": {"name": None},
                "arrivalAirport": {"name": "test"},
                "departureTime": None,
                "arrivalTime": None,
            },
            datetime(1999, 12, 31),
        ),
    ],
)
def test_flight_is_scheduled_returns_false_if_flight_is_not_scheduled(
    test_flight: Flight,
    flight_info: Dict[str, Any],
    flight_time: datetime,
) -> None:
    checkin_scheduler = CheckInScheduler(FlightRetriever(Config()))

    test_flight.departure_time = datetime(1999, 12, 31)
    checkin_scheduler.flights.append(test_flight)

    new_flight = Flight(flight_info, "")
    new_flight.departure_time = flight_time

    assert checkin_scheduler._flight_is_scheduled(new_flight) is False
