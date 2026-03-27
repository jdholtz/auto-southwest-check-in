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
        browser_session,
        flight_db_id: str,
        confirmation_number: str,
        first_name: str,
        last_name: str,
        departure_time: datetime,
        departure_airport: str,
        destination_airport: str,
        is_same_day: bool,
        db_conn_factory,
    ) -> None:
        self.browser_session = browser_session
        self.headers = browser_session.headers if browser_session else {}
        self.flight_db_id = flight_db_id
        self.confirmation_number = confirmation_number
        self.first_name = first_name
        self.last_name = last_name
        self.departure_time = departure_time
        self.departure_airport = departure_airport
        self.destination_airport = destination_airport
        self.is_same_day = is_same_day
        self.db_conn_factory = db_conn_factory
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

    def _log_diagnostic(self, category: str, endpoint: str, expected: str, actual: str) -> None:
        """Log a diagnostic entry for API behavior tracking."""
        from db import log_diagnostic
        try:
            conn = self.db_conn_factory()
            header_keys = list(self.headers.keys()) if self.headers else []
            log_diagnostic(
                conn,
                category=category,
                endpoint=endpoint,
                expected_behavior=expected,
                actual_behavior=actual,
                headers_snapshot=json.dumps(header_keys),
            )
            conn.close()
        except Exception:
            pass

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

            # Ensure browser session is alive before check-in
            if self.browser_session:
                try:
                    self.browser_session.ensure_alive()
                    self.headers = self.browser_session.headers
                except DriverTimeoutError:
                    logger.debug("Timeout while refreshing browser session before check-in")

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
            self._log_diagnostic("checkin_failure", "check-in endpoint",
                                 "Successful check-in", "Airport check-in required")
            return
        except RequestError as err:
            logger.debug("Failed to check in. Error: %s", err)
            self._update_status("failed", str(err))
            self._log_diagnostic("checkin_failure",
                                 f"check-in for {self.confirmation_number}",
                                 "200 OK with checkInConfirmationPage",
                                 str(err))
            return

        confirmation_page = reservation.get("checkInConfirmationPage", {})
        result_json = json.dumps(confirmation_page)
        self._update_status("success", result_json)
        logger.info("Successfully checked in for flight %s", self.flight_db_id)

        # Discovery: log response structure for seat assignment analysis
        self._discover_seat_info(reservation)

    def _discover_seat_info(self, reservation: JSON) -> None:
        """Log check-in response structure to help discover seat selection endpoints."""
        from db import add_log, update_flight_seat, get_seat_preferences

        conn = self.db_conn_factory()
        try:
            # Log top-level keys
            top_keys = list(reservation.keys())
            add_log(conn, f"Check-in response keys: {top_keys}", "info", self.flight_db_id)

            # Look for seat-related data anywhere in the response
            confirmation_page = reservation.get("checkInConfirmationPage", {})

            # Log _links if present (Southwest hypermedia pattern)
            links = confirmation_page.get("_links", {})
            if links:
                link_keys = list(links.keys())
                add_log(conn, f"Check-in _links available: {link_keys}", "info", self.flight_db_id)

                # Look for seat-related links
                seat_links = [k for k in link_keys if "seat" in k.lower()]
                if seat_links:
                    add_log(conn, f"Seat-related links found: {seat_links}", "info", self.flight_db_id)
                    # Attempt seat selection if links exist
                    self._attempt_seat_selection(conn, links, seat_links)

            # Check for seat assignments in flights/passengers
            flights = confirmation_page.get("flights", [])
            for flight_data in flights:
                passengers = flight_data.get("passengers", [])
                for pax in passengers:
                    # Log all passenger keys to discover seat fields
                    pax_keys = list(pax.keys())
                    add_log(conn, f"Passenger data keys: {pax_keys}", "info", self.flight_db_id)

                    # Try common seat field names
                    seat = (
                        pax.get("seatAssignment")
                        or pax.get("seat")
                        or pax.get("seatNumber")
                        or pax.get("assignedSeat")
                    )
                    if seat:
                        add_log(conn, f"Seat assignment found: {seat}", "info", self.flight_db_id)
                        update_flight_seat(conn, self.flight_db_id, str(seat))
                    else:
                        # Log boarding info if no seat found
                        boarding = f"Group {pax.get('boardingGroup', '?')}, Position {pax.get('boardingPosition', '?')}"
                        add_log(conn, f"No seat assignment in response. Boarding: {boarding}", "info", self.flight_db_id)
        except Exception as e:
            logger.error("Error during seat discovery: %s", e)
            add_log(conn, f"Seat discovery error: {e}", "error", self.flight_db_id)
        finally:
            conn.close()

    def _attempt_seat_selection(self, conn, links: JSON, seat_links: list[str]) -> None:
        """Attempt to select a preferred seat using discovered API links."""
        from db import get_seat_preferences, update_flight_seat, add_log

        prefs = get_seat_preferences(conn)
        if not prefs:
            add_log(conn, "No seat preferences configured, skipping seat selection", "info", self.flight_db_id)
            return

        preferred_letters = prefs.get("preferred_letters", "A,F").split(",")
        preferred_rows = [int(r.strip()) for r in prefs.get("preferred_rows", "1,2,3,4,5,6").split(",") if r.strip().isdigit()]
        fallback_letters = prefs.get("fallback_letters", "A,C,D,F").split(",")

        for link_name in seat_links:
            link_data = links[link_name]
            add_log(conn, f"Attempting seat selection via '{link_name}': {json.dumps(link_data)[:200]}", "info", self.flight_db_id)

            try:
                href = link_data.get("href", "")
                if not href:
                    continue

                # Try to fetch seat map
                site = f"mobile-air-operations{href}" if not href.startswith("http") else href
                method = link_data.get("method", "GET").upper()
                body = link_data.get("body")

                if method == "GET":
                    response = make_request("GET", site, self.headers, link_data.get("query"), max_attempts=3)
                else:
                    response = make_request("POST", site, self.headers, body, max_attempts=3)

                add_log(conn, f"Seat endpoint response keys: {list(response.keys())[:10]}", "info", self.flight_db_id)

                # TODO: Parse seat map response and select best available seat
                # This will be refined once we see actual API response structure
            except Exception as e:
                add_log(conn, f"Seat selection attempt failed: {e}", "warning", self.flight_db_id)

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

        # Use browser session if available, otherwise fall back to raw HTTP
        if self.browser_session:
            response = self.browser_session.make_request("POST", site, {}, info, random_sleep=False)
            info = response["checkInViewReservationPage"]["_links"]["checkIn"]
            site = f"mobile-air-operations{info['href']}"
            reservation = self.browser_session.make_request("POST", site, {}, info["body"], random_sleep=False)
        else:
            response = make_request("POST", site, self.headers, info, random_sleep=False)
            info = response["checkInViewReservationPage"]["_links"]["checkIn"]
            site = f"mobile-air-operations{info['href']}"
            reservation = make_request("POST", site, self.headers, info["body"], random_sleep=False)
        return reservation
