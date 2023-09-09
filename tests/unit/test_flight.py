from datetime import datetime
from pathlib import Path
from typing import Any, Dict
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
            "arrivalAirport": {"name": None},
            "departureTime": None,
            "arrivalTime": None,
        }

        # Needs to be mocked so it is only run when Flight is instantiated
        with mock.patch.object(Flight, "_get_flight_time", return_value=None):
            # pylint: disable=attribute-defined-outside-init
            self.flight = Flight(flight_info, "test_num")

    def test_flights_with_the_same_attributes_are_equal(self, mocker: MockerFixture) -> None:
        mocker.patch.object(Flight, "_get_flight_time")
        flight_info = {
            "departureAirport": {"name": None},
            "arrivalAirport": {"name": None},
            "departureTime": None,
            "arrivalTime": None,
        }
        flight1 = Flight(flight_info, "")
        flight2 = Flight(flight_info, "")

        assert flight1 == flight2

    @pytest.mark.parametrize(
        "flight_info",
        [
            {
                "departureAirport": {"name": "test"},
                "arrivalAirport": {"name": None},
                "departureTime": None,
                "arrivalTime": None,
            },
            {
                "departureAirport": {"name": None},
                "arrivalAirport": {"name": "test"},
                "departureTime": None,
                "arrivalTime": None,
            },
            {
                "departureAirport": {"name": None},
                "arrivalAirport": {"name": None},
                "departureTime": "12:08",
                "arrivalTime": None,
            },
        ],
    )
    def test_flights_with_different_attributes_are_not_equal(
        self, mocker: MockerFixture, flight_info: Dict[str, Any]
    ) -> None:
        mocker.patch.object(Flight, "_get_flight_time", return_value=flight_info["departureTime"])
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
