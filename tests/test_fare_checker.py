from typing import Any, Dict, List

import pytest
from pytest_mock import MockerFixture

from lib.config import Config
from lib.fare_checker import BOOKING_URL, FareChecker
from lib.flight import Flight
from lib.flight_retriever import FlightRetriever
from lib.notification_handler import NotificationHandler
from lib.utils import FlightChangeError

# This needs to be accessed to be tested
# pylint: disable=protected-access

JSON = Dict[str, Any]


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


def test_check_flight_price_sends_notification_on_lower_fares(mocker: MockerFixture) -> None:
    flight_price = {"sign": "-", "amount": "10", "currencyCode": "USD"}
    mocker.patch.object(FareChecker, "_get_flight_price", return_value=flight_price)
    mock_lower_fare_notification = mocker.patch.object(NotificationHandler, "lower_fare")

    fare_checker = FareChecker(FlightRetriever(Config()))
    fare_checker.check_flight_price("test_flight")

    mock_lower_fare_notification.assert_called_once()


def test_check_flight_price_does_not_send_notifications_when_fares_are_higher(
    mocker: MockerFixture,
) -> None:
    flight_price = {"sign": "+", "amount": "10", "currencyCode": "USD"}
    mocker.patch.object(FareChecker, "_get_flight_price", return_value=flight_price)
    mock_lower_fare_notification = mocker.patch.object(NotificationHandler, "lower_fare")

    fare_checker = FareChecker(FlightRetriever(Config()))
    fare_checker.check_flight_price("test_flight")

    mock_lower_fare_notification.assert_not_called()


