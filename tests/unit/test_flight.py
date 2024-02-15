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
            "departureAirport": {"name": None},
            "arrivalAirport": {"name": None, "country": None},
            "departureTime": None,
            "flights": [{"number": "100"}],
        }

        departure_time = datetime(1999, 1, 1, 8, 59)
        # Needs to be mocked so it is only run when Flight is instantiated
        with mock.patch.object(Flight, "_get_flight_time", return_value=departure_time):
            # pylint: disable=attribute-defined-outside-init
            self.flight = Flight(flight_info, "test_num")

    @pytest.mark.parametrize(["country", "is_international"], [(None, False), ("Mexico", True)])
    def test_flight_is_international_when_country_is_specified(
        self, mocker: MockerFixture, country: str, is_international: bool
    ) -> None:
        mocker.patch.object(Flight, "_get_flight_time")
        flight_info = {
            "departureAirport": {"name": None},
            "arrivalAirport": {"name": None, "country": country},
            "departureTime": None,
            "flights": [{"number": "100"}],
        }
        flight = Flight(flight_info, "")

        assert flight.is_international == is_international

    def test_flights_with_the_same_flight_numbers_and_departure_times_are_equal(
        self, mocker: MockerFixture
    ) -> None:
        mocker.patch.object(Flight, "_get_flight_time", return_value=datetime(1999, 1, 1, 8, 59))
        flight_info = {
            "departureAirport": {"name": None},
            "arrivalAirport": {"name": None, "country": None},
            "departureTime": None,
            "flights": [{"number": "100"}],
        }
        flight1 = Flight(flight_info, "")
        flight2 = Flight(flight_info, "")

        assert flight1 == flight2

    @pytest.mark.parametrize(
        ["flight_info", "departure_time"],
        [
            (
                {  # Test different flight numbers
                    "departureAirport": {"name": None},
                    "arrivalAirport": {"name": None, "country": None},
                    "departureTime": None,
                    "flights": [{"number": "101"}],
                },
                datetime(1999, 1, 1, 8, 59),
            ),
            (
                {  # Test different departure times
                    "departureAirport": {"name": None},
                    "arrivalAirport": {"name": None, "country": None},
                    "departureTime": None,
                    "flights": [{"number": "100"}],
                },
                datetime(1999, 1, 1, 9, 59),
            ),
        ],
    )
    def test_flights_with_different_flight_numbers_or_departure_times_are_not_equal(
        self, mocker: MockerFixture, flight_info: Dict[str, Any], departure_time: datetime
    ) -> None:
        mocker.patch.object(Flight, "_get_flight_time", return_value=departure_time)
        new_flight = Flight(flight_info, "")

        assert self.flight != new_flight

    def test_get_flight_time_returns_the_correct_time(self, mocker: MockerFixture) -> None:
        mock_get_airport_tz = mocker.patch.object(
            Flight, "_get_airport_timezone", return_value="Asia/Calcutta"
        )
        mock_convert_to_utc = mocker.patch.object(
            Flight, "_convert_to_utc", return_value="12:31:05"
        )

        flight_info = {
            "departureDate": "12-31-99",
            "departureTime": "23:59:59",
            "departureAirport": {"code": "999"},
        }
        flight_time = self.flight._get_flight_time(flight_info)

        mock_get_airport_tz.assert_called_once_with("999")
        mock_convert_to_utc.assert_called_once_with("12-31-99 23:59:59", "Asia/Calcutta")
        assert flight_time == "12:31:05"

    def test_get_airport_timezone_returns_the_correct_timezone(self, mocker: MockerFixture) -> None:
        mocker.patch.object(Path, "read_text")
        mocker.patch("json.loads", return_value={"test_code": "Asia/Calcutta"})
        timezone = self.flight._get_airport_timezone("test_code")
        assert timezone == pytz.timezone("Asia/Calcutta")

    def test_convert_to_utc_converts_local_time_to_utc(self) -> None:
        tz = pytz.timezone("Asia/Calcutta")
        utc_flight_time = self.flight._convert_to_utc("1999-12-31 23:59", tz)

        assert utc_flight_time == datetime(1999, 12, 31, 18, 29)

    @pytest.mark.parametrize(
        ["numbers", "expected_num"], [(["100"], "100"), (["100", "101"], "100\u200b/\u200b101")]
    )
    def test_get_flight_number_creates_flight_number_correctly(
        self, numbers: List[str], expected_num: str
    ) -> None:
        flights = [{"number": num} for num in numbers]
        assert self.flight._get_flight_number(flights) == expected_num
