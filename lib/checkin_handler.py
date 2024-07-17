from __future__ import annotations

import os
import signal
import time
from datetime import datetime, timedelta
from multiprocessing import Lock, Process
from typing import TYPE_CHECKING, Any, Dict

from .flight import Flight
from .log import get_logger
from .utils import (
    AirportCheckInError,
    DriverTimeoutError,
    RequestError,
    get_current_time,
    make_request,
)

if TYPE_CHECKING:
    from .checkin_scheduler import CheckInScheduler

# Type alias for JSON
JSON = Dict[str, Any]

CHECKIN_URL = "mobile-air-operations/v1/mobile-air-operations/page/check-in/"
MANUAL_CHECKIN_URL = "https://mobile.southwest.com/check-in"

# Should only be relevant for same day flights
MAX_CHECK_IN_ATTEMPTS = 10

logger = get_logger(__name__)


class CheckInHandler:
    """
    Handles checking in for a single flight.

    Sleeps until the flight's check-in time and then attempts the check in.
    """

    def __init__(self, checkin_scheduler: CheckInScheduler, flight: Flight, lock: Lock) -> None:
        self.checkin_scheduler = checkin_scheduler
        self.flight = flight
        self.lock = lock
        self.pid = None

        self.notification_handler = checkin_scheduler.notification_handler
        self.first_name = checkin_scheduler.reservation_monitor.first_name
        self.last_name = checkin_scheduler.reservation_monitor.last_name

    def schedule_check_in(self) -> None:
        logger.debug("Scheduling check-in for current flight")
        process = Process(target=self._set_check_in)
        process.start()
        self.pid = process.pid

    def stop_check_in(self) -> None:
        """
        Terminate the check-in process by killing its process ID. The process can't
        be directly terminated with process.terminate() as the process object cannot
        be pickled (necessary when using multiprocessing's 'spawn' start method).
        """
        logger.debug("Stopping check-in for current flight")

        try:
            logger.debug("Killing process with PID %d", self.pid)
            os.kill(self.pid, signal.SIGTERM)

            # Wait so zombie (defunct) processes are not created
            logger.debug("Waiting for process with PID %d to be terminated", self.pid)
            os.waitpid(self.pid, 0)
        except (ChildProcessError, PermissionError):
            # Processes are handled differently in Windows
            pass

        logger.debug("Process with PID %d successfully terminated", self.pid)

    def _set_check_in(self) -> None:
        # Starts to check in five seconds early in case the Southwest server is ahead of your server
        checkin_time = self.flight.departure_time - timedelta(days=1, seconds=5)

        try:
            self._wait_for_check_in(checkin_time)
            self._check_in()
        except KeyboardInterrupt:
            # This is handled in the Reservation Monitor attached to this Checkin Handler
            pass

    def _wait_for_check_in(self, checkin_time: datetime) -> None:
        current_time = get_current_time()
        if checkin_time <= current_time:
            logger.debug("Check-in time has passed. Going straight to check-in")
            return

        # Refresh headers 30 minutes before to make sure they are valid
        sleep_time = (checkin_time - current_time - timedelta(minutes=30)).total_seconds()

        # Only try to refresh the headers if the check-in is more than thirty minutes away
        if sleep_time > 0:
            logger.debug("Sleeping until thirty minutes before check-in...")
            self._safe_sleep(sleep_time)

            # Lock to ensure multiple checkin handlers aren't refreshing headers
            # at the same time (the webdriver doesn't work well with concurrency)
            logger.debug("Acquiring lock...")
            with self.lock:
                logger.debug("Lock acquired")
                try:
                    self.checkin_scheduler.refresh_headers()
                except DriverTimeoutError:
                    logger.debug("Timeout while refreshing headers before check-in")
                    self.notification_handler.timeout_before_checkin(self.flight)

            logger.debug("Lock released")
            current_time = get_current_time()

        sleep_time = (checkin_time - current_time).total_seconds()
        logger.debug("Sleeping until check-in: %d seconds...", sleep_time)
        time.sleep(sleep_time)

    def _safe_sleep(self, total_sleep_time: int) -> None:
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
        Checks into a flight. Will catch any errors that occur during the check-in process.
        """
        print(
            f"Checking in to flight from '{self.flight.departure_airport}' to "
            f"'{self.flight.destination_airport}' for {self.first_name} {self.last_name}\n"
        )  # Don't log as it has sensitive information

        try:
            reservation = self._attempt_check_in()
        except AirportCheckInError:
            logger.debug("Failed to check in. Airport check-in is required")
            self.notification_handler.airport_checkin_required(self.flight)
            return
        except RequestError as err:
            logger.debug("Failed to check in. Error: %s. Exiting", err)
            self.notification_handler.failed_checkin(err, self.flight)
            return

        self.notification_handler.successful_checkin(
            reservation["checkInConfirmationPage"], self.flight
        )

    def _attempt_check_in(self) -> JSON:
        """
        Keeps attempting to check in until all flights are checked in. This should
        succeed after one attempt for non-same-day flights, but is necessary for
        same-day flights.

        For same-day flights: since the check-in is started early, the submission will
        go through for the previous flight, but the flight attached to this handler will
        not have been checked in yet. Therefore, this function keeps attempting to check
        in until both flights have checked in.
        """
        logger.debug("Attempting to check in")
        expected_flights = 2 if self.flight.is_same_day else 1

        attempts = 0
        while attempts < MAX_CHECK_IN_ATTEMPTS:
            attempts += 1

            reservation = self._check_in_to_flight()
            flights = reservation["checkInConfirmationPage"]["flights"]
            if len(flights) >= expected_flights:
                logger.debug("Successfully checked in after %d attempts", attempts)
                return reservation

            logger.debug(
                "Same-day flight has not been checked in yet. Waiting 1 second and trying again"
            )
            time.sleep(1)

        logger.debug("Same-day flight failed to check in after %d attempts", MAX_CHECK_IN_ATTEMPTS)
        raise RequestError("Too many attempts during check-in")

    def _check_in_to_flight(self) -> JSON:
        """
        First, initiate a POST request to get the needed check-in information. Subsequently, execute
        another POST request to submit the check in.
        """
        headers = self.checkin_scheduler.headers
        info = {
            "firstName": self.first_name,
            "lastName": self.last_name,
            "passengerSearchToken": "",
            "recordLocator": self.flight.confirmation_number,
        }
        site = CHECKIN_URL + self.flight.confirmation_number

        logger.debug("Making POST request to check in")
        response = make_request("POST", site, headers, info, random_sleep=False)

        info = response["checkInViewReservationPage"]["_links"]["checkIn"]
        site = f"mobile-air-operations{info['href']}"

        logger.debug("Making POST request to check in")
        # Don't randomly sleep during this request to have it go through more quickly
        reservation = make_request("POST", site, headers, info["body"], random_sleep=False)
        return reservation