def test_get_flight_price_gets_flight_price_matching_current_flight(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    flights = [
        {"departureTime": "11:30", "arrivalTime": "14:00"},
        {"departureTime": "11:30", "arrivalTime": "13:30", "fares": ["fare_one", "fare_two"]},
    ]
    mocker.patch.object(FareChecker, "_get_matching_flights", return_value=(flights, "test_fare"))
    mock_get_matching_fare = mocker.patch.object(
        FareChecker, "_get_matching_fare", return_value="price"
    )

    test_flight.local_departure_time = "11:30"
    test_flight.local_arrival_time = "13:30"
    fare_checker = FareChecker(FlightRetriever(Config()))
    price = fare_checker._get_flight_price(test_flight)

    assert price == "price"
    mock_get_matching_fare.assert_called_once_with(["fare_one", "fare_two"], "test_fare")


# This scenario should not happen because Southwest should always have a flight
# at the same time (as it is a scheduled flight)
def test_get_flight_price_returns_nothing_when_no_matching_flights_appear(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    flights = [{"departureTime": "10:30"}, {"departureTime": "11:30"}]
    mocker.patch.object(FareChecker, "_get_matching_flights", return_value=(flights, "test_fare"))

    test_flight.local_departure_time = "12:00"
    fare_checker = FareChecker(FlightRetriever(Config()))
    price = fare_checker._get_flight_price(test_flight)

    assert price is None


@pytest.mark.parametrize("bound", ["outbound", "inbound"])
def test_get_matching_flights_retrieves_correct_bound_page(
    mocker: MockerFixture, bound: str
) -> None:
    change_flight_page = {"_links": {"changeShopping": {"href": "test_link"}}}
    fare_type_bounds = [
        {"fareProductDetails": {"fareProductId": "outbound_fare"}},
        {"fareProductDetails": {"fareProductId": "inbound_fare"}},
    ]
    mocker.patch.object(
        FareChecker, "_get_change_flight_page", return_value=(change_flight_page, fare_type_bounds)
    )

    search_query = {"outbound": {"isChangeBound": False}}
    search_query.update({bound: {"isChangeBound": True}})
    mocker.patch.object(FareChecker, "_get_search_query", return_value=search_query)

    response = {"changeShoppingPage": {"flights": {f"{bound}Page": {"cards": "test_cards"}}}}
    mocker.patch("lib.fare_checker.make_request", return_value=response)

    fare_checker = FareChecker(FlightRetriever(Config()))
    matching_flights, fare_type = fare_checker._get_matching_flights(None)

    assert matching_flights == "test_cards"
    assert fare_type == bound + "_fare"


def test_get_change_flight_page_retrieves_change_flight_page(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    reservation_info = {
        "viewReservationViewPage": {
            "bounds": ["bound_one", "bound_two"],
            "_links": {"change": {"href": "test_link", "query": "query"}},
        }
    }
    expected_page = {"changeFlightPage": "test_page"}
    mock_make_request = mocker.patch(
        "lib.fare_checker.make_request", side_effect=[reservation_info, expected_page]
    )
    mock_check_for_companion = mocker.patch.object(FareChecker, "_check_for_companion")

    fare_checker = FareChecker(FlightRetriever(Config()))
    change_flight_page, fare_type_bounds = fare_checker._get_change_flight_page(test_flight)

    mock_check_for_companion.assert_called_once()
    assert change_flight_page == "test_page"
    assert fare_type_bounds == ["bound_one", "bound_two"]

    call_args = mock_make_request.call_args[0]
    assert call_args[1] == BOOKING_URL + "test_link"
    assert call_args[3] == "query"


def test_get_change_flight_page_raises_exception_when_flight_cannot_be_changed(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    reservation_info = {
        "viewReservationViewPage": {
            "greyBoxMessage": None,
            "bounds": ["bound_one", "bound_two"],
            "_links": {"change": None},
        }
    }
    mocker.patch("lib.fare_checker.make_request", return_value=reservation_info)

    fare_checker = FareChecker(FlightRetriever(Config()))
    with pytest.raises(FlightChangeError):
        fare_checker._get_change_flight_page(test_flight)


def test_get_search_query_returns_the_correct_query_for_one_way(test_flight: Flight) -> None:
    bound_one = {
        "originalDate": "1/1",
        "toAirportCode": "LAX",
        "fromAirportCode": "MIA",
        "timeDeparts": "12:00",
    }
    flight_page = {
        "boundSelections": [bound_one],
        "_links": {"changeShopping": {"body": [{"boundReference": "bound_1"}]}},
    }

    test_flight.local_departure_time = "12:00"
    search_query = FareChecker._get_search_query(flight_page, test_flight)

    assert len(search_query) == 1
    assert search_query.get("outbound") == {
        "boundReference": "bound_1",
        "date": "1/1",
        "destination-airport": "LAX",
        "origin-airport": "MIA",
        "isChangeBound": True,
    }


def test_get_search_query_returns_the_correct_query_for_round_trip(test_flight: Flight) -> None:
    bound_one = {
        "originalDate": "1/1",
        "toAirportCode": "LAX",
        "fromAirportCode": "MIA",
        "timeDeparts": "12:00",
    }
    bound_two = {
        "originalDate": "1/2",
        "toAirportCode": "MIA",
        "fromAirportCode": "LAX",
        "timeDeparts": "1:00",
    }
    flight_page = {
        "boundSelections": [bound_one, bound_two],
        "_links": {
            "changeShopping": {
                "body": [{"boundReference": "bound_1"}, {"boundReference": "bound_2"}]
            }
        },
    }

    test_flight.local_departure_time = "1:00"
    search_query = FareChecker._get_search_query(flight_page, test_flight)

    assert len(search_query) == 2
    assert search_query.get("outbound") == {
        "boundReference": "bound_1",
        "date": "1/1",
        "destination-airport": "LAX",
        "origin-airport": "MIA",
        "isChangeBound": False,
    }
    assert search_query.get("inbound") == {
        "boundReference": "bound_2",
        "date": "1/2",
        "destination-airport": "MIA",
        "origin-airport": "LAX",
        "isChangeBound": True,
    }


def test_check_for_companion_raises_exception_when_a_companion_is_detected() -> None:
    reservation_info = {
        "greyBoxMessage": {
            "body": (
                "In order to change or cancel, you must first cancel the associated "
                "companion reservation."
            )
        }
    }

    with pytest.raises(FlightChangeError):
        FareChecker._check_for_companion(reservation_info)


@pytest.mark.parametrize(
    "reservation",
    [{"greyBoxMessage": None}, {"greyBoxMessage": {}}, {"greyBoxMessage": {"body": ""}}],
)
def test_check_for_companion_passes_when_no_companion_exists(reservation: JSON) -> None:
    # It will throw an exception if the test does not pass
    FareChecker._check_for_companion(reservation)


def test_get_matching_fare_returns_the_correct_fare() -> None:
    fares = [
        {"_meta": {"fareProductId": "wrong_fare"}, "priceDifference": "fake_price"},
        {"_meta": {"fareProductId": "right_fare"}, "priceDifference": "price"},
    ]
    fare_checker = FareChecker(FlightRetriever(Config()))
    fare_price = fare_checker._get_matching_fare(fares, "right_fare")
    assert fare_price == "price"


@pytest.mark.parametrize("fares", [None, [{"_meta": {"fareProductId": "right_fare"}}]])
def test_get_matching_fare_returns_default_price_when_price_is_not_available(
    fares: List[JSON],
) -> None:
    fare_checker = FareChecker(FlightRetriever(Config()))
    fare_price = fare_checker._get_matching_fare(fares, "right_fare")
    assert fare_price == {"amount": 0, "currencyCode": "USD"}


def test_get_matching_fare_raises_exception_when_fare_does_not_exist() -> None:
    fares = [{"_meta": {"fareProductId": "wrong_fare"}}]
    fare_checker = FareChecker(FlightRetriever(Config()))
    with pytest.raises(KeyError):
        fare_checker._get_matching_fare(fares, "right_fare")


def test_unavailable_fare_returns_default_price() -> None:
    fare_checker = FareChecker(FlightRetriever(Config()))
    fare_price = fare_checker._unavailable_fare("fare")
    assert fare_price == {"amount": 0, "currencyCode": "USD"}
