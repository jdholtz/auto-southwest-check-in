"""
Runs the fare checker through various scenarios that could happen while checking a flight's fare
"""

import copy
from unittest import mock

import pytest
from pytest_mock import MockerFixture
from requests_mock.mocker import Mocker as RequestMocker

from lib.config import GlobalConfig
from lib.fare_checker import BOOKING_URL, FareChecker
from lib.flight import Flight
from lib.reservation_monitor import ReservationMonitor
from lib.utils import BASE_URL, CheckFaresOption, FlightChangeError
from lib.webdriver import WebDriver

CHANGE_FLIGHT_URL = BASE_URL + BOOKING_URL + "change_page"
MATCHING_FLIGHTS_URL = BASE_URL + BOOKING_URL + "matching_flights"
CANCEL_BOUND_URL = BASE_URL + BOOKING_URL + "cancel_bound"
REFUND_QUOTE_URL = BASE_URL + BOOKING_URL + "refund_quote"

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
        "stopDescription": "Nonstop",
    },
    {
        "flightNumbers": "98\u200b/\u200b99",
        "fares": [
            {
                "_meta": {"fareProductId": "WGA"},
                "priceDifference": {"sign": "-", "amount": "5,200", "currencyCode": "PTS"},
            }
        ],
        "stopDescription": "1 Stop, LAX",
    },
    {
        "flightNumbers": "100\u200b/\u200b101",
        "fares": [
            {"_meta": {"fareProductId": "TEST"}},
            {
                "_meta": {"fareProductId": "WGA"},
                "priceDifference": {"sign": "-", "amount": "3,600", "currencyCode": "PTS"},
            },
        ],
        "stopDescription": "1 Stop, NYC",
    },
    {
        "flightNumbers": "102",
        "fares": [
            {
                "_meta": {"fareProductId": "WGA"},
                "priceDifference": {"sign": "-", "amount": "4,800", "currencyCode": "PTS"},
            }
        ],
        "stopDescription": "Nonstop",
    },
]

MATCHING_FLIGHTS = {"changeShoppingPage": {"flights": {"outboundPage": {"cards": FLIGHT_CARDS}}}}


@pytest.fixture(autouse=True)
def mock_sleep(mocker: MockerFixture) -> None:
    mocker.patch("time.sleep")


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
        "arrivalAirport": {"code": "SYD", "name": "test_inbound", "country": None},
        "departureAirport": {"code": "LAX", "name": "test_outbound"},
        "departureDate": "2021-12-06",
        "departureTime": "14:40",
        "flights": [{"number": "WN100"}, {"number": "WN101"}],
        "fareProductDetails": {"fareProductId": "WGA"},
    }

    reservation_info = {
        "bounds": [flight_info],
        "_links": {"change": {"href": "change_page", "query": "test_query"}, "reaccom": None},
        "greyBoxMessage": None,
    }
    return Flight(flight_info, reservation_info, "TEST")


def test_fare_drop_outbound_same_flight(
    requests_mock: RequestMocker, monitor: ReservationMonitor, flight: Flight
) -> None:
    requests_mock.get(CHANGE_FLIGHT_URL, [{"json": CHANGE_FLIGHT_PAGE, "status_code": 200}])
    requests_mock.post(MATCHING_FLIGHTS_URL, [{"json": MATCHING_FLIGHTS, "status_code": 200}])

    fare_checker = FareChecker(monitor)
    fare_checker.check_flight_price(flight)

    monitor.notification_handler.lower_fare.assert_called_once_with(flight, "-3,600 PTS")


def test_fare_drop_inbound_same_flight(
    requests_mock: RequestMocker, monitor: ReservationMonitor, flight: Flight
) -> None:
    flight.flight_number = "97"

    flight_info = copy.deepcopy(flight.reservation_info["bounds"][0])
    # Changing the outbound flight's fare to an invalid type will safeguard against the
    # outbound flight being looked at instead of the inbound
    flight_info["fareProductDetails"] = {"fareProductId": "TEST"}
    flight.reservation_info["bounds"].insert(0, flight_info)

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

    requests_mock.get(CHANGE_FLIGHT_URL, [{"json": flight_page, "status_code": 200}])
    requests_mock.post(MATCHING_FLIGHTS_URL, [{"json": matching_flights, "status_code": 200}])

    fare_checker = FareChecker(monitor)
    fare_checker.check_flight_price(flight)

    monitor.notification_handler.lower_fare.assert_called_once_with(flight, "-4,300 PTS")


