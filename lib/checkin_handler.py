from __future__ import annotations

import os
import queue
import signal
import threading
import time
from datetime import datetime, timedelta
from multiprocessing import Lock, Process
from typing import TYPE_CHECKING, Any

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
    from .flight import Flight

# Type alias for JSON
JSON = dict[str, Any]

CHECKIN_URL = "mobile-air-operations/v1/mobile-air-operations/page/check-in/"
MANUAL_CHECKIN_URL = "https://mobile.southwest.com/check-in"

# Should only be relevant for same day flights
MAX_CHECK_IN_ATTEMPTS = 10
# Number of threads to use for check-in
CHECK_IN_THREADS = 5

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
        # Check-in is 24 hours before the flight departs
        checkin_time = self.flight.departure_time - timedelta(days=1)

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

    def _safe_sleep(self, total_sleep_time: float) -> None:
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

        Starts CHECK_IN_THREADS threads to check in for potentially faster check-ins.
        """
        print(
            f"Checking in to flight from '{self.flight.departure_airport}' to "
            f"'{self.flight.destination_airport}' for {self.first_name} {self.last_name}\n"
        )  # Don't log as it has sensitive information

        # Start CHECK_IN_THREADS threads to check in, each sleeping one second longer than the
        # previous thread. This is to increase the likelihood of a successful check-in on the first
        # attempt (otherwise a 400 error could be received, and the request could take up to 3
        # seconds to finish before the next one is attempted).
        result_queue = queue.Queue()
        threads = []
        for i in range(CHECK_IN_THREADS):
            logger.debug("Starting thread with sleep time %d", i)
            thread = threading.Thread(target=self._thread_check_in, args=(result_queue, i))
            threads.append(thread)
            thread.start()

        logger.debug("All threads started. Waiting for them to finish")
        for thread in threads:
            thread.join()
        logger.debug("All threads completed. Checking their results")

        # Check all results from the threads. The loop will end early when a successful check-in or
        # an AirportCheckInError is received. If a RequestError is received, the loop will continue
        # until the results of all threads have been checked and `request_err` will be the last
        # RequestError received.
        request_err = None
        while not result_queue.empty():
            result = result_queue.get_nowait()

            if isinstance(result, dict):
                # Received a successful check-in
                logger.debug("A successful check-in was received")
                self.notification_handler.successful_checkin(
                    result["checkInConfirmationPage"], self.flight
                )
                return
            if isinstance(result, AirportCheckInError):
                # Received an airport check-in error. Don't need to check any more results
                # as the rest should have the same result
                logger.debug("Failed to check in. Airport check-in is required")
                self.notification_handler.airport_checkin_required(self.flight)
                return

            if isinstance(result, RequestError):
                # Received a request error. Store it and continue checking the other results
                logger.debug("Received request error: %s", result)
                request_err = result
            else:
                raise ValueError(f"Unexpected result in result queue: {result}")

        # Handle the RequestError at this point
        logger.debug("Failed to check in. Error: %s. Exiting", request_err)
        self.notification_handler.failed_checkin(request_err, self.flight)

    def _thread_check_in(self, result_queue: queue.Queue, sleep_time: int) -> None:
        """
        Check in to the flight after sleeping for `sleep_time` seconds. Puts the result in the
        `result_queue`. Should be run in each check-in thread.
        """
        time.sleep(sleep_time)

        try:
            reservation = self._attempt_check_in()
            result_queue.put(reservation)
        except (AirportCheckInError, RequestError) as err:
            result_queue.put(err)

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

        expected_flights = 1
        if self.flight.is_same_day:
            logger.debug("Checking in same-day flight")
            expected_flights = 2

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

        logger.debug("Making first POST request to check in")
        # Don't randomly sleep during the check-in requests to have them go through more quickly
        response = make_request("POST", site, headers, info, random_sleep=False)

        info = response["checkInViewReservationPage"]["_links"]["checkIn"]
        site = f"mobile-air-operations{info['href']}"

        logger.debug("Making second POST request to check in")
        reservation = make_request("POST", site, headers, info["body"], random_sleep=False)
        return reservation
