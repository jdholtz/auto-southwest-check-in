from typing import Any, Callable

import pytest
from pytest_mock import MockerFixture

from lib import fare_checker
from lib.config import ReservationConfig
from lib.fare_checker import FareChecker
from lib.flight import Flight
from lib.notification_handler import NotificationHandler
from lib.reservation_monitor import ReservationMonitor
from lib.utils import CheckFaresOption, FlightChangeError

JSON = dict[str, Any]


@pytest.fixture(autouse=True)
def mock_sleep(mocker: MockerFixture) -> None:
    mocker.patch("time.sleep")


@pytest.fixture
def test_flight(mocker: MockerFixture) -> Flight:
    mocker.patch.object(Flight, "_set_flight_time")
    flight_info = {
        "departureAirport": {"name": None},
        "arrivalAirport": {"name": None, "country": None},
        "departureTime": None,
        "flights": [{"number": "WN100"}],
    }

    reservation_info = {"bounds": [flight_info]}
    return Flight(flight_info, reservation_info, "")


class TestFareChecker:
    @pytest.fixture(autouse=True)
    def _set_up_checker(self) -> None:
        self.checker = FareChecker(ReservationMonitor(ReservationConfig()))

    def test_check_flight_price_sends_notification_on_lower_fares(
        self, mocker: MockerFixture
    ) -> None:
        flight_price = {"amount": -10, "currencyCode": "USD"}
        mocker.patch.object(FareChecker, "_get_flight_price", return_value=flight_price)
        mock_lower_fare_notification = mocker.patch.object(NotificationHandler, "lower_fare")

        self.checker.check_flight_price("test_flight")

        mock_lower_fare_notification.assert_called_once()

    # -1 dollar fares are a false positive and are treated as a higher fare
    @pytest.mark.parametrize("amount", [10, 0, -1])
    def test_check_flight_price_does_not_send_notifications_when_fares_are_higher(
        self, mocker: MockerFixture, amount: int
    ) -> None:
        flight_price = {"amount": amount, "currencyCode": "USD"}
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
            FareChecker, "_get_matching_fare", return_value={"amount": -300, "currencyCode": "PTS"}
        )

        price = self.checker._get_flight_price(test_flight)

        assert price == {"amount": -300, "currencyCode": "PTS"}
        mock_get_matching_fare.assert_called_once_with(["fare_one", "fare_two"], "test_fare")

    @pytest.mark.parametrize("bound", ["outbound", "inbound"])
    def test_get_matching_flights_retrieves_correct_bound_page(
        self, mocker: MockerFixture, test_flight: Flight, bound: str
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

        matching_flights, fare_type = self.checker._get_matching_flights(test_flight)

        assert matching_flights == "test_cards"
        assert fare_type == bound + "_fare"

    def test_get_change_flight_page_raises_exception_when_bound_not_matched(
        self, mocker: MockerFixture, test_flight: Flight
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

        # Set both bounds to be false which could happen when the flight number doesn't match those
        # on the reservation, indicating a formatting change on Southwest's end
        search_query = {"outbound": {"isChangeBound": False}, "inbound": {"isChangeBound": False}}
        mocker.patch.object(FareChecker, "_get_search_query", return_value=search_query)

        mocker.patch("lib.fare_checker.make_request")

        with pytest.raises(ValueError):
            self.checker._get_matching_flights(test_flight)

    def test_get_change_flight_page_retrieves_change_flight_page(
        self, mocker: MockerFixture
    ) -> None:
        res_info = {
            "bounds": ["bound_one", "bound_two"],
            "_links": {"change": {"href": "test_link", "query": "query_body"}, "reaccom": None},
        }
        flight_page = {"changeFlightPage": "test_page"}
        mock_make_request = mocker.patch("lib.fare_checker.make_request", return_value=flight_page)
        mock_check_for_companion = mocker.patch.object(FareChecker, "_check_for_companion")

        change_flight_page, fare_type_bounds = self.checker._get_change_flight_page(res_info)

        mock_check_for_companion.assert_called_once()
        assert change_flight_page == "test_page"
        assert fare_type_bounds == ["bound_one", "bound_two"]

        call_args = mock_make_request.call_args[0]
        assert call_args[1] == fare_checker.BOOKING_URL + "test_link"
        assert call_args[3] == "query_body"

    def test_get_change_flight_page_raises_exception_when_flight_is_reaccommodated(self) -> None:
        reservation_info = {
            "greyBoxMessage": None,
            "bounds": ["bound_one", "bound_two"],
            "_links": {"change": None, "reaccom": {"href": "test_link"}},
        }

        with pytest.raises(FlightChangeError) as err:
            self.checker._get_change_flight_page(reservation_info)

        assert "reaccommodated" in str(err.value).lower()

    def test_get_change_flight_page_raises_exception_when_flight_cannot_be_changed(self) -> None:
        reservation_info = {
            "greyBoxMessage": None,
            "bounds": ["bound_one", "bound_two"],
            "_links": {"change": None, "reaccom": None},
        }

        with pytest.raises(FlightChangeError) as err:
            self.checker._get_change_flight_page(reservation_info)

        assert "cannot be changed" in str(err.value).lower()

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
        [
            {"greyBoxMessage": None},
            {"greyBoxMessage": {}},
            {"greyBoxMessage": {"body": None}},
            {"greyBoxMessage": {"body": ""}},
        ],
    )
    def test_check_for_companion_passes_when_no_companion_exists(self, reservation: JSON) -> None:
        # An exception will be thrown if the test does not pass
        self.checker._check_for_companion(reservation)

    def test_get_lowest_fare_returns_lowest_matching_fare(
        self, mocker: MockerFixture, test_flight: Flight
    ) -> None:
        self.checker.filter = fare_checker.any_flight_filter

        flights = [{"fares": "fare1"}, {"fares": "fare2"}, {"fares": "fare3"}]
        fares = [
            {"amount": 3000, "currencyCode": "PTS"},
            {"amount": -2000, "currencyCode": "PTS"},
            {"amount": -1000, "currencyCode": "PTS"},
        ]
        mocker.patch.object(FareChecker, "_get_matching_fare", side_effect=fares)

        assert self.checker._get_lowest_fare(test_flight, flights, "test_fare") == fares[1]

    def test_get_lowest_fare_returns_matching_fare_when_only_one_flight(
        self, mocker: MockerFixture, test_flight: Flight
    ) -> None:
        self.checker.filter = fare_checker.same_flight_filter

        flights = [
            {"fares": "fare1", "flightNumbers": "100"},
            {"fares": "fare2", "flightNumbers": "101"},
        ]

        fares = [{"amount": 3000, "currencyCode": "PTS"}, {"amount": -2000, "currencyCode": "PTS"}]
        # Only should be called once, so should only return the first fare
        mocker.patch.object(FareChecker, "_get_matching_fare", side_effect=fares)

        assert self.checker._get_lowest_fare(test_flight, flights, "test_fare") == fares[0]

    # An empty list of flights should never be returned from Southwest, but test just in case
    @pytest.mark.parametrize("flights", [[], [{"fares": "fare1"}]])
    def test_get_lowest_fare_returns_zero_when_no_matching_fares(
        self, mocker: MockerFixture, test_flight: Flight, flights: list[JSON]
    ) -> None:
        self.checker.filter = fare_checker.any_flight_filter
        mocker.patch.object(FareChecker, "_get_matching_fare", return_value=None)

        assert self.checker._get_lowest_fare(test_flight, flights, "test_fare") == {
            "amount": 0,
            "currencyCode": "USD",
        }

    def test_get_matching_fare_returns_the_correct_fare(self) -> None:
        fares = [
            {
                "_meta": {"fareProductId": "wrong_fare"},
                "priceDifference": {"amount": "10,000", "currencyCode": "PTS"},
            },
            {
                "_meta": {"fareProductId": "right_fare"},
                "priceDifference": {"amount": "3,000", "sign": "-", "currencyCode": "PTS"},
            },
        ]
        fare_price = self.checker._get_matching_fare(fares, "right_fare")
        assert fare_price == {"amount": -3000, "currencyCode": "PTS"}

    @pytest.mark.parametrize("fares", [None, [], [{"_meta": {"fareProductId": "right_fare"}}]])
    def test_get_matching_fare_returns_nothing_when_price_is_not_available(
        self, fares: list[JSON]
    ) -> None:
        assert self.checker._get_matching_fare(fares, "right_fare") is None


@pytest.mark.parametrize(
    ("option", "expected_filter"),
    [
        (CheckFaresOption.SAME_FLIGHT, fare_checker.same_flight_filter),
        (CheckFaresOption.SAME_DAY_NONSTOP, fare_checker.nonstop_flight_filter),
        (CheckFaresOption.SAME_DAY, fare_checker.any_flight_filter),
    ],
)
def test_get_fare_check_filter_returns_the_corresponding_filter(
    option: CheckFaresOption, expected_filter: Callable[[Flight, JSON], bool]
) -> None:
    assert fare_checker.get_fare_check_filter(option) == expected_filter


def test_get_fare_check_filter_raises_exception_when_option_does_not_match() -> None:
    with pytest.raises(ValueError):
        fare_checker.get_fare_check_filter("wrong_option")


@pytest.mark.parametrize(
    ("flight", "filter_out"), [({"flightNumbers": "100"}, True), ({"flightNumbers": "101"}, False)]
)
def test_same_flight_filter(flight: JSON, filter_out: bool, test_flight: Flight) -> None:
    assert fare_checker.same_flight_filter(test_flight, flight) == filter_out


def test_any_flight_filter(test_flight: Flight) -> None:
    assert fare_checker.any_flight_filter(test_flight, {"flightNumbers": "101"})


@pytest.mark.parametrize(
    ("flight", "filter_out"),
    [({"stopDescription": "1 Stop, LAX"}, False), ({"stopDescription": "Nonstop"}, True)],
)
def test_nonstop_flight_filter(flight: JSON, filter_out: bool) -> None:
    assert fare_checker.nonstop_flight_filter(test_flight, flight) == filter_out
