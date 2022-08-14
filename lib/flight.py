from __future__ import annotations
from datetime import datetime, timedelta
import time
from threading import Thread
from typing import Any, Dict, TYPE_CHECKING

import pytz
import requests

from .general import CheckInError, make_request, NotificationLevel
if TYPE_CHECKING:
    from account import Account

CHECKIN_URL = "mobile-air-operations/v1/mobile-air-operations/page/check-in/"
MANUAL_CHECKIN_URL = "https://mobile.southwest.com/check-in"


class Flight:
    def __init__(self, account: Account, confirmation_number: str, flight: Dict[str, Any]) -> None:
        self.account = account
        self.confirmation_number = confirmation_number
        self.departure_time: datetime = None
        self.departure_airport: str = None
        self.destination_airport: str = None
        self._get_flight_info(flight)
        x = Thread(target=self._set_check_in)
        x.start()

    def _get_flight_info(self, flight: Dict[str, Any]) -> None:
        self.departure_airport = flight["departureAirport"]["name"]
        self.destination_airport = flight["arrivalAirport"]["name"]
        self.departure_time = self._get_flight_time(flight)

    def _get_flight_time(self, flight: Dict[str, Any]) -> datetime:
        flight_date = f"{flight['departureDate']} {flight['departureTime']}"
        departure_airport_code = flight['departureAirport']['code']
        airport_timezone = self._get_airport_timezone(departure_airport_code)
        flight_time = self._convert_to_utc(flight_date, airport_timezone)

        return flight_time

    @staticmethod
    def _get_airport_timezone(airport_code: str) -> Any:
        airport_info = requests.post("https://openflights.org/php/apsearch.php", data={"iata": airport_code})
        airport_timezone = pytz.timezone(airport_info.json()['airports'][0]['tz_id'])

        return airport_timezone

    @staticmethod
    def _convert_to_utc(flight_date: str, airport_timezone: Any) -> datetime:
        flight_date = datetime.strptime(flight_date, "%Y-%m-%d %H:%M")
        flight_time = airport_timezone.localize(flight_date)
        utc_time = flight_time.astimezone(pytz.utc).replace(tzinfo=None)

        return utc_time

    def _set_check_in(self) -> None:
        # Starts to check in five seconds early in case the Southwest server is ahead of your server
        checkin_time = self.departure_time - timedelta(days = 1, seconds = 5)

        current_time = datetime.utcnow()

        if checkin_time > current_time:
            print(f"Scheduling checkin to flight from '{self.departure_airport}' to '{self.destination_airport}' "
                  f"for {self.account.first_name} {self.account.last_name} at {checkin_time} UTC\n")

            # Refresh headers 10 minutes before to make sure they are valid
            sleep_time = (checkin_time - current_time - timedelta(minutes = 10)).total_seconds()

            # Only try to refresh the headers if the checkin is more than ten minutes away
            if sleep_time > 0:
                time.sleep(sleep_time)
                self.account.refresh_headers()

            current_time = datetime.utcnow()
            sleep_time = (checkin_time - current_time).total_seconds()
            time.sleep(sleep_time)

        self._check_in()
        self.account.flights.remove(self)

    def _check_in(self) -> None:
        account_name = f"{self.account.first_name} {self.account.last_name}"
        print(f"Checking in to flight from '{self.departure_airport}' to '{self.destination_airport}' "
              f"for {account_name}\n")

        headers = self.account.headers
        info = {"first-name": self.account.first_name, "last-name": self.account.last_name}
        site = CHECKIN_URL + self.confirmation_number

        try:
            response = make_request("GET", site, headers, info)

            info = response['checkInViewReservationPage']['_links']['checkIn']
            site = f"mobile-air-operations{info['href']}"

            reservation = make_request("POST", site, headers, info['body'])
        except CheckInError as err:
            # TODO: Kill thread
            error_message = f"Failed to check in to flight {self.confirmation_number} for {account_name}. " \
                            f"Reason: {err}.\nCheck in at this url: {MANUAL_CHECKIN_URL}\n"

            self.account.send_notification(error_message, NotificationLevel.ERROR)
            print(error_message)
            return

        self._send_results(reservation['checkInConfirmationPage'])

    # Sends the results to the console and any notification services if they are enabled
    def _send_results(self, boarding_pass: Dict[str, Any]) -> None:
        success_message = f"Successfully checked in to flight from '{self.departure_airport}' to " \
                          f"'{self.destination_airport}' for {self.account.first_name} {self.account.last_name}!\n"

        for flight in boarding_pass['flights']:
            for passenger in flight['passengers']:
                success_message += f"{passenger['name']} got {passenger['boardingGroup']}{passenger['boardingPosition']}!\n"

        self.account.send_notification(success_message, NotificationLevel.INFO)
        print(success_message)
