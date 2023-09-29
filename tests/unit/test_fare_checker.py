from typing import Any, Dict, List

import pytest
from pytest_mock import MockerFixture

from lib.config import ReservationConfig
from lib.fare_checker import BOOKING_URL, FareChecker
from lib.flight import Flight
from lib.notification_handler import NotificationHandler
from lib.reservation_monitor import ReservationMonitor
from lib.utils import FlightChangeError

# This needs to be accessed to be tested
# pylint: disable=protected-access

JSON = Dict[str, Any]


@pytest.fixture
def test_flight(mocker: MockerFixture) -> Flight:
    mocker.patch.object(Flight, "_get_flight_time")
    flight_info = {
        "departureAirport": {"name": None},
        "arrivalAirport": {"name": None},
        "departureTime": None,
        "flights": [{"number": "100"}],
    }
    return Flight(flight_info, "")


class TestFareChecker:
    @pytest.fixture(autouse=True)
    def _set_up_checker(self) -> None:
        # pylint: disable=attribute-defined-outside-init
        self.checker = FareChecker(ReservationMonitor(ReservationConfig()))

    # Test with a comma to make sure the fare checker handles it correctly
    @pytest.mark.parametrize("amount", ["10", "2,000"])
    def test_check_flight_price_sends_notification_on_lower_fares(
        self, mocker: MockerFixture, amount: str
    ) -> None:
        flight_price = {"sign": "-", "amount": amount, "currencyCode": "USD"}
        mocker.patch.object(FareChecker, "_get_flight_price", return_value=flight_price)
        mock_lower_fare_notification = mocker.patch.object(NotificationHandler, "lower_fare")

        self.checker.check_flight_price("test_flight")

        mock_lower_fare_notification.assert_called_once()

    # -1 dollar fares are a false positive and are treated as a higher fare
    @pytest.mark.parametrize(["sign", "amount"], [("+", "10"), ("-", "1")])
    def test_check_flight_price_does_not_send_notifications_when_fares_are_higher(
        self, mocker: MockerFixture, sign: str, amount: str
    ) -> None:
        flight_price = {"sign": sign, "amount": amount, "currencyCode": "USD"}
        mocker.patch.object(FareChecker, "_get_flight_price", return_value=flight_price)
        mock_lower_fare_notification = mocker.patch.object(NotificationHandler, "lower_fare")

        self.checker.check_flight_price("test_flight")
        mock_lower_fare_notification.assert_not_called()

    def test_get_flight_price_gets_flight_price_matching_current_flight(
        self, mocker: MockerFixture, test_flight: Flight
    ) -> None:
        flights = [
            {"flightNumbers": "99"},
            {"flightNumbers": "100", "fares": ["fare_one", "fare_two"]},
        ]
        mocker.patch.object(
            FareChecker, "_get_matching_flights", return_value=(flights, "test_fare")
        )
        mock_get_matching_fare = mocker.patch.object(
            FareChecker, "_get_matching_fare", return_value="price"
        )

        price = self.checker._get_flight_price(test_flight)

        assert price == "price"
        mock_get_matching_fare.assert_called_once_with(["fare_one", "fare_two"], "test_fare")

    # This scenario should not happen because Southwest should always have a flight
    # at the same time (as it is a scheduled flight)
    def test_get_flight_price_raises_error_when_no_matching_flights_appear(
        self, mocker: MockerFixture, test_flight: Flight
    ) -> None:
        flights = [{"flightNumbers": "98"}, {"flightNumbers": "99"}]
        mocker.patch.object(
            FareChecker, "_get_matching_flights", return_value=(flights, "test_fare")
        )

        with pytest.raises(ValueError):
            self.checker._get_flight_price(test_flight)

    @pytest.mark.parametrize("bound", ["outbound", "inbound"])
    def test_get_matching_flights_retrieves_correct_bound_page(
        self, mocker: MockerFixture, bound: str
    ) -> None:
        change_flight_page = {"_links": {"changeShopping": {"href": "test_link"}}}
        fare_type_bounds = [
            {"fareProductDetails": {"fareProductId": "outbound_fare"}},
            {"fareProductDetails": {"fareProductId": "inbound_fare"}},
        ]
        mocker.patch.object(
            FareChecker,
            "_get_change_flight_page",
            return_value=(change_flight_page, fare_type_bounds),
        )

        search_query = {"outbound": {"isChangeBound": False}}
        search_query.update({bound: {"isChangeBound": True}})
        mocker.patch.object(FareChecker, "_get_search_query", return_value=search_query)

        response = {"changeShoppingPage": {"flights": {f"{bound}Page": {"cards": "test_cards"}}}}
        mocker.patch("lib.fare_checker.make_request", return_value=response)

        matching_flights, fare_type = self.checker._get_matching_flights(None)

        assert matching_flights == "test_cards"
        assert fare_type == bound + "_fare"

    def test_get_change_flight_page_retrieves_change_flight_page(
        self, mocker: MockerFixture, test_flight: Flight
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

        change_flight_page, fare_type_bounds = self.checker._get_change_flight_page(test_flight)

        mock_check_for_companion.assert_called_once()
        assert change_flight_page == "test_page"
        assert fare_type_bounds == ["bound_one", "bound_two"]

        call_args = mock_make_request.call_args[0]
        assert call_args[1] == BOOKING_URL + "test_link"
        assert call_args[3] == "query"

    def test_get_change_flight_page_raises_exception_when_flight_cannot_be_changed(
        self, mocker: MockerFixture, test_flight: Flight
    ) -> None:
        reservation_info = {
            "viewReservationViewPage": {
                "greyBoxMessage": None,
                "bounds": ["bound_one", "bound_two"],
                "_links": {"change": None},
            }
        }
        mocker.patch("lib.fare_checker.make_request", return_value=reservation_info)

        with pytest.raises(FlightChangeError):
            self.checker._get_change_flight_page(test_flight)

    def test_get_search_query_returns_the_correct_query_for_one_way(
        self, test_flight: Flight
    ) -> None:
        bound_one = {
            "originalDate": "1/1",
            "toAirportCode": "LAX",
            "fromAirportCode": "MIA",
            "flight": "100",
        }
        flight_page = {
            "boundSelections": [bound_one],
            "_links": {"changeShopping": {"body": [{"boundReference": "bound_1"}]}},
        }

        search_query = self.checker._get_search_query(flight_page, test_flight)

        assert len(search_query) == 1
        assert search_query.get("outbound") == {
            "boundReference": "bound_1",
            "date": "1/1",
            "destination-airport": "LAX",
            "origin-airport": "MIA",
            "isChangeBound": True,
        }

    def test_get_search_query_returns_the_correct_query_for_round_trip(
        self, test_flight: Flight
    ) -> None:
        bound_one = {
            "originalDate": "1/1",
            "toAirportCode": "LAX",
            "fromAirportCode": "MIA",
            "flight": "99",
        }
        bound_two = {
            "originalDate": "1/2",
            "toAirportCode": "MIA",
            "fromAirportCode": "LAX",
            "flight": "100",
        }
        flight_page = {
            "boundSelections": [bound_one, bound_two],
            "_links": {
                "changeShopping": {
                    "body": [{"boundReference": "bound_1"}, {"boundReference": "bound_2"}]
                }
            },
        }

        search_query = self.checker._get_search_query(flight_page, test_flight)

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

    def test_check_for_companion_raises_exception_when_a_companion_is_detected(self) -> None:
        reservation_info = {
            "greyBoxMessage": {
                "body": (
                    "In order to change or cancel, you must first cancel the associated "
                    "companion reservation."
                )
            }
        }

        with pytest.raises(FlightChangeError):
            self.checker._check_for_companion(reservation_info)

    @pytest.mark.parametrize(
        "reservation",
        [{"greyBoxMessage": None}, {"greyBoxMessage": {}}, {"greyBoxMessage": {"body": ""}}],
    )
    def test_check_for_companion_passes_when_no_companion_exists(self, reservation: JSON) -> None:
        # It will throw an exception if the test does not pass
        self.checker._check_for_companion(reservation)

    def test_get_matching_fare_returns_the_correct_fare(self) -> None:
        fares = [
            {"_meta": {"fareProductId": "wrong_fare"}, "priceDifference": "fake_price"},
            {"_meta": {"fareProductId": "right_fare"}, "priceDifference": "price"},
        ]
        fare_price = self.checker._get_matching_fare(fares, "right_fare")
        assert fare_price == "price"

    @pytest.mark.parametrize("fares", [None, [], [{"_meta": {"fareProductId": "right_fare"}}]])
    def test_get_matching_fare_returns_default_price_when_price_is_not_available(
        self, fares: List[JSON]
    ) -> None:
        fare_price = self.checker._get_matching_fare(fares, "right_fare")
        assert fare_price == {"amount": "0", "currencyCode": "USD"}

    def test_unavailable_fare_returns_default_price(self) -> None:
        fare_price = self.checker._unavailable_fare("fare")
        assert fare_price == {"amount": "0", "currencyCode": "USD"}
