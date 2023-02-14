from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

import apprise

from .flight import Flight
from .general import CheckInError, LoginError, NotificationLevel

if TYPE_CHECKING:  # pragma: no cover
    from .flight_retriever import FlightRetriever

MANUAL_CHECKIN_URL = "https://mobile.southwest.com/check-in"


class NotificationHandler:
    """Handles all notifications that will be sent to the user either via Apprise or the console"""

    def __init__(self, flight_retriever: FlightRetriever) -> None:
        self.flight_retriever = flight_retriever
        self.notification_urls = self.flight_retriever.config.notification_urls
        self.notification_level = self.flight_retriever.config.notification_level

    def _get_account_name(self) -> str:
        return f"{self.flight_retriever.first_name} {self.flight_retriever.last_name}"

    def send_notification(self, body: str, level: int = None) -> None:
        print(body)

        # Check the level to see if we still want to send it. If level is none, it means
        # the message will always be printed. For example, this is used when testing notifications.
        if level and level < self.notification_level:
            return

        title = "Auto Southwest Check-in Script"

        apobj = apprise.Apprise(self.notification_urls)
        apobj.notify(title=title, body=body, body_format=apprise.NotifyFormat.TEXT)

    def new_flights(self, flights: List[Flight]) -> None:
        # Don't send notifications if no new flights are scheduled
        if len(flights) == 0:
            return

        flight_schedule_message = f"Successfully scheduled the following flights to check in for {self._get_account_name()}:\n"
        for flight in flights:
            flight_schedule_message += f"Flight from {flight.departure_airport} to {flight.destination_airport} at {flight.departure_time} UTC\n"

        self.send_notification(flight_schedule_message, NotificationLevel.INFO)

    def failed_reservation_retrieval(self, error: CheckInError, confirmation_number: str) -> None:
        error_message = (
            f"Failed to retrieve reservation for {self._get_account_name()} "
            f"with confirmation number {confirmation_number}. Reason: {error}.\n"
            f"Make sure the flight information is correct and try again.\n"
        )
        self.send_notification(error_message, NotificationLevel.ERROR)

    def failed_login(self, error: LoginError) -> None:
        error_message = (
            f"Failed to log in to account with username {self.flight_retriever.username}. "
            f"Status Code: {error}.\nMake sure the login information is correct and try again.\n"
        )
        self.send_notification(error_message, NotificationLevel.ERROR)

    def successful_checkin(self, boarding_pass: Dict[str, Any], flight: Flight) -> None:
        success_message = (
            f"Successfully checked in to flight from '{flight.departure_airport}' to "
            f"'{flight.destination_airport}' for {self._get_account_name()}!\n"
        )

        for flight_info in boarding_pass["flights"]:
            for passenger in flight_info["passengers"]:
                success_message += f"{passenger['name']} got {passenger['boardingGroup']}{passenger['boardingPosition']}!\n"

        self.send_notification(success_message, NotificationLevel.INFO)

    def failed_checkin(self, error: CheckInError, flight: Flight) -> None:
        error_message = (
            f"Failed to check in to flight {flight.confirmation_number} for {self._get_account_name()} "
            f"Reason: {error}.\nCheck in at this url: {MANUAL_CHECKIN_URL}\n"
        )
        self.send_notification(error_message, NotificationLevel.ERROR)
