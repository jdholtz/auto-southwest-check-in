from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List

from .checkin_handler import CheckInHandler
from .flight import Flight
from .general import CheckInError, make_request
from .webdriver import WebDriver

if TYPE_CHECKING:  # pragma: no cover
    from .flight_retriever import FlightRetriever

VIEW_RESERVATION_URL = "mobile-air-booking/v1/mobile-air-booking/page/view-reservation/"


class CheckInScheduler:
    """
    Handles scheduling flights based on confirmation numbers. Retrieves the
    necessary information and schedule a checkin for each flight via the CheckinHandler.
    """

    def __init__(self, flight_retriever: FlightRetriever) -> None:
        self.flight_retriever = flight_retriever
        self.notification_handler = self.flight_retriever.notification_handler

        self.headers = {}
        self.flights = []

    def schedule(self, confirmation_numbers: List[str]) -> None:
        prev_flight_len = len(self.flights)

        for confirmation_number in confirmation_numbers:
            self._schedule_flights(confirmation_number)

        self.notification_handler.new_flights(self.flights[prev_flight_len:])

    def _schedule_flights(self, confirmation_number: str) -> None:
        reservation_info = self._get_reservation_info(confirmation_number)

        # If multiple flights are under the same confirmation number, it will schedule all checkins one by one
        for flight_info in reservation_info:
            flight = Flight(flight_info, confirmation_number)

            if flight_info["departureStatus"] != "DEPARTED" and not self._flight_is_scheduled(
                flight
            ):
                self.flights.append(flight)
                checkin_handler = CheckInHandler(self, flight)
                checkin_handler.schedule_check_in()

    def _get_reservation_info(self, confirmation_number: str) -> List[Dict[str, Any]]:
        info = {
            "first-name": self.flight_retriever.first_name,
            "last-name": self.flight_retriever.last_name,
        }
        site = VIEW_RESERVATION_URL + confirmation_number

        try:
            response = make_request("GET", site, self.headers, info)
        except CheckInError as err:
            self.notification_handler.failed_reservation_retrieval(err, confirmation_number)
            return []

        reservation_info = response["viewReservationViewPage"]["bounds"]
        return reservation_info

    def _flight_is_scheduled(self, flight: Flight) -> bool:
        for scheduled_flight in self.flights:
            if (
                flight.departure_time == scheduled_flight.departure_time
                and flight.departure_airport == scheduled_flight.departure_airport
                and flight.destination_airport == scheduled_flight.destination_airport
            ):
                return True

        return False

    def refresh_headers(self) -> None:
        webdriver = WebDriver(self)
        webdriver.set_headers()

    def remove_departed_flights(self) -> None:
        current_time = datetime.utcnow()

        for flight in self.flights[:]:
            if flight.departure_time < current_time:
                self.flights.remove(flight)
