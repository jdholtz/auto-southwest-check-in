import json
from pathlib import Path
from typing import Optional

from .flight import Flight
from .general import make_request
from .webdriver import WebDriver

import apprise

CONFIG_FILE_NAME = "config.json"
VIEW_RESERVATION_URL = "mobile-air-booking/v1/mobile-air-booking/page/view-reservation/"


class Account:
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> None:
        self.username = username
        self.password = password
        self.first_name = first_name
        self.last_name = last_name
        self.flights = []
        self.headers = {}
        self.config = {}
        self._get_config()

    def _get_config(self) -> None:
        parent_dir = Path(__file__).parents[1]
        config_file = str(parent_dir) + "/" + CONFIG_FILE_NAME

        try:
            with open(config_file) as file:
                self.config = json.load(file)
        except FileNotFoundError:
            pass

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
            if not flight in self.flights:
                flight = Flight(self, confirmation_number, flight)
                self.flights.append(flight)

    def send_notification(self, body: str) -> None:
        if "notification_urls" not in self.config or len(self.config["notification_urls"]) == 0:
            # Notification config is not set up
            return

        title = "Auto Southwest Check-in Script"

        apobj = apprise.Apprise(self.config["notification_urls"])
        apobj.notify(title=title, body=body)