@pytest.mark.parametrize(
    ("check_fares_option", "low_fare"),
    [
        (CheckFaresOption.SAME_FLIGHT, "-3,600 PTS"),
        (CheckFaresOption.SAME_DAY_NONSTOP, "-4,800 PTS"),
        (CheckFaresOption.SAME_DAY, "-5,200 PTS"),
    ],
)
def test_fare_drop_with_filter(
    requests_mock: RequestMocker,
    monitor: ReservationMonitor,
    flight: Flight,
    check_fares_option: CheckFaresOption,
    low_fare: str,
) -> None:
    requests_mock.get(CHANGE_FLIGHT_URL, [{"json": CHANGE_FLIGHT_PAGE, "status_code": 200}])
    requests_mock.post(MATCHING_FLIGHTS_URL, [{"json": MATCHING_FLIGHTS, "status_code": 200}])

    monitor.config.check_fares = check_fares_option
    fare_checker = FareChecker(monitor)
    fare_checker.check_flight_price(flight)

    monitor.notification_handler.lower_fare.assert_called_once_with(flight, low_fare)


@pytest.mark.parametrize(("amount", "sign"), [("1,000", None), ("1", "-"), ("0", None)])
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
    if sign:
        fare["sign"] = sign
    else:
        fare.pop("sign")

    matching_flights = copy.deepcopy(MATCHING_FLIGHTS)
    matching_flights["changeShoppingPage"]["flights"]["outboundPage"]["cards"] = flights

    requests_mock.get(CHANGE_FLIGHT_URL, [{"json": CHANGE_FLIGHT_PAGE, "status_code": 200}])
    requests_mock.post(MATCHING_FLIGHTS_URL, [{"json": matching_flights, "status_code": 200}])

    fare_checker = FareChecker(monitor)
    fare_checker.check_flight_price(flight)

    monitor.notification_handler.lower_fare.assert_not_called()


def test_flight_error_with_companion(
    requests_mock: RequestMocker, monitor: ReservationMonitor, flight: Flight
) -> None:
    message = {"body": "You must first cancel the associated companion reservation."}
    flight.reservation_info["greyBoxMessage"] = message
    flight.reservation_info["bounds"][0]["fareProductDetails"] = {"fareProductId": "WGARED"}
    monitor.username = "test-user"
    monitor.password = "test-password"

    mock_points_transactions = mock.Mock(
        return_value={
            "data": [
                {
                    "product_category": "FLIGHT",
                    "transaction_type": "REDEEM",
                    "transaction_at": "2026-01-01T12:00:00Z",
                    "flight_details": {
                        "record_locator": "TEST",
                        "origination_airport_code": "LAX",
                        "destination_airport_code": "SYD",
                        "depart_at": "2021-12-06T14:40:00",
                    },
                    "points_detail": {
                        "transaction_points": {"amount": "20,000", "currency": "PTS"}
                    },
                }
            ]
        }
    )

    flights = copy.deepcopy(FLIGHT_CARDS)
    flights[2]["fares"] = [
        {"_meta": {"fareProductId": "WGARED"}, "reasonIfUnavailable": "Unavailable"},
        {
            "_meta": {"fareProductId": "PLURED"},
            "price": {"amount": "20,000", "currencyCode": "PTS"},
            "priceDifference": {"sign": "+", "amount": "0", "currencyCode": "PTS"},
        },
    ]

    matching_flights = copy.deepcopy(MATCHING_FLIGHTS)
    matching_flights["changeShoppingPage"]["flights"]["outboundPage"]["cards"] = flights

    requests_mock.get(CHANGE_FLIGHT_URL, [{"json": CHANGE_FLIGHT_PAGE, "status_code": 200}])
    requests_mock.post(MATCHING_FLIGHTS_URL, [{"json": matching_flights, "status_code": 200}])
    with mock.patch.object(WebDriver, "get_points_transactions", mock_points_transactions):
        fare_checker = FareChecker(monitor)
        fare_checker.check_flight_price(flight)

    monitor.notification_handler.lower_fare.assert_not_called()
    mock_points_transactions.assert_called_once()


