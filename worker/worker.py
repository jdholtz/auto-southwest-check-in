"""Main worker process that polls the database for active accounts/reservations
and manages check-in scheduling."""

import json
import os
import sys
import signal
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

# Add worker directory to path so lib imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import (
    get_connection,
    get_active_accounts,
    get_active_reservations,
    get_pending_flights,
    upsert_flight,
    update_flight_status,
    add_log,
    get_notification_configs,
)
from lib.log import get_logger
from lib.utils import (
    DriverTimeoutError,
    LoginError,
    RequestError,
    get_current_time,
    make_request,
)
from lib.webdriver import WebDriver
from lib.checkin_handler import CheckInHandler

logger = get_logger(__name__)

VIEW_RESERVATION_URL = "mobile-air-booking/v1/mobile-air-booking/page/view-reservation/"
POLL_INTERVAL = 60  # seconds
RETRIEVAL_INTERVAL_DEFAULT = 24 * 3600  # 24 hours in seconds

# Shared state
headers = {}
headers_lock = threading.Lock()
active_handlers: dict[str, CheckInHandler] = {}
last_account_check: dict[str, float] = {}
last_reservation_check: dict[str, float] = {}
shutdown_event = threading.Event()


def refresh_headers_via_webdriver() -> dict:
    """Use webdriver to get fresh Southwest API headers."""
    global headers

    class FakeScheduler:
        """Minimal scheduler interface for WebDriver compatibility."""

        def __init__(self):
            self.headers = {}

    scheduler = FakeScheduler()
    try:
        webdriver = WebDriver(scheduler)
        webdriver.set_headers()
        headers = scheduler.headers
        return headers
    except Exception as e:
        logger.error("Failed to refresh headers: %s", e)
        raise


def get_db():
    """Create a new DB connection (for use in threads)."""
    return get_connection()


def process_reservation(
    conn: sqlite3.Connection,
    reservation: dict,
    current_headers: dict,
) -> list[dict]:
    """Retrieve flights for a reservation from Southwest API and sync to database."""
    confirmation_number = reservation["confirmation_number"]
    first_name = reservation["first_name"]
    last_name = reservation["last_name"]
    reservation_id = reservation["id"]

    info = {
        "firstName": first_name,
        "lastName": last_name,
        "recordLocator": confirmation_number,
    }
    site = VIEW_RESERVATION_URL + confirmation_number

    try:
        response = make_request("POST", site, current_headers, info)
    except RequestError as err:
        logger.error("Failed to retrieve reservation %s: %s", confirmation_number, err)
        add_log(conn, f"Failed to retrieve reservation {confirmation_number}: {err}", "error")
        return []

    reservation_info = response.get("viewReservationViewPage", {})
    bounds = reservation_info.get("bounds", [])
    flights_data = []

    for bound in bounds:
        departure_airport = bound.get("departureAirport", {}).get("code", "")
        destination_airport = bound.get("destinationAirport", {}).get("code", "")
        flight_number = bound.get("flights", [{}])[0].get("number", "") if bound.get("flights") else ""
        departure_date = bound.get("departureDate", "")
        departure_time_str = bound.get("departureTime", "")
        is_international = bound.get("isInternational", False)

        if departure_date and departure_time_str:
            # Convert to UTC using airport timezone mapping
            from lib.flight import Flight

            try:
                flight = Flight(bound, reservation_info, confirmation_number)
                departure_utc = flight.departure_time.isoformat()
            except Exception:
                departure_utc = f"{departure_date}T{departure_time_str}:00"

            flight_id = upsert_flight(
                conn,
                reservation_id,
                flight_number,
                departure_airport,
                destination_airport,
                departure_utc,
                is_international,
            )
            flights_data.append(
                {
                    "id": flight_id,
                    "confirmation_number": confirmation_number,
                    "first_name": first_name,
                    "last_name": last_name,
                    "departure_time": departure_utc,
                    "departure_airport": departure_airport,
                    "destination_airport": destination_airport,
                    "flight_number": flight_number,
                }
            )

    add_log(
        conn,
        f"Retrieved {len(flights_data)} flights for reservation {confirmation_number}",
        "info",
    )
    return flights_data


