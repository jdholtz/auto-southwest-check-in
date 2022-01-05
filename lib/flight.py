from __future__ import annotations
from datetime import datetime, timedelta
import time
from threading import Thread
from typing import Any, Dict, Optional, TYPE_CHECKING

import pytz
import requests

from .general import make_request
if TYPE_CHECKING:
    from account import Account

CHECKIN_URL = "mobile-air-operations/v1/mobile-air-operations/page/check-in/"


class Flight:
    def __init__(self, account: Optional[Account], confirmation_number: str, flight: Flight) -> None:
        self.account = account
        self.confirmation_number = confirmation_number
        self.departure_time = None
        self.departure_airport = None
        self.destination_airport = None
        self._get_flight_info(flight)
        x = Thread(target=self._set_check_in)
        x.start()

    def _get_flight_info(self, flight: Flight) -> None:
        self.departure_airport = flight["departureAirport"]["name"]
        self.destination_airport = flight["arrivalAirport"]["name"]
        self.departure_time = self._get_flight_time(flight)

    def _get_flight_time(self, flight: Flight) -> datetime:
        flight_date = f"{flight['departureDate']} {flight['departureTime']}"
        departure_airport_code = flight['departureAirport']['code']
        airport_timezone = self._get_airport_timezone(departure_airport_code)
        flight_time = self._convert_to_utc(flight_date, airport_timezone)

        return flight_time

    def _get_airport_timezone(self, airport_code: str) -> Any:
        airport_info = requests.post("https://openflights.org/php/apsearch.php", data={"iata": airport_code})
        airport_timezone = pytz.timezone(airport_info.json()['airports'][0]['tz_id'])

        return airport_timezone

    def _convert_to_utc(self, flight_date: str, airport_timezone: Any) -> datetime:
        flight_date = datetime.strptime(flight_date, "%Y-%m-%d %H:%M")
        flight_time = airport_timezone.localize(flight_date)
        utc_time = flight_time.astimezone(pytz.utc).replace(tzinfo=None)

        return utc_time

    def _set_check_in(self) -> None:
        # Starts to check in five seconds early in case the Southwest server is ahead of your server
        checkin_time = self.departure_time - timedelta(days=1, seconds=5)

        current_time = datetime.utcnow()

        if checkin_time > current_time:
            print(f"Scheduling checkin to flight from '{self.departure_airport}' to '{self.destination_airport}' "
                  f"for {self.account.first_name} {self.account.last_name} at {checkin_time} UTC\n")

            # Refresh headers 10 minutes before to make sure they are valid
            sleep_time = (checkin_time - current_time - timedelta(minutes=10)).total_seconds()

            # Only try to refresh the headers if the checkin is more than ten minutes away
            if sleep_time > 0:
                time.sleep(sleep_time)

                # Check if the check in was started manually or from logging in
                # To-Do: Make one function to retrieve headers
                if self.account.username is None:
                    self.account.get_checkin_info(self.confirmation_number)
                else:
                    self.account.get_flights()

            current_time = datetime.utcnow()
            sleep_time = (checkin_time - current_time).total_seconds()
            time.sleep(sleep_time)

        self._check_in()
        self.account.flights.remove(self)

    def _check_in(self) -> None:
        print(f"Checking in to flight from '{self.departure_airport}' to '{self.destination_airport}' "
              f"for {self.account.first_name} {self.account.last_name}\n")

        info = {"first-name": self.account.first_name, "last-name": self.account.last_name}
        site = CHECKIN_URL + self.confirmation_number

        response = make_request("GET", site, self.account, info)

        info = response['checkInViewReservationPage']['_links']['checkIn']
        site = f"mobile-air-operations{info['href']}"

        reservation = make_request("POST", site, self.account, info['body'])
        self._print_results(reservation['checkInConfirmationPage'])

    def _print_results(self, boarding_pass: Dict[str, Any]) -> None:
        print(f"Successfully checked in to flight from '{self.departure_airport}' to '{self.destination_airport}'!")
        for flight in boarding_pass['flights']:
            for passenger in flight['passengers']:
                print(f"{passenger['name']} got {passenger['boardingGroup']}{passenger['boardingPosition']}!")
        print()
