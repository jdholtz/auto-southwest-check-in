import time
from datetime import datetime
from typing import Any, Dict, List

from .checkin_scheduler import CheckInScheduler
from .config import Config
from .notification_handler import NotificationHandler
from .webdriver import WebDriver


class FlightRetriever:
    """
    Retrieve flights based on the information (reservation info or login credentials)
    provided.
    """

    def __init__(self, first_name: str = None, last_name: str = None) -> None:
        self.first_name = first_name
        self.last_name = last_name

        self.config = Config()
        self.notification_handler = NotificationHandler(self)
        self.checkin_scheduler = CheckInScheduler(self)

    def schedule_reservations(self, flights: List[Dict[str, Any]]) -> None:
        confirmation_numbers = []

        for flight in flights:
            confirmation_numbers.append(flight["confirmationNumber"])

        self.checkin_scheduler.schedule(confirmation_numbers)


class AccountFlightRetriever(FlightRetriever):
    """
    Helper class used to retrieve flights in an interval when login credentials
    are provided.
    """

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        super().__init__()

    def monitor_account(self) -> None:
        # Convert hours to seconds
        # TODO: Don't loop if retrieval_interval is 0
        retrieval_interval = self.config.retrieval_interval * 60 * 60

        while True:
            time_before = datetime.utcnow()

            flights = self._get_flights()
            self.schedule_reservations(flights)
            self.checkin_scheduler.remove_departed_flights()

            # Account for the time it takes to retrieve the flights when
            # deciding how long to sleep
            time_after = datetime.utcnow()
            time_taken = (time_after - time_before).total_seconds()
            time.sleep(retrieval_interval - time_taken)

    def _get_flights(self) -> List[Dict[str, Any]]:
        webdriver = WebDriver(self.checkin_scheduler)
        flights = webdriver.get_flights(self)
        return flights
