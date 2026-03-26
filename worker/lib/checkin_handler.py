"""Adapted check-in handler that uses threading instead of multiprocessing
and writes status updates to the database."""

from __future__ import annotations

import json
import time
import threading
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from .log import get_logger
from .utils import (
    AirportCheckInError,
    DriverTimeoutError,
    RequestError,
    get_current_time,
    make_request,
)

if TYPE_CHECKING:
    import sqlite3

JSON = dict[str, Any]

CHECKIN_URL = "mobile-air-operations/v1/mobile-air-operations/page/check-in/"
MAX_CHECK_IN_ATTEMPTS = 10

logger = get_logger(__name__)


class CheckInHandler:
    """Handles checking in for a single flight using threads and DB status tracking."""

    def __init__(
        self,
        headers: dict,
        flight_db_id: str,
        confirmation_number: str,
        first_name: str,
        last_name: str,
        departure_time: datetime,
        departure_airport: str,
        destination_airport: str,
        is_same_day: bool,
        lock: threading.Lock,
        db_conn_factory,
        notification_handler=None,
        refresh_headers_fn=None,
    ) -> None:
        self.headers = headers
        self.flight_db_id = flight_db_id
        self.confirmation_number = confirmation_number
        self.first_name = first_name
        self.last_name = last_name
        self.departure_time = departure_time
        self.departure_airport = departure_airport
        self.destination_airport = destination_airport
        self.is_same_day = is_same_day
        self.lock = lock
        self.db_conn_factory = db_conn_factory
        self.notification_handler = notification_handler
        self.refresh_headers_fn = refresh_headers_fn
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def schedule_check_in(self) -> None:
        logger.debug("Scheduling check-in for flight %s", self.flight_db_id)
        self._thread = threading.Thread(target=self._set_check_in, daemon=True)
        self._thread.start()
        self._update_status("scheduled")

    def stop_check_in(self) -> None:
        logger.debug("Stopping check-in for flight %s", self.flight_db_id)
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _update_status(self, status: str, result: str | None = None) -> None:
        from db import update_flight_status, add_log

        conn = self.db_conn_factory()
        update_flight_status(conn, self.flight_db_id, status, result)
        add_log(
            conn,
            f"Flight {self.confirmation_number} {self.departure_airport}->{self.destination_airport}: {status}",
            level="info",
            flight_id=self.flight_db_id,
        )
        conn.close()

    def _set_check_in(self) -> None:
        checkin_time = self.departure_time - timedelta(days=1)
        try:
            self._wait_for_check_in(checkin_time)
            if not self._stop_event.is_set():
                self._check_in()
        except Exception as e:
            logger.exception("Error during check-in: %s", e)
            self._update_status("failed", str(e))

    def _wait_for_check_in(self, checkin_time: datetime) -> None:
        current_time = get_current_time()
        if checkin_time <= current_time:
            return

        # Refresh headers 30 minutes before
        sleep_time = (checkin_time - current_time - timedelta(minutes=30)).total_seconds()

        if sleep_time > 0:
            self._safe_sleep(sleep_time)
            if self._stop_event.is_set():
                return

            if self.refresh_headers_fn:
                with self.lock:
                    try:
                        new_headers = self.refresh_headers_fn()
                        if new_headers:
                            self.headers.update(new_headers)
                    except DriverTimeoutError:
                        logger.debug("Timeout while refreshing headers before check-in")

            current_time = get_current_time()

        sleep_time = (checkin_time - current_time).total_seconds()
        if sleep_time > 0:
            self._safe_sleep(sleep_time)

    def _safe_sleep(self, total_sleep_time: float) -> None:
        """Sleep in chunks, checking stop event periodically."""
        chunk = 60  # Check every minute
        while total_sleep_time > 0 and not self._stop_event.is_set():
            sleep_time = min(total_sleep_time, chunk)
            self._stop_event.wait(timeout=sleep_time)
            total_sleep_time -= sleep_time

    def _check_in(self) -> None:
        self._update_status("checking_in")
        logger.info(
            "Checking in to flight %s -> %s for %s %s",
            self.departure_airport,
            self.destination_airport,
            self.first_name,
            self.last_name,
        )

        try:
            reservation = self._attempt_check_in()
        except AirportCheckInError:
            logger.debug("Failed to check in. Airport check-in required")
            self._update_status("failed", "Airport check-in required")
            return
        except RequestError as err:
            logger.debug("Failed to check in. Error: %s", err)
            self._update_status("failed", str(err))
            return

        result_json = json.dumps(reservation.get("checkInConfirmationPage", {}))
        self._update_status("success", result_json)
        logger.info("Successfully checked in for flight %s", self.flight_db_id)

    def _attempt_check_in(self) -> JSON:
        expected_flights = 2 if self.is_same_day else 1
        attempts = 0

        while attempts < MAX_CHECK_IN_ATTEMPTS:
            attempts += 1
            reservation = self._check_in_to_flight()
            flights = reservation["checkInConfirmationPage"]["flights"]
            if len(flights) >= expected_flights:
                return reservation
            time.sleep(1)

        raise RequestError("Too many attempts during check-in")

    def _check_in_to_flight(self) -> JSON:
        info = {
            "firstName": self.first_name,
            "lastName": self.last_name,
            "passengerSearchToken": "",
            "recordLocator": self.confirmation_number,
        }
        site = CHECKIN_URL + self.confirmation_number
        response = make_request("POST", site, self.headers, info, random_sleep=False)

        info = response["checkInViewReservationPage"]["_links"]["checkIn"]
        site = f"mobile-air-operations{info['href']}"
        reservation = make_request("POST", site, self.headers, info["body"], random_sleep=False)
        return reservation
