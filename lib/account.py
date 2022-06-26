from typing import Optional

from .config import Config
from .flight import Flight
from .general import CheckInError, make_request
from .webdriver import WebDriver

import apprise

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
        self.config = Config()


    def get_flights(self) -> None:
        webdriver = WebDriver()
        reservations = webdriver.get_info(self)

        flight_schedule_message = f"Scheduling the following flights to check in for {self.first_name} {self.last_name}:\n"
        for reservation in reservations:
            confirmation_number = reservation['confirmationNumber']
            flight_schedule_message += self._get_reservation_info(confirmation_number)

        # Only send the message if new flights were scheduled
        if flight_schedule_message.count('\n') > 1:
            self.send_notification(flight_schedule_message)

    def get_checkin_info(self, confirmation_number: str) -> None:
        self.refresh_headers()

        flight_schedule_message = f"Scheduling the following flights to check in for {self.first_name} {self.last_name}:\n"
        flight_schedule_message += self._get_reservation_info(confirmation_number)

        # Only send the message if new flights were scheduled
        if flight_schedule_message.count('\n') > 1:
            self.send_notification(flight_schedule_message)

    def refresh_headers(self) -> None:
        webdriver = WebDriver()
        self.headers = webdriver.get_info()

    def _get_reservation_info(self, confirmation_number: str) -> None:
        info = {"first-name": self.first_name, "last-name": self.last_name}
        site = VIEW_RESERVATION_URL + confirmation_number

        try:
            response = make_request("GET", site, self.headers, info)
        except CheckInError as err:
            error_message = f"Failed to retrieve reservation for {self.first_name} {self.last_name} " \
                            f"with confirmation number {confirmation_number}. Reason: {err}.\n" \
                            f"Make sure the flight information is correct and try again."
            self.send_notification(error_message)
            print(error_message)
            return

        # If multiple flights are under the same confirmation number, it will schedule all checkins one by one
        flight_info = response['viewReservationViewPage']['bounds']

        flight_schedule_message = ""
        for flight in flight_info:
            # if not flight in self.flights: // TODO: This doesn't work. Add a function to make sure it only schedules if it isn't already added
            if flight['departureStatus'] != "DEPARTED":
                flight = Flight(self, confirmation_number, flight)
                self.flights.append(flight)
                flight_schedule_message += f"Flight from {flight.departure_airport} to {flight.destination_airport} at {flight.departure_time} UTC\n"

        return flight_schedule_message

    def send_notification(self, body: str) -> None:
        if len(self.config.notification_urls) == 0:
            # Notification config is not set up
            return

        title = "Auto Southwest Check-in Script"

        apobj = apprise.Apprise(self.config.notification_urls)
        apobj.notify(title=title, body=body)
