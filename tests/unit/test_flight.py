from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

import pytest
import pytz
from pytest_mock import MockerFixture

from lib.flight import Flight

# This needs to be accessed to be tested
# pylint: disable=protected-access


class TestFlight:
    @pytest.fixture(autouse=True)
    def _set_up_flight(self) -> None:
        flight_info = {
            "departureAirport": {"name": None, "code": "DAL"},
            "arrivalAirport": {"name": None, "country": None},
            "departureDate": "1971-06-18",
            "departureTime": "07:00",
            "flights": [{"number": "WN100"}],
        }

        # Needs to be mocked so it is only run when Flight is instantiated
        with mock.patch.object(Flight, "_set_flight_time"):
            # Reservation info can be left empty as it is only used for caching, but isn't relevant
            # to the functionality of the flight class
            # pylint: disable=attribute-defined-outside-init
            self.flight = Flight(flight_info, {}, "test_num")

            # Flight times that would be set if _set_flight_time isn't mocked
            self.flight.departure_time = datetime(1971, 6, 18, 12)
            self.flight._local_departure_time = datetime(1971, 6, 18, 7)

    @pytest.mark.parametrize(["country", "is_international"], [(None, False), ("Mexico", True)])
    def test_flight_is_international_when_country_is_specified(
        self, mocker: MockerFixture, country: str, is_international: bool
    ) -> None:
        mocker.patch.object(Flight, "_set_flight_time")
        flight_info = {
            "departureAirport": {"name": None},
            "arrivalAirport": {"name": None, "country": country},
            "departureTime": None,
            "flights": [{"number": "WN100"}],
        }
        flight = Flight(flight_info, {}, "")

        assert flight.is_international == is_international

    def test_flights_with_the_same_flight_numbers_and_departure_times_are_equal(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(Flight, "_set_flight_time")
        flight_info = {
            "departureAirport": {"name": None},
            "arrivalAirport": {"name": None, "country": None},
            "departureTime": None,
            "flights": [{"number": "WN100"}],
        }
        flight1 = Flight(flight_info, {}, "")
        flight2 = Flight(flight_info, {}, "")

        flight1.departure_time = datetime(1999, 1, 1, 8, 59)
        flight2.departure_time = datetime(1999, 1, 1, 8, 59)

        assert flight1 == flight2

    @pytest.mark.parametrize(
        ["flight_info", "departure_time"],
        [
            (
                {  # Test different flight numbers
                    "departureAirport": {"name": None},
                    "arrivalAirport": {"name": None, "country": None},
                    "departureTime": None,
                    "flights": [{"number": "WN101"}],
                },
                datetime(1999, 1, 1, 8, 59),
            ),
            (
                {  # Test different departure times
                    "departureAirport": {"name": None},
                    "arrivalAirport": {"name": None, "country": None},
                    "departureTime": None,
                    "flights": [{"number": "WN100"}],
                },
                datetime(1999, 1, 1, 9, 59),
            ),
        ],
    )
    def test_flights_with_different_flight_numbers_or_departure_times_are_not_equal(
        self, mocker: MockerFixture, flight_info: Dict[str, Any], departure_time: datetime
    ) -> None:
        mocker.patch.object(Flight, "_set_flight_time")
        new_flight = Flight(flight_info, {}, "")
        new_flight.departure_time = departure_time

        assert self.flight != new_flight

    @pytest.mark.parametrize(
        ["twenty_four_hr", "expected_time"], [(True, "13:59"), (False, "1:59 PM")]
    )
    def test_get_display_time_formats_time_correctly(
        self, twenty_four_hr: bool, expected_time: str
    ) -> None:
        tz = pytz.timezone("Asia/Calcutta")
        self.flight._local_departure_time = tz.localize(datetime(1999, 12, 31, 13, 59))
        assert self.flight.get_display_time(twenty_four_hr) == f"1999-12-31 {expected_time} IST"

    def test_set_flight_time_sets_the_correct_time(self, mocker: MockerFixture) -> None:
        mock_get_airport_tz = mocker.patch.object(
            Flight, "_get_airport_timezone", return_value="Asia/Calcutta"
        )
        mock_convert_to_utc = mocker.patch.object(Flight, "_convert_to_utc", return_value="18:29")

        flight_info = {
            "departureDate": "12-31-99",
            "departureTime": "23:59",
            "departureAirport": {"code": "999"},
        }
        self.flight._set_flight_time(flight_info)

        mock_get_airport_tz.assert_called_once_with("999")
        mock_convert_to_utc.assert_called_once_with("12-31-99 23:59", "Asia/Calcutta")
        assert self.flight.departure_time == "18:29"

    def test_get_airport_timezone_returns_the_correct_timezone(self, mocker: MockerFixture) -> None:
        mocker.patch.object(Path, "read_text")
        mocker.patch("json.loads", return_value={"test_code": "Asia/Calcutta"})
        timezone = self.flight._get_airport_timezone("test_code")
        assert timezone == pytz.timezone("Asia/Calcutta")

    def test_convert_to_utc_converts_local_time_to_utc(self) -> None:
        tz = pytz.timezone("Asia/Calcutta")
        utc_flight_time = self.flight._convert_to_utc("1999-12-31 23:59", tz)

        assert utc_flight_time == datetime(1999, 12, 31, 18, 29)
        assert self.flight._local_departure_time == tz.localize(datetime(1999, 12, 31, 23, 59))

    @pytest.mark.parametrize(
        ["numbers", "expected_num"],
        [(["WN100"], "100"), (["WN100", "WN101"], "100\u200b/\u200b101")],
    )
    def test_get_flight_number_creates_flight_number_correctly(
        self, numbers: List[str], expected_num: str
    ) -> None:
        flights = [{"number": num} for num in numbers]
        assert self.flight._get_flight_number(flights) == expected_num
