from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict

import pytz

TZ_FILE_PATH = "utils/airport_timezones.json"


class Flight:
    """
    A helper class that parses necessary information from JSON received from the Southwest API.

    The flight time is automatically translated from the flight's local timezone to UTC.
    """

    def __init__(self, flight_info: Dict[str, Any], confirmation_number: str) -> None:
        self.confirmation_number = confirmation_number
        self.departure_airport = flight_info["departureAirport"]["name"]
        self.destination_airport = flight_info["arrivalAirport"]["name"]
        self.departure_time = self._get_flight_time(flight_info)

        # Needed for the fare checker
        self.local_departure_time = flight_info["departureTime"]
        self.local_arrival_time = flight_info["arrivalTime"]

    def _get_flight_time(self, flight: Dict[str, Any]) -> datetime:
        flight_date = f"{flight['departureDate']} {flight['departureTime']}"
        departure_airport_code = flight["departureAirport"]["code"]
        airport_timezone = self._get_airport_timezone(departure_airport_code)
        flight_time = self._convert_to_utc(flight_date, airport_timezone)

        return flight_time

    @staticmethod
    def _get_airport_timezone(airport_code: str) -> Any:
        project_dir = os.path.dirname(os.path.dirname(__file__))
        with open(project_dir + "/" + TZ_FILE_PATH) as tz:
            airport_timezones = json.load(tz)

        airport_timezone = pytz.timezone(airport_timezones[airport_code])
        return airport_timezone

    @staticmethod
    def _convert_to_utc(flight_date: str, airport_timezone: Any) -> datetime:
        flight_date = datetime.strptime(flight_date, "%Y-%m-%d %H:%M")
        flight_time = airport_timezone.localize(flight_date)
        utc_time = flight_time.astimezone(pytz.utc).replace(tzinfo=None)

        return utc_time
