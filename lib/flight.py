from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytz

JSON = Dict[str, Any]

TZ_FILE_PATH = "utils/airport_timezones.json"


class Flight:
    """
    A helper class that parses flight information received from the Southwest API.

    The flight time is automatically translated from the flight's local timezone to UTC.
    """

    def __init__(self, flight_info: JSON, reservation_info: JSON, confirmation_number: str) -> None:
        self.confirmation_number = confirmation_number
        self.departure_airport = flight_info["departureAirport"]["name"]
        self.destination_airport = flight_info["arrivalAirport"]["name"]
        self.flight_number = self._get_flight_number(flight_info["flights"])
        self.is_same_day = False

        # Cached for use by the fare checker
        self.reservation_info = reservation_info

        # Track to notify the user of filling out their passport information.
        # Southwest only fills the country's value for international flights
        self.is_international = flight_info["arrivalAirport"]["country"] is not None

        self._local_departure_time = None
        self.departure_time = None
        self._set_flight_time(flight_info)

    def __eq__(self, other: object) -> bool:
        # Define how two flights are equal to each other
        return (
            isinstance(other, Flight)
            and self.flight_number == other.flight_number
            and self.departure_time == other.departure_time
        )

    def get_display_time(self, twenty_four_hr_time: bool) -> str:
        if twenty_four_hr_time:
            time_format = "%H:%M"
        else:
            # The '#' removes leading zeros in Windows and '-' in Linux/Mac
            time_format = "%#I:%M %p" if os.name == "nt" else "%-I:%M %p"

        date_format = f"%Y-%m-%d {time_format} %Z"
        return datetime.strftime(self._local_departure_time, date_format)

    def _set_flight_time(self, flight: JSON) -> None:
        flight_date = f"{flight['departureDate']} {flight['departureTime']}"
        departure_airport_code = flight["departureAirport"]["code"]
        airport_timezone = self._get_airport_timezone(departure_airport_code)
        self.departure_time = self._convert_to_utc(flight_date, airport_timezone)

    def _get_airport_timezone(self, airport_code: str) -> Any:
        project_dir = Path(__file__).parents[1]
        tz_file = project_dir / TZ_FILE_PATH
        airport_timezones = json.loads(tz_file.read_text())

        airport_timezone = pytz.timezone(airport_timezones[airport_code])
        return airport_timezone

    def _convert_to_utc(self, flight_date: str, airport_timezone: Any) -> datetime:
        flight_date = datetime.strptime(flight_date, "%Y-%m-%d %H:%M")
        self._local_departure_time = airport_timezone.localize(flight_date)

        utc_time = self._local_departure_time.astimezone(timezone.utc).replace(tzinfo=None)
        return utc_time

    def _get_flight_number(self, flights: JSON) -> str:
        """
        Formats the flight number in the way that the fare checker expects it, which is with the
        'WN' prefix removed and a slash separating each number with a zero-width space on either
        side.
        """
        flight_number = ""
        for flight in flights:
            # Remove the 'WN' prefix from each flight number
            flight_number += flight["number"].replace("WN", "", 1)
            # Add a slash with a zero-width space on either side
            flight_number += "\u200b/\u200b"

        # Remove any slashes and zero-width spaces from the end
        return flight_number.rstrip("/\u200b")
