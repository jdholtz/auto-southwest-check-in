import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

from .checkin_scheduler import CheckInScheduler
from .config import Config
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

    def __init__(self, config: Config, first_name: str = None, last_name: str = None) -> None:
        self.first_name = first_name
        self.last_name = last_name

        self.config = config
        self.notification_handler = NotificationHandler(self)
        self.checkin_scheduler = CheckInScheduler(self)

    def monitor(self, reservations: List[Dict[str, Any]]) -> None:
        """
        Check for reservation changes and lower fares every X hours (retrieval interval).
        Will exit when no more flights are scheduled for check-in.
        """
        while True:
            time_before = datetime.utcnow()

            # Ensure we have valid headers
            self.checkin_scheduler.refresh_headers()

            # Schedule the reservations every time in case a flight is changed or cancelled
            self._schedule_reservations(reservations)

            if len(self.checkin_scheduler.flights) <= 0:
                logger.debug("No more flights are scheduled for check-in. Exiting...")
                break

            self._check_flight_fares()

            if self.config.retrieval_interval <= 0:
                logger.debug(
                    "Monitoring reservations for lower fares is disabled as retrieval interval is 0"
                )
                break

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
            except RequestError as err:
                logger.error("Requesting error during fare check. %s. Skipping...", err)
            except FlightChangeError as err:
                logger.debug("%s. Skipping fare check", err)
            except Exception as err:
                logger.exception("Unexpected error during fare check: %s", repr(err))

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


class AccountMonitor(ReservationMonitor):
    """Monitor an account for newly booked reservations"""

    def __init__(self, config: Config, username: str, password: str) -> None:
        self.username = username
        self.password = password
        super().__init__(config)

    def monitor(self) -> None:
        """
        Check for newly booked reservations for the account every
        X hours (retrieval interval).
        """
        while True:
            time_before = datetime.utcnow()
            reservations, skip_scheduling = self._get_reservations()

            if not skip_scheduling:
                self._schedule_reservations(reservations)
                self._check_flight_fares()

            if self.config.retrieval_interval <= 0:
                logger.debug("Account monitoring is disabled as retrieval interval is 0")
                break

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
