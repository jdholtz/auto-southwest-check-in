"""
Runs the fare checker through various scenarios that could happen while checking a flight's fare
"""

import copy
from typing import List
from unittest import mock

import pytest
from requests_mock.mocker import Mocker as RequestMocker

from lib.checkin_scheduler import VIEW_RESERVATION_URL
from lib.config import GlobalConfig
from lib.fare_checker import BOOKING_URL, FareChecker
from lib.flight import Flight
from lib.reservation_monitor import ReservationMonitor
from lib.utils import BASE_URL, FlightChangeError

TEST_RESERVATION_URL = BASE_URL + VIEW_RESERVATION_URL + "TEST"
CHAGE_FLIGHT_URL = BASE_URL + BOOKING_URL + "change_page"
MATCHING_FLIGHTS_URL = BASE_URL + BOOKING_URL + "matching_flights"

RESERVATION_INFO = {
    "viewReservationViewPage": {
        "bounds": [{"fareProductDetails": {"fareProductId": "WGA"}}],
        "_links": {"change": {"href": "change_page", "query": "test_query"}},
        "greyBoxMessage": None,
    }
}

CHANGE_FLIGHT_PAGE = {
    "changeFlightPage": {
        "_links": {
            "changeShopping": {
                "body": [{"boundReference": "reference"}],
                "href": "matching_flights",
            }
        },
        "boundSelections": [
            {
                "originalDate": "2021-12-06",
                "toAirportCode": "SYD",
                "fromAirportCode": "LAX",
                "flight": "100\u200b/\u200b101",
            }
        ],
    }
}

FLIGHT_CARDS = [
    {
        "departureTime": "14:40",  # Here to make sure it doesn't select based off time
        "flightNumbers": "97",
        "fares": [
            {
                "_meta": {"fareProductId": "WGA"},
                "priceDifference": {"sign": "-", "amount": "4,300", "currencyCode": "PTS"},
            }
        ],
    },
    {"flightNumbers": "98\u200b/\u200b99"},
    {
        "flightNumbers": "100\u200b/\u200b101",
        "fares": [
            {"_meta": {"fareProductId": "TEST"}},
            {
                "_meta": {"fareProductId": "WGA"},
                "priceDifference": {"sign": "-", "amount": "4,300", "currencyCode": "PTS"},
            },
        ],
    },
]

MATCHING_FLIGHTS = {"changeShoppingPage": {"flights": {"outboundPage": {"cards": FLIGHT_CARDS}}}}


@pytest.fixture
def monitor() -> ReservationMonitor:
    config = GlobalConfig()
    config.create_reservation_config(
        [{"confirmationNumber": "TEST", "firstName": "Berkant", "lastName": "Marika"}]
    )
    monitor = ReservationMonitor(config.reservations[0])
    monitor.notification_handler.lower_fare = mock.Mock()
    return monitor


@pytest.fixture
def flight() -> Flight:
    flight_info = {
        "arrivalAirport": {"name": "test_inbound", "country": None},
        "departureAirport": {"code": "LAX", "name": "test_outbound"},
        "departureDate": "2021-12-06",
        "departureTime": "14:40",
        "flights": [{"number": "100"}, {"number": "101"}],
    }
    return Flight(flight_info, "TEST")


def test_fare_drop_outbound(
    requests_mock: RequestMocker, monitor: ReservationMonitor, flight: Flight
) -> None:
    requests_mock.get(TEST_RESERVATION_URL, [{"json": RESERVATION_INFO, "status_code": 200}])
    requests_mock.get(CHAGE_FLIGHT_URL, [{"json": CHANGE_FLIGHT_PAGE, "status_code": 200}])
    requests_mock.post(MATCHING_FLIGHTS_URL, [{"json": MATCHING_FLIGHTS, "status_code": 200}])

    fare_checker = FareChecker(monitor)
    fare_checker.check_flight_price(flight)

    monitor.notification_handler.lower_fare.assert_called_once_with(flight, "-4300 PTS")


