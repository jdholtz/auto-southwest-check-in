from typing import Any, Dict, List

from .config import Config
from .flight import Flight
from .general import CheckInError, make_request, NotificationLevel
from .webdriver import WebDriver

import apprise

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
        self.config = Config()

    def get_flights(self) -> None:
        prev_flight_len = len(self.flights)

        webdriver = WebDriver()
        reservations = webdriver.get_info(self)

        for reservation in reservations:
            confirmation_number = reservation['confirmationNumber']
            self._get_reservation_info(confirmation_number)

        self._send_new_flight_notifications(prev_flight_len)

    def get_checkin_info(self, confirmation_number: str) -> None:
        prev_flight_len = len(self.flights)

        self.refresh_headers()
        self._get_reservation_info(confirmation_number)

        self._send_new_flight_notifications(prev_flight_len)

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
            self.send_notification(error_message, NotificationLevel.ERROR)
            print(error_message)
            return

        # If multiple flights are under the same confirmation number, it will schedule all checkins one by one
        flight_info = response['viewReservationViewPage']['bounds']

        for flight in flight_info:
            # if not flight in self.flights: // TODO: This doesn't work. Add a function to make sure it only schedules if it isn't already added
            if flight['departureStatus'] != "DEPARTED":
                flight = Flight(self, confirmation_number, flight)
                self.flights.append(flight)

    # Sends new flight notifications to the user. It detects new flights by getting every scheduled flight after
    # the previous length of the flights list.
    def _send_new_flight_notifications(self, prev_flight_len: int) -> None:
        if len(self.flights) == prev_flight_len:
            # Don't send any notifications if no new flights have been scheduled
            return

        flight_schedule_message = f"Successfully scheduled the following flights to check in for {self.first_name} {self.last_name}:\n"
        for flight in self.flights[prev_flight_len:]:
            flight_schedule_message += f"Flight from {flight.departure_airport} to {flight.destination_airport} at {flight.departure_time} UTC\n"

        self.send_notification(flight_schedule_message, NotificationLevel.INFO)

    def send_notification(self, body: str, level: int = None) -> None:
        if len(self.config.notification_urls) == 0:
            # Notification config is not set up
            return

        # Check the level to see if we still want to send it. If level is none, it means
        # the message will always be printed. For example, this is used when testing notifications.
        if level and level < self.config.notification_level:
            return

        title = "Auto Southwest Check-in Script"

        apobj = apprise.Apprise(self.config.notification_urls)
        apobj.notify(
            title = title,
            body = body,
            body_format = apprise.NotifyFormat.TEXT
        )
