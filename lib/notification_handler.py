from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

import apprise
import requests

from .flight import Flight
from .log import get_logger
from .utils import LoginError, NotificationLevel, RequestError

if TYPE_CHECKING:
    from .reservation_monitor import ReservationMonitor

MANUAL_CHECKIN_URL = "https://mobile.southwest.com/check-in"
MANAGE_RESERVATION_URL_MOBILE = "https://mobile.southwest.com/view-reservation"
MANAGE_RESERVATION_URL_DESKTOP = "https://www.southwest.com/air/manage-reservation/"

logger = get_logger(__name__)


class NotificationHandler:
    """Handles all notifications that will be sent to the user either via Apprise or the console"""

    def __init__(self, reservation_monitor: ReservationMonitor) -> None:
        self.reservation_monitor = reservation_monitor
        self.notification_urls = reservation_monitor.config.notification_urls
        self.notification_level = reservation_monitor.config.notification_level

    def send_notification(self, body: str, level: NotificationLevel = None) -> None:
        print(body)  # This isn't logged as it contains sensitive information

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

        is_international = False
        twenty_four_hr_time = self.reservation_monitor.config.notification_24_hour_time
        flight_schedule_message = (
            "Successfully scheduled the following flights to check in for "
            f"{self._get_account_name()}:\n"
        )
        for flight in flights:
            flight_time = flight.get_display_time(twenty_four_hr_time)
            flight_schedule_message += (
                f"Flight from {flight.departure_airport} to {flight.destination_airport} on "
                f"{flight_time}\n"
            )
            if flight.is_international:
                is_international = True

        if is_international:
            # Add an extra message for international flights to make sure people fill out their
            # passport information.
            flight_schedule_message += (
                "\nInternational flights were scheduled. Make sure to fill out your passport "
                "information before the check-in date\n"
            )

        logger.debug("Sending new flights notification")
        self.send_notification(flight_schedule_message, NotificationLevel.INFO)

    def failed_reservation_retrieval(self, error: RequestError, confirmation_number: str) -> None:
        error_message = (
            f"Error: Failed to retrieve reservation for {self._get_account_name()} "
            f"with confirmation number {confirmation_number}. Reason: {error}.\n"
            "Make sure the reservation information is correct and try again.\n"
        )
        logger.debug("Sending failed reservation retrieval notification...")
        self.send_notification(error_message, NotificationLevel.ERROR)

    def timeout_during_retrieval(self, monitor_type: str) -> None:
        message = (
            f"Notice: Webdriver time out during {monitor_type} retrieval for "
            f"{self._get_account_name()}. Skipping reservation retrieval until next interval\n"
        )
        self.send_notification(message, NotificationLevel.NOTICE)

    def too_many_requests_during_login(self) -> None:
        message = (
            "Notice: Encountered a Too Many Requests error while logging in for "
            f"{self._get_account_name()}. Skipping reservation retrieval until next interval\n"
        )
        self.send_notification(message, NotificationLevel.NOTICE)

    def failed_login(self, error: LoginError) -> None:
        error_message = (
            "Error: Failed to log in to account with username "
            f"{self.reservation_monitor.username}. {error}.\n"
        )
        logger.debug("Sending failed login notification...")
        self.send_notification(error_message, NotificationLevel.ERROR)

    def successful_checkin(self, boarding_pass: Dict[str, Any], flight: Flight) -> None:
        success_message = (
            f"Successfully checked in to flight from '{flight.departure_airport}' to "
            f"'{flight.destination_airport}' for {self._get_account_name()}!\n"
        )

        for flight_info in boarding_pass["flights"]:
            for passenger in flight_info["passengers"]:
                if passenger["boardingGroup"] is not None:
                    success_message += (
                        f"{passenger['name']} got "
                        f"{passenger['boardingGroup']}{passenger['boardingPosition']}!\n"
                    )

        logger.debug("Sending successful check-in notification...")
        self.send_notification(success_message, NotificationLevel.INFO)

    def failed_checkin(self, error: RequestError, flight: Flight) -> None:
        error_message = (
            f"Error: Failed to check in to flight {flight.confirmation_number} for "
            f"{self._get_account_name()}. Reason: {error}.\nCheck in at this url: "
            f"{MANUAL_CHECKIN_URL}\n"
        )
        logger.debug("Sending failed check-in notification...")
        self.send_notification(error_message, NotificationLevel.ERROR)

    def airport_checkin_required(self, flight: Flight) -> None:
        error_message = (
            f"Error: Airport check-in is required for flight {flight.confirmation_number} for "
            f"{self._get_account_name()}.\n"
        )
        logger.debug("Sending airport check-in required notification...")
        self.send_notification(error_message, NotificationLevel.ERROR)

    def timeout_before_checkin(self, flight: Flight) -> None:
        twenty_four_hr_time = self.reservation_monitor.config.notification_24_hour_time
        flight_time = flight.get_display_time(twenty_four_hr_time)

        error_message = (
            "Error: Timed out waiting for headers before check-in. Check-in to flight "
            f"{flight.confirmation_number} for {self._get_account_name()} at {flight_time} may "
            "fail.\n"
        )
        logger.debug("Sending timeout before check-in notification...")
        self.send_notification(error_message, NotificationLevel.ERROR)

    def lower_fare(self, flight: Flight, price_info: str) -> None:
        twenty_four_hr_time = self.reservation_monitor.config.notification_24_hour_time
        flight_time = flight.get_display_time(twenty_four_hr_time)

        message = (
            f"Found lower fare of {price_info} for flight {flight.confirmation_number} "
            f"from '{flight.departure_airport}' to '{flight.destination_airport}' on {flight_time} "
            f"for {self._get_account_name()}!\nManage your reservation here: "
            f"{MANAGE_RESERVATION_URL_MOBILE} or {MANAGE_RESERVATION_URL_DESKTOP}\n"
        )
        logger.debug("Sending lower fare notification...")
        self.send_notification(message, NotificationLevel.INFO)

    def healthchecks_success(self, data: str) -> None:
        if self.reservation_monitor.config.healthchecks_url is not None:
            requests.post(self.reservation_monitor.config.healthchecks_url, data=data)

    def healthchecks_fail(self, data: str) -> None:
        if self.reservation_monitor.config.healthchecks_url is not None:
            requests.post(self.reservation_monitor.config.healthchecks_url + "/fail", data=data)

    def _get_account_name(self) -> str:
        # hasattr has to be used instead of isinstance to avoid a circular import
        if (
            hasattr(self.reservation_monitor, "username")
            and not self.reservation_monitor.first_name
        ):
            # No name has been set, so use the account's username. A ReservationMonitor will always
            # have a name set, but check if it is an AccountMonitor (through hasattr) just in case
            return self.reservation_monitor.username

        return f"{self.reservation_monitor.first_name} {self.reservation_monitor.last_name}"