def test_fare_drop_inbound(
    requests_mock: RequestMocker, monitor: ReservationMonitor, flight: Flight
) -> None:
    flight.flight_number = "97"

    bounds = [
        {"fareProductDetails": {"fareProductId": "TEST"}},
        {"fareProductDetails": {"fareProductId": "WGA"}},
    ]
    reservation_info = copy.deepcopy(RESERVATION_INFO)
    reservation_info["viewReservationViewPage"]["bounds"] = bounds

    flight_page = copy.deepcopy(CHANGE_FLIGHT_PAGE)
    page_info = flight_page["changeFlightPage"]
    page_info["_links"]["changeShopping"]["body"].append({"boundReference": "reference"})

    bound_selection = {
        "originalDate": "2021-12-12",
        "toAirportCode": "LAX",
        "fromAirportCode": "SYD",
        "flight": "97",
    }
    page_info["boundSelections"].append(bound_selection)

    matching_flights = copy.deepcopy(MATCHING_FLIGHTS)
    matching_flights["changeShoppingPage"]["flights"] = {"inboundPage": {"cards": FLIGHT_CARDS}}

    requests_mock.get(TEST_RESERVATION_URL, [{"json": reservation_info, "status_code": 200}])
    requests_mock.get(CHAGE_FLIGHT_URL, [{"json": flight_page, "status_code": 200}])
    requests_mock.post(MATCHING_FLIGHTS_URL, [{"json": matching_flights, "status_code": 200}])

    fare_checker = FareChecker(monitor)
    fare_checker.check_flight_price(flight)

    monitor.notification_handler.lower_fare.assert_called_once_with(flight, "-4300 PTS")


@pytest.mark.parametrize(["amount", "sign"], [("1,000", "+"), ("1", "-"), ("0", None)])
def test_no_fare_drop(
    requests_mock: RequestMocker,
    monitor: ReservationMonitor,
    flight: Flight,
    amount: str,
    sign: str,
) -> None:
    flights = copy.deepcopy(FLIGHT_CARDS)
    fare = flights[2]["fares"][1]["priceDifference"]
    fare["amount"] = amount
    fare["sign"] = sign

    matching_flights = copy.deepcopy(MATCHING_FLIGHTS)
    matching_flights["changeShoppingPage"]["flights"]["outboundPage"]["cards"] = flights

    requests_mock.get(TEST_RESERVATION_URL, [{"json": RESERVATION_INFO, "status_code": 200}])
    requests_mock.get(CHAGE_FLIGHT_URL, [{"json": CHANGE_FLIGHT_PAGE, "status_code": 200}])
    requests_mock.post(MATCHING_FLIGHTS_URL, [{"json": matching_flights, "status_code": 200}])

    fare_checker = FareChecker(monitor)
    fare_checker.check_flight_price(flight)

    monitor.notification_handler.lower_fare.assert_not_called()


def test_flight_error_with_companion(
    requests_mock: RequestMocker, monitor: ReservationMonitor, flight: Flight
) -> None:
    reservation_info = copy.deepcopy(RESERVATION_INFO)
    message = {"body": "You must first cancel the associated companion reservation."}
    reservation_info["viewReservationViewPage"]["greyBoxMessage"] = message

    requests_mock.get(TEST_RESERVATION_URL, [{"json": reservation_info, "status_code": 200}])

    fare_checker = FareChecker(monitor)
    with pytest.raises(FlightChangeError):
        fare_checker.check_flight_price(flight)


def test_flight_error_when_no_change_link_exists(
    requests_mock: RequestMocker, monitor: ReservationMonitor, flight: Flight
) -> None:
    reservation_info = copy.deepcopy(RESERVATION_INFO)
    reservation_info["viewReservationViewPage"]["_links"]["change"] = None

    requests_mock.get(TEST_RESERVATION_URL, [{"json": reservation_info, "status_code": 200}])

    fare_checker = FareChecker(monitor)
    with pytest.raises(FlightChangeError):
        fare_checker.check_flight_price(flight)


@pytest.mark.parametrize(
    "fare", [None, [{"_meta": {"fareProductId": "TEST"}}], [{"_meta": {"fareProductId": "WGA"}}]]
)
def test_unavailable_fares(
    requests_mock: RequestMocker, monitor: ReservationMonitor, flight: Flight, fare: List
) -> None:
    flights = copy.deepcopy(FLIGHT_CARDS)
    flights[2]["fares"] = fare

    matching_flights = copy.deepcopy(MATCHING_FLIGHTS)
    matching_flights["changeShoppingPage"]["flights"]["outboundPage"]["cards"] = flights

    requests_mock.get(TEST_RESERVATION_URL, [{"json": RESERVATION_INFO, "status_code": 200}])
    requests_mock.get(CHAGE_FLIGHT_URL, [{"json": CHANGE_FLIGHT_PAGE, "status_code": 200}])
    requests_mock.post(MATCHING_FLIGHTS_URL, [{"json": matching_flights, "status_code": 200}])

    fare_checker = FareChecker(monitor)
    fare_checker.check_flight_price(flight)

    monitor.notification_handler.lower_fare.assert_not_called()
