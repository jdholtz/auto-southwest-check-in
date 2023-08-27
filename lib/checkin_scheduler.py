from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Dict, List

from .checkin_handler import CheckInHandler
from .flight import Flight
from .log import get_logger
from .utils import RequestError, make_request
from .webdriver import WebDriver

if TYPE_CHECKING:
    from .reservation_monitor import ReservationMonitor

VIEW_RESERVATION_URL = "mobile-air-booking/v1/mobile-air-booking/page/view-reservation/"
logger = get_logger(__name__)

FLIGHT_IN_PAST_CODE = 400520413


class CheckInScheduler:
    """
    Handles scheduling flights from reservations. Retrieves the necessary
    information and schedules a check-in for each flight via the CheckinHandler.
    """

    def __init__(self, reservation_monitor: ReservationMonitor) -> None:
        self.reservation_monitor = reservation_monitor
        self.notification_handler = reservation_monitor.notification_handler

        self.headers = {}
        self.flights = []
        self.checkin_handlers = []

    def process_reservations(self, confirmation_numbers: List[str]) -> None:
        """
        Flights from all confirmation numbers are retrieved. Then, any new
        flights are scheduled and any flights now longer found are removed.
        """
        flights = []
        for confirmation_number in confirmation_numbers:
            flights.extend(self._get_flights(confirmation_number))

        logger.debug("%d total flights were found", len(flights))
        new_flights = self._get_new_flights(flights)
        self._schedule_flights(new_flights)

        self._remove_old_flights(flights)

    def refresh_headers(self) -> None:
        logger.debug("Refreshing headers for current session")
        webdriver = WebDriver(self)
        webdriver.set_headers()

    def _get_flights(self, confirmation_number: str) -> List[Flight]:
        """Get all flights booked on a single reservation"""
        reservation_info = self._get_reservation_info(confirmation_number)
        logger.debug("%d flights found under current reservation", len(reservation_info))

        flights = []
        # If multiple flights are under the same confirmation number, it will schedule all checkins
        for flight_info in reservation_info:
            if flight_info["departureStatus"] != "DEPARTED":
                flight = Flight(flight_info, confirmation_number)
                self._set_same_day_flight(flight, flights)
                flights.append(flight)

        return flights

    def _get_reservation_info(self, confirmation_number: str) -> List[Dict[str, Any]]:
        info = {
            "first-name": self.reservation_monitor.first_name,
            "last-name": self.reservation_monitor.last_name,
        }
        site = VIEW_RESERVATION_URL + confirmation_number

        try:
            logger.debug("Retrieving reservation information")
            response = make_request("GET", site, self.headers, info)
        except RequestError as err:
            # Don't send a notification if flights have already been scheduled and all flights
            # from this reservation are old. This is how old flights are removed.
            if len(self.flights) == 0 or err.southwest_code != FLIGHT_IN_PAST_CODE:
                logger.debug("Failed to retrieve reservation info. Error: %s. Exiting", err)
                self.notification_handler.failed_reservation_retrieval(err, confirmation_number)
            else:
                logger.debug("Flights on the reservation have already departed")

            return []

        logger.debug("Successfully retrieved reservation information")
        reservation_info = response["viewReservationViewPage"]["bounds"]
        return reservation_info

    def _set_same_day_flight(self, flight: Flight, previous_flights: List[Flight]) -> None:
        for prev_flight in previous_flights:
            if flight.departure_time - prev_flight.departure_time <= timedelta(hours=24):
                logger.debug("Flight is on the same day")
                flight.is_same_day = True
                break

    def _get_new_flights(self, flights: List[Flight]) -> List[Flight]:
        """Retrieve a list of all flights that are not already scheduled for check-in"""
        new_flights = []
        for flight in flights:
            if flight not in self.flights:
                new_flights.append(flight)

        logger.debug("%d new flights found", len(new_flights))
        return new_flights

    def _schedule_flights(self, flights: List[Flight]) -> None:
        logger.debug("Scheduling %d flights for check-in", len(flights))
        for flight in flights:
            checkin_handler = CheckInHandler(self, flight, self.reservation_monitor.lock)
            checkin_handler.schedule_check_in()

            self.flights.append(flight)
            self.checkin_handlers.append(checkin_handler)

        self.notification_handler.new_flights(flights)

    def _remove_old_flights(self, flights: List[Flight]) -> None:
        """Remove all scheduled flights that are not in the current flight list"""
        logger.debug("%d flights are currently scheduled. Removing old flights", len(self.flights))

        # Copy the list because it can potentially change inside the loop
        for flight in self.flights[:]:
            if flight not in flights:
                flight_idx = self.flights.index(flight)
                print(
                    f"Flight from {flight.departure_airport} to {flight.destination_airport} at "
                    f"{flight.departure_time} UTC is no longer scheduled. Stopping its check-in\n"
                )  # Don't log as it has sensitive information

                self.checkin_handlers[flight_idx].stop_check_in()

                self.checkin_handlers.pop(flight_idx)
                self.flights.pop(flight_idx)

        logger.debug(
            "Successfully removed old flights. %d flights are now scheduled", len(self.flights)
        )
