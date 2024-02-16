import multiprocessing
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

from .checkin_scheduler import CheckInScheduler
from .config import AccountConfig, Config
from .fare_checker import FareChecker
from .log import get_logger
from .notification_handler import NotificationHandler
from .utils import FlightChangeError, LoginError, RequestError
from .webdriver import WebDriver

TOO_MANY_REQUESTS_CODE = 429

logger = get_logger(__name__)


class ReservationMonitor:
    """
    A high-level class responsible for monitoring one or more reservations for
    check-ins, flight changes or cancellations, and lower flight fares.
    """

    def __init__(self, config: Config, lock: multiprocessing.Lock = None) -> None:
        self.first_name = config.first_name
        self.last_name = config.last_name

        self.config = config
        self.lock = lock
        self.notification_handler = NotificationHandler(self)
        self.checkin_scheduler = CheckInScheduler(self)

    def start(self) -> None:
        """Start each reservation monitor in a separate process to run them in parallel"""
        process = multiprocessing.Process(target=self.monitor)
        process.start()

    def monitor(self) -> None:
        try:
            self._monitor()
        except KeyboardInterrupt:
            # Add a small delay so the MainThread's message prints first
            time.sleep(0.05)
            # Lock so all processes are stopped sequentially
            with self.lock:
                self._stop_monitoring()

    def _monitor(self) -> None:
        """
        Check for reservation changes and lower fares every X hours (retrieval interval).
        Will exit when no more flights are scheduled for check-in.
        """
        reservation = {"confirmationNumber": self.config.confirmation_number}

        while True:
            time_before = datetime.utcnow()

            logger.debug("Acquiring lock...")
            with self.lock:
                logger.debug("Lock acquired")

                # Ensure there are valid headers
                self.checkin_scheduler.refresh_headers()

                # Schedule the reservations every time in case a flight is changed or cancelled
                self._schedule_reservations([reservation])

                if len(self.checkin_scheduler.flights) <= 0:
                    logger.debug("No more flights are scheduled for check-in. Exiting...")
                    break

                self._check_flight_fares()

                if self.config.retrieval_interval <= 0:
                    logger.debug("Reservation monitoring is disabled as retrieval interval is 0")
                    break

            logger.debug("Lock released")
            self._smart_sleep(time_before)

    def _schedule_reservations(self, reservations: List[Dict[str, Any]]) -> None:
        logger.debug("Scheduling flight check-ins for %d reservations", len(reservations))
        confirmation_numbers = [reservation["confirmationNumber"] for reservation in reservations]
        self.checkin_scheduler.process_reservations(confirmation_numbers)

    def _check_flight_fares(self) -> None:
        if not self.config.check_fares:
            return

        flights = self.checkin_scheduler.flights
        logger.debug("Checking fares for %d flights", len(flights))

        fare_checker = FareChecker(self)
        for flight in flights:
            # If a fare check fails, don't completely exit. Just print the error
            # and continue
            try:
                fare_checker.check_flight_price(flight)
                self.notification_handler.healthchecks_success(
                    f"Successful fare check, confirmation number={flight.confirmation_number}"
                )
            except RequestError as err:
                logger.error("Requesting error during fare check. %s. Skipping...", err)
                self.notification_handler.healthchecks_fail(
                    f"Failed fare check, confirmation number={flight.confirmation_number}"
                )
            except FlightChangeError as err:
                logger.debug("%s. Skipping fare check", err)
                self.notification_handler.healthchecks_success(
                    f"Successful fare check, confirmation number={flight.confirmation_number}"
                )
            except Exception as err:
                logger.exception("Unexpected error during fare check: %s", repr(err))
                self.notification_handler.healthchecks_fail(
                    f"Failed fare check, confirmation number={flight.confirmation_number}"
                )

    def _smart_sleep(self, previous_time: datetime) -> None:
        """
        Account for the time it took to do recurring tasks so the sleep interval
        is the exact time provided in the configuration file.
        """
        current_time = datetime.utcnow()
        time_taken = (current_time - previous_time).total_seconds()
        sleep_time = self.config.retrieval_interval - time_taken
        logger.debug("Sleeping for %d seconds", sleep_time)
        time.sleep(sleep_time)

    def _stop_checkins(self) -> None:
        """
        Stops all check-ins for a monitor. This is called when Ctrl-C is pressed. The
        flight information is not logged because it contains sensitive information.
        """
        for checkin in self.checkin_scheduler.checkin_handlers:
            print(
                f"Cancelling check-in from '{checkin.flight.departure_airport}' to "
                f"'{checkin.flight.destination_airport}' for {self.first_name} {self.last_name}"
            )
            checkin.stop_check_in()

    def _stop_monitoring(self) -> None:
        print(
            f"\nStopping monitoring for reservation with confirmation number "
            f"{self.config.confirmation_number} and name {self.first_name} {self.last_name}"
        )
        self._stop_checkins()


class AccountMonitor(ReservationMonitor):
    """Monitor an account for newly booked reservations"""

    def __init__(self, config: AccountConfig, lock: multiprocessing.Lock) -> None:
        super().__init__(config, lock)
        self.username = config.username
        self.password = config.password

    def _monitor(self) -> None:
        """
        Check for newly booked reservations for the account every X hours (retrieval interval).
        """
        while True:
            time_before = datetime.utcnow()

            logger.debug("Acquiring lock...")
            with self.lock:
                logger.debug("Lock acquired")
                reservations, skip_scheduling = self._get_reservations()

                if not skip_scheduling:
                    self._schedule_reservations(reservations)
                    self._check_flight_fares()

                if self.config.retrieval_interval <= 0:
                    logger.debug("Account monitoring is disabled as retrieval interval is 0")
                    break

            logger.debug("Lock released")
            self._smart_sleep(time_before)

    def _get_reservations(self) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Returns a list of reservations and a boolean indicating if reservation
        scheduling should be skipped.

        Reservation scheduling will be skipped if a Too Many Requests error is encountered
        because new headers might not be valid and a list of reservations could not be retrieved.
        """
        logger.debug("Retrieving reservations for account")
        webdriver = WebDriver(self.checkin_scheduler)

        try:
            reservations = webdriver.get_reservations(self)
        except LoginError as err:
            if err.status_code == TOO_MANY_REQUESTS_CODE:
                # Don't exit when a Too Many Requests error happens. Instead, just skip the
                # retrieval until the next time.
                logger.warning(
                    "Encountered a Too Many Requests error while logging in. Skipping reservation "
                    "retrieval"
                )
                return [], True

            logger.debug("Error logging in. %s. Exiting", err)
            self.notification_handler.failed_login(err)
            sys.exit(1)

        logger.debug("Successfully retrieved %d reservations", len(reservations))
        return reservations, False

    def _stop_monitoring(self) -> None:
        print(f"\nStopping monitoring for account with username {self.username}")
        self._stop_checkins()