def schedule_pending_flights(conn: sqlite3.Connection) -> None:
    """Schedule check-ins for any pending flights."""
    global headers

    pending = get_pending_flights(conn)
    for flight_row in pending:
        flight_id = flight_row["id"]

        if flight_id in active_handlers:
            continue

        departure_time_str = flight_row["departure_time"]
        try:
            departure_time = datetime.fromisoformat(departure_time_str)
            if departure_time.tzinfo is None:
                departure_time = departure_time.replace(tzinfo=timezone.utc)
        except ValueError:
            logger.error("Invalid departure time for flight %s: %s", flight_id, departure_time_str)
            continue

        checkin_time = departure_time - timedelta(days=1)
        if checkin_time < get_current_time():
            # Check-in time has passed, check if it's still within window
            if departure_time > get_current_time():
                # Flight hasn't departed, try to check in now
                pass
            else:
                update_flight_status(conn, flight_id, "failed", "Departure time has passed")
                continue

        handler = CheckInHandler(
            headers=dict(headers),
            flight_db_id=flight_id,
            confirmation_number=flight_row["confirmation_number"],
            first_name=flight_row["first_name"],
            last_name=flight_row["last_name"],
            departure_time=departure_time,
            departure_airport=flight_row["departure_airport"],
            destination_airport=flight_row["destination_airport"],
            is_same_day=False,
            lock=headers_lock,
            db_conn_factory=get_db,
            refresh_headers_fn=refresh_headers_via_webdriver,
        )
        handler.schedule_check_in()
        active_handlers[flight_id] = handler

        logger.info(
            "Scheduled check-in for flight %s (%s -> %s) at %s",
            flight_id,
            flight_row["departure_airport"],
            flight_row["destination_airport"],
            checkin_time.isoformat(),
        )


def process_accounts(conn: sqlite3.Connection) -> None:
    """Process all active accounts - log in via webdriver and retrieve reservations."""
    global headers

    accounts = get_active_accounts(conn)
    for account in accounts:
        account_id = account["id"]
        retrieval_interval = account.get("retrieval_interval", 24) * 3600

        # Check if we need to refresh this account
        last_check = last_account_check.get(account_id, 0)
        if time.time() - last_check < retrieval_interval:
            continue

        logger.info("Processing account: %s", account["username"])
        add_log(conn, f"Processing account: {account['username']}", "info")

        try:
            with headers_lock:
                refresh_headers_via_webdriver()
        except Exception as e:
            logger.error("Failed to get headers for account %s: %s", account["username"], e)
            add_log(conn, f"Failed to get headers for account {account['username']}: {e}", "error")
            continue

        # Get reservations linked to this account
        reservations = conn.execute(
            "SELECT * FROM reservations WHERE account_id = ? AND is_active = 1",
            (account_id,),
        ).fetchall()

        for res_row in reservations:
            res = dict(res_row)
            process_reservation(conn, res, headers)

        last_account_check[account_id] = time.time()


def process_manual_reservations(conn: sqlite3.Connection) -> None:
    """Process reservations not linked to any account."""
    global headers

    reservations = conn.execute(
        "SELECT * FROM reservations WHERE account_id IS NULL AND is_active = 1"
    ).fetchall()

    for res_row in reservations:
        res = dict(res_row)
        res_id = res["id"]
        retrieval_interval = RETRIEVAL_INTERVAL_DEFAULT

        last_check = last_reservation_check.get(res_id, 0)
        if time.time() - last_check < retrieval_interval:
            continue

        logger.info("Processing reservation: %s", res["confirmation_number"])

        if not headers:
            try:
                with headers_lock:
                    refresh_headers_via_webdriver()
            except Exception as e:
                logger.error("Failed to get headers: %s", e)
                add_log(conn, f"Failed to get headers: {e}", "error")
                continue

        process_reservation(conn, res, headers)
        last_reservation_check[res_id] = time.time()


def cleanup_handlers() -> None:
    """Remove handlers for flights that are no longer pending."""
    conn = get_db()
    for flight_id in list(active_handlers.keys()):
        row = conn.execute(
            "SELECT checkin_status FROM flights WHERE id = ?", (flight_id,)
        ).fetchone()
        if not row or row["checkin_status"] in ("success", "failed"):
            handler = active_handlers.pop(flight_id, None)
            if handler:
                handler.stop_check_in()
    conn.close()


def main_loop() -> None:
    """Main worker loop - polls database and manages check-ins."""
    logger.info("Worker started")
    conn = get_db()
    add_log(conn, "Worker started", "info")

    while not shutdown_event.is_set():
        try:
            conn = get_db()

            # Process accounts (login + retrieve reservations)
            process_accounts(conn)

            # Process manual reservations
            process_manual_reservations(conn)

            # Schedule check-ins for pending flights
            schedule_pending_flights(conn)

            # Clean up completed handlers
            cleanup_handlers()

            conn.close()
        except Exception as e:
            logger.exception("Error in main loop: %s", e)
            try:
                err_conn = get_db()
                add_log(err_conn, f"Worker error: {e}", "error")
                err_conn.close()
            except Exception:
                pass

        # Wait for next poll
        shutdown_event.wait(timeout=POLL_INTERVAL)

    # Shutdown: stop all handlers
    logger.info("Worker shutting down...")
    for handler in active_handlers.values():
        handler.stop_check_in()


def signal_handler(signum, frame):
    logger.info("Received signal %d, shutting down...", signum)
    shutdown_event.set()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    main_loop()
