from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest
import pytz
from pytest_mock import MockerFixture

from lib.flight import Flight

# This needs to be accessed to be tested
# pylint: disable=protected-access


@pytest.fixture
def test_flight() -> Flight:
    flight_info = {
        "departureAirport": {"name": None},
        "arrivalAirport": {"name": None},
        "departureTime": None,
        "arrivalTime": None,
    }

    # Needs to be mocked so it isn't run only when Flight is instantiated
    with mock.patch.object(Flight, "_get_flight_time"):
        return Flight(flight_info, "test_num")


def test_get_flight_time_returns_the_correct_time(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    mock_get_airport_tz = mocker.patch.object(
        Flight, "_get_airport_timezone", return_value="Asia/Calcutta"
    )
    mock_convert_to_utc = mocker.patch.object(Flight, "_convert_to_utc", return_value="12:31:05")

    flight_info = {
        "departureDate": "12-31-99",
        "departureTime": "23:59:59",
        "departureAirport": {"code": "999"},
    }
    flight_time = test_flight._get_flight_time(flight_info)

    mock_get_airport_tz.assert_called_once_with("999")
    mock_convert_to_utc.assert_called_once_with("12-31-99 23:59:59", "Asia/Calcutta")
    assert flight_time == "12:31:05"


def test_get_airport_timezone_returns_the_correct_timezone(
    mocker: MockerFixture, test_flight: Flight
) -> None:
    mocker.patch.object(Path, "read_text")
    mocker.patch("json.loads", return_value={"test_code": "Asia/Calcutta"})
    timezone = test_flight._get_airport_timezone("test_code")
    assert timezone == pytz.timezone("Asia/Calcutta")


def test_convert_to_utc_converts_local_time_to_utc(test_flight: Flight) -> None:
    tz = pytz.timezone("Asia/Calcutta")
    utc_flight_time = test_flight._convert_to_utc("1999-12-31 23:59", tz)

    assert utc_flight_time == datetime(1999, 12, 31, 18, 29)
