from __future__ import annotations

import time
from datetime import datetime, timedelta
from multiprocessing import Process
from typing import TYPE_CHECKING

from .flight import Flight
from .log import get_logger
from .utils import RequestError, make_request

if TYPE_CHECKING:
    from .checkin_scheduler import CheckInScheduler

CHECKIN_URL = "mobile-air-operations/v1/mobile-air-operations/page/check-in/"
MANUAL_CHECKIN_URL = "https://mobile.southwest.com/check-in"

logger = get_logger(__name__)


class CheckInHandler:
    """
    Handles checking in for a single flight.

    Sleeps until the flight's check-in time and then attempts the check in.
    """

    def __init__(self, checkin_scheduler: CheckInScheduler, flight: Flight) -> None:
        self.checkin_scheduler = checkin_scheduler
        self.flight = flight
        self.process = Process(target=self._set_check_in)

        self.notification_handler = checkin_scheduler.notification_handler
        self.first_name = checkin_scheduler.reservation_monitor.first_name
        self.last_name = checkin_scheduler.reservation_monitor.last_name

    def schedule_check_in(self) -> None:
        logger.debug("Scheduling check-in for current flight")
        self.process.start()

    def stop_check_in(self) -> None:
        logger.debug("Stopping check-in for current flight")
        self.process.terminate()

    def _set_check_in(self) -> None:
        # Starts to check in five seconds early in case the Southwest server is ahead of your server
        checkin_time = self.flight.departure_time - timedelta(days=1, seconds=5)
        self._wait_for_check_in(checkin_time)
        self._check_in()

    def _wait_for_check_in(self, checkin_time: datetime) -> None:
        current_time = datetime.utcnow()
        if checkin_time <= current_time:
            logger.debug("Check-in time has passed. Going straight to check-in")
            return

        # Refresh headers 10 minutes before to make sure they are valid
        sleep_time = (checkin_time - current_time - timedelta(minutes=10)).total_seconds()

        # Only try to refresh the headers if the check-in is more than ten minutes away
        if sleep_time > 0:
            logger.debug("Sleeping until ten minutes before check-in...")
            self.safe_sleep(sleep_time)
            self.checkin_scheduler.refresh_headers()

        current_time = datetime.utcnow()
        sleep_time = (checkin_time - current_time).total_seconds()
        logger.debug("Sleeping until check-in: %d seconds...", sleep_time)
        time.sleep(sleep_time)

    def safe_sleep(self, total_sleep_time: int) -> None:
        """
        If the total sleep time is too long, an overflow error could occur.
        Therefore, the script will continuously sleep in two week periods
        to avoid this issue.
        """
        two_weeks = 60 * 60 * 24 * 14
        while total_sleep_time > 0:
            sleep_time = min(total_sleep_time, two_weeks)
            time.sleep(sleep_time)
            total_sleep_time -= sleep_time

    def _check_in(self) -> None:
        """
        First, make a GET request to get the needed check-in information. Then, make
        a POST request to submit the check in.
        """
        account_name = f"{self.first_name} {self.last_name}"
        logger.debug("Attempting to check in")
        print(
            f"Checking in to flight from '{self.flight.departure_airport}' to "
            f"'{self.flight.destination_airport}' for {account_name}\n"
        )  # Don't log as it has sensitive information

        headers = self.checkin_scheduler.headers
        info = {
            "first-name": self.first_name,
            "last-name": self.last_name,
        }
        site = CHECKIN_URL + self.flight.confirmation_number

        try:
            logger.debug("Making GET request to check in")
            response = make_request("GET", site, headers, info)

            info = response["checkInViewReservationPage"]["_links"]["checkIn"]
            site = f"mobile-air-operations{info['href']}"

            logger.debug("Making POST request to check in")
            reservation = make_request("POST", site, headers, info["body"])
        except RequestError as err:
            logger.debug("Failed to check in. Error: %s. Exiting", err)
            self.notification_handler.failed_checkin(err, self.flight)
            return

        logger.debug("Successfully checked in!")
        self.notification_handler.successful_checkin(
            reservation["checkInConfirmationPage"], self.flight
        )
