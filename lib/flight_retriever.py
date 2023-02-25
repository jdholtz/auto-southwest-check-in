import logging
import sys
import time
from datetime import datetime
from typing import Any, Dict, List

from .checkin_scheduler import CheckInScheduler
from .config import Config
from .general import LoginError
from .notification_handler import NotificationHandler
from .webdriver import WebDriver

logger = logging.getLogger(__name__)


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

    def schedule_reservations(self, flights: List[Dict[str, Any]]) -> None:
        logger.debug("Scheduling reservations for %d flights", len(flights))
        confirmation_numbers = []

        for flight in flights:
            confirmation_numbers.append(flight["confirmationNumber"])

        self.checkin_scheduler.schedule(confirmation_numbers)


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
        # Convert hours to seconds
        retrieval_interval = self.config.retrieval_interval * 60 * 60

        while True:
            time_before = datetime.utcnow()

            flights = self._get_flights()
            self.schedule_reservations(flights)
            self.checkin_scheduler.remove_departed_flights()

            if retrieval_interval <= 0:
                logger.debug("Account monitoring is disabled as retrieval interval is 0")
                break

            # Account for the time it takes to retrieve the flights when
            # deciding how long to sleep
            time_after = datetime.utcnow()
            time_taken = (time_after - time_before).total_seconds()
            sleep_time = retrieval_interval - time_taken
            logger.debug("Sleeping for %d seconds", sleep_time)
            time.sleep(sleep_time)

    def _get_flights(self) -> List[Dict[str, Any]]:
        logger.debug("Retrieving flights for account")
        webdriver = WebDriver(self.checkin_scheduler)

        try:
            flights = webdriver.get_flights(self)
        except LoginError as err:
            logger.debug("Error logging in. %s. Exiting", err)
            self.notification_handler.failed_login(err)
            sys.exit()

        logger.debug("Successfully retrieved %d flights", len(flights))
        return flights
