from typing import Any, Dict, List

from .flight import Flight
from .general import make_request
from .webdriver import WebDriver

VIEW_RESERVATION_URL = "mobile-air-booking/v1/mobile-air-booking/page/view-reservation/"


class Account:
    def __init__(
        self,
        username: str = None,
        password: str = None,
        first_name: str = None,
        last_name: str = None
    ) -> None:
        self.username = username
        self.password = password
        self.first_name = first_name
        self.last_name = last_name
        self.flights: List[Flight] = []
        self.headers: Dict[str, Any] = {}

    def get_flights(self) -> None:
        webdriver = WebDriver()
        reservations = webdriver.get_info(self)

        for reservation in reservations:
            confirmation_number = reservation['confirmationNumber']
            self._get_reservation_info(confirmation_number)

    def get_checkin_info(self, confirmation_number: str) -> None:
        self.refresh_headers()
        self._get_reservation_info(confirmation_number)

    def refresh_headers(self) -> None:
        webdriver = WebDriver()
        self.headers = webdriver.get_info()

    def _get_reservation_info(self, confirmation_number: str) -> None:
        info = {"first-name": self.first_name, "last-name": self.last_name}
        site = VIEW_RESERVATION_URL + confirmation_number

        response = make_request("GET", site, self.headers, info)

        # If multiple flights are under the same confirmation number, it will schedule all checkins one by one
        flight_info = response['viewReservationViewPage']['bounds']

        for flight in flight_info:
            # if not flight in self.flights: // TODO: This doesn't work. Add a function to make sure it only schedules if it isn't already added
            if flight['departureStatus'] != "DEPARTED":
                flight = Flight(self, confirmation_number, flight)
                self.flights.append(flight)
