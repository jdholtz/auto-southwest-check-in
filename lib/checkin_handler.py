from __future__ import annotations

import time
from datetime import datetime, timedelta
from multiprocessing import Process
from typing import TYPE_CHECKING

from .flight import Flight
from .general import CheckInError, make_request

if TYPE_CHECKING:  # pragma: no cover
    from .checkin_scheduler import CheckInScheduler

CHECKIN_URL = "mobile-air-operations/v1/mobile-air-operations/page/check-in/"
MANUAL_CHECKIN_URL = "https://mobile.southwest.com/check-in"


class CheckInHandler:
    """
    Handles checking in for a single flight.

    Sleeps until the flight's checkin time and then attempts the check in.
    """

    def __init__(self, checkin_scheduler: CheckInScheduler, flight: Flight) -> None:
        self.checkin_scheduler = checkin_scheduler
        self.flight = flight

        self.notification_handler = self.checkin_scheduler.notification_handler
        self.first_name = self.checkin_scheduler.flight_retriever.first_name
        self.last_name = self.checkin_scheduler.flight_retriever.last_name

    def schedule_check_in(self) -> None:
        process = Process(target=self._set_check_in)
        process.start()

    def _set_check_in(self) -> None:
        # Starts to check in five seconds early in case the Southwest server is ahead of your server
        checkin_time = self.flight.departure_time - timedelta(days=1, seconds=5)
        self._wait_for_check_in(checkin_time)
        self._check_in()

    def _wait_for_check_in(self, checkin_time: datetime) -> None:
        current_time = datetime.utcnow()
        if checkin_time <= current_time:
            return

        # Refresh headers 10 minutes before to make sure they are valid
        sleep_time = (checkin_time - current_time - timedelta(minutes=10)).total_seconds()

        # Only try to refresh the headers if the checkin is more than ten minutes away
        if sleep_time > 0:
            time.sleep(sleep_time)
            self.checkin_scheduler.refresh_headers()

        current_time = datetime.utcnow()
        sleep_time = (checkin_time - current_time).total_seconds()
        time.sleep(sleep_time)

    def _check_in(self) -> None:
        """
        First, make a GET request to get the needed checkin information. Then, make
        a POST request to submit the check in.
        """
        account_name = f"{self.first_name} {self.last_name}"
        print(
            f"Checking in to flight from '{self.flight.departure_airport}' to '{self.flight.destination_airport}' "
            f"for {account_name}\n"
        )

        headers = self.checkin_scheduler.headers
        info = {
            "first-name": self.first_name,
            "last-name": self.last_name,
        }
        site = CHECKIN_URL + self.flight.confirmation_number

        try:
            response = make_request("GET", site, headers, info)

            info = response["checkInViewReservationPage"]["_links"]["checkIn"]
            site = f"mobile-air-operations{info['href']}"

            reservation = make_request("POST", site, headers, info["body"])
        except CheckInError as err:
            self.notification_handler.failed_checkin(err, self.flight)
            return

        self.notification_handler.successful_checkin(
            reservation["checkInConfirmationPage"], self.flight
        )
