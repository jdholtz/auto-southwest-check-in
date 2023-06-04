import sys
import time
from datetime import datetime
from typing import Any, Dict, List

from .checkin_scheduler import CheckInScheduler
from .config import Config
from .fare_checker import FareChecker
from .log import get_logger
from .notification_handler import NotificationHandler
from .utils import FlightChangeError, LoginError, RequestError
from .webdriver import WebDriver

BAD_REQUESTS_CODE = 429

logger = get_logger(__name__)


class FlightRetriever:
    """
    Retrieve flights based on the information (reservation info or login credentials)
    provided.
    """

    def __init__(self, config: Config, first_name: str = None, last_name: str = None) -> None:
        self.first_name = first_name
        self.last_name = last_name

        self.config = config
        self.notification_handler = NotificationHandler(self)
        self.checkin_scheduler = CheckInScheduler(self)

    def monitor_flights(self, flights: List[Dict[str, Any]]) -> None:
        """
        Check for lower fares every X hours (retrieval interval). Will exit
        when no more flights are scheduled.
        """
        self._schedule_reservations(flights)

        while True:
            time_before = datetime.utcnow()
            self.checkin_scheduler.remove_departed_flights()
            self._check_flight_fares()

            if len(self.checkin_scheduler.flights) <= 0:
                logger.debug("No more flights are scheduled. Exiting...")
                break

            if self.config.retrieval_interval <= 0:
                logger.debug(
                    "Monitoring flights for lower fares is disabled as retrieval interval is 0"
                )
                break

            self._smart_sleep(time_before)
            # Ensure we have valid headers before the next cycle
            self.checkin_scheduler.refresh_headers()

    def _schedule_reservations(self, flights: List[Dict[str, Any]]) -> None:
        logger.debug("Scheduling reservations for %d flights", len(flights))
        confirmation_numbers = []

        for flight in flights:
            confirmation_numbers.append(flight["confirmationNumber"])

        self.checkin_scheduler.schedule(confirmation_numbers)

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


class AccountFlightRetriever(FlightRetriever):
    """
    Helper class used to retrieve flights in an interval when login credentials
    are provided.
    """

    def __init__(self, config: Config, username: str, password: str) -> None:
        self.username = username
        self.password = password
        super().__init__(config)

    def monitor_account(self) -> None:
        """
        Check for newly booked flights to check in for the account every
        X hours (retrieval interval). Monitoring can be turned off by
        providing a value of 0 for the 'retrieval_interval' field in the
        configuration file.
        """
        while True:
            time_before = datetime.utcnow()

            flights = self._get_flights()
            self._schedule_reservations(flights)
            self.checkin_scheduler.remove_departed_flights()
            self._check_flight_fares()

            if self.config.retrieval_interval <= 0:
                logger.debug("Account monitoring is disabled as retrieval interval is 0")
                break

            self._smart_sleep(time_before)

    def _get_flights(self) -> List[Dict[str, Any]]:
        logger.debug("Retrieving flights for account")
        webdriver = WebDriver(self.checkin_scheduler)

        try:
            flights = webdriver.get_flights(self)
        except LoginError as err:
            if err.status_code == BAD_REQUESTS_CODE:
                # Don't exit when a Bad Request error happens. Instead, just skip the retrieval
                # until the next time.
                logger.warning(
                    "Encountered a bad request error while logging in. Skipping flight retrieval"
                )
                return []

            logger.debug("Error logging in. %s. Exiting", err)
            self.notification_handler.failed_login(err)
            sys.exit()

        logger.debug("Successfully retrieved %d flights", len(flights))
        return flights