def test_flight_error_when_no_change_link_exists(
    monitor: ReservationMonitor, flight: Flight
) -> None:
    flight.reservation_info["_links"]["change"] = None

    fare_checker = FareChecker(monitor)
    with pytest.raises(FlightChangeError):
        fare_checker.check_flight_price(flight)


def test_basic_fare_drop_uses_upgrade_prices_when_basic_is_unavailable(
    requests_mock: RequestMocker, monitor: ReservationMonitor, flight: Flight
) -> None:
    flights = copy.deepcopy(FLIGHT_CARDS)
    flights[2]["fares"] = [
        {
            "_meta": {"fareProductId": "WGA"},
            "reasonIfUnavailable": "Unavailable",
        },
        {
            "_meta": {"fareProductId": "PLU"},
            "price": {"amount": "60", "currencyCode": "USD"},
            "priceDifference": {"sign": "+", "amount": "19", "currencyCode": "USD"},
        },
        {
            "_meta": {"fareProductId": "ANY"},
            "price": {"amount": "130", "currencyCode": "USD"},
            "priceDifference": {"sign": "+", "amount": "51", "currencyCode": "USD"},
        },
    ]

    matching_flights = copy.deepcopy(MATCHING_FLIGHTS)
    matching_flights["changeShoppingPage"]["flights"]["outboundPage"]["cards"] = flights
    flight.reservation_info["_links"]["cancelBound"] = {
        "href": "cancel_bound",
        "method": "GET",
        "query": {},
    }
    cancel_bound_page = {
        "viewForCancelBoundPage": {
            "_links": {
                "refundQuote": {
                    "href": "refund_quote",
                    "method": "POST",
                    "body": {},
                }
            }
        }
    }
    refund_quote_page = {
        "cancelRefundQuotePage": {
            "cancelBounds": [{"flight": "100\u200b/\u200b101"}],
            "tripTotals": [{"amount": "79", "currencyCode": "USD"}],
        }
    }

    requests_mock.get(CHANGE_FLIGHT_URL, [{"json": CHANGE_FLIGHT_PAGE, "status_code": 200}])
    requests_mock.get(CANCEL_BOUND_URL, [{"json": cancel_bound_page, "status_code": 200}])
    requests_mock.post(MATCHING_FLIGHTS_URL, [{"json": matching_flights, "status_code": 200}])
    requests_mock.post(REFUND_QUOTE_URL, [{"json": refund_quote_page, "status_code": 200}])

    fare_checker = FareChecker(monitor)
    fare_checker.check_flight_price(flight)

    monitor.notification_handler.lower_fare.assert_called_once_with(flight, "-38 USD")


@pytest.mark.parametrize(
    "fare", [None, [{"_meta": {"fareProductId": "TEST"}}], [{"_meta": {"fareProductId": "WGA"}}]]
)
def test_unavailable_fares(
    requests_mock: RequestMocker, monitor: ReservationMonitor, flight: Flight, fare: list
) -> None:
    flights = copy.deepcopy(FLIGHT_CARDS)
    flights[2]["fares"] = fare

    matching_flights = copy.deepcopy(MATCHING_FLIGHTS)
    matching_flights["changeShoppingPage"]["flights"]["outboundPage"]["cards"] = flights

    requests_mock.get(CHANGE_FLIGHT_URL, [{"json": CHANGE_FLIGHT_PAGE, "status_code": 200}])
    requests_mock.post(MATCHING_FLIGHTS_URL, [{"json": matching_flights, "status_code": 200}])

    fare_checker = FareChecker(monitor)
    fare_checker.check_flight_price(flight)

    monitor.notification_handler.lower_fare.assert_not_called()
