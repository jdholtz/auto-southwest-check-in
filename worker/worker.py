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
    upsert_reservation,
    deactivate_stale_reservations,
    update_flight_status,
    update_flight_reservation_info,
    add_log,
    add_fare_check,
    get_flights_for_fare_check,
    get_flights_for_seat_upgrade,
    get_seat_preferences,
    update_flight_seat,
    log_diagnostic,
    get_notification_configs,
)
from lib.log import get_logger
from lib.utils import (
    CheckFaresOption,
    DriverTimeoutError,
    FlightChangeError,
    LoginError,
    RequestError,
    get_current_time,
)
from lib.browser_session import BrowserSession
from lib.checkin_handler import CheckInHandler

logger = get_logger(__name__)

VIEW_RESERVATION_URL = "mobile-air-booking/v1/mobile-air-booking/page/view-reservation/"
POLL_INTERVAL = 60  # seconds
RETRIEVAL_INTERVAL_DEFAULT = 24 * 3600  # 24 hours in seconds

# Shared state
browser_session: BrowserSession | None = None
active_handlers: dict[str, CheckInHandler] = {}
last_account_check: dict[str, float] = {}
last_reservation_check: dict[str, float] = {}
shutdown_event = threading.Event()


def get_db():
    """Create a new DB connection (for use in threads)."""
    return get_connection()


def process_reservation(
    conn: sqlite3.Connection,
    reservation: dict,
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
        response = browser_session.make_request("POST", site, {}, info, max_attempts=3)
    except RequestError as err:
        err_str = str(err)
        logger.error("Failed to retrieve reservation %s: %s", confirmation_number, err_str)
        resp_body = getattr(err, "response_body", "") or ""
        header_keys = list(browser_session.headers.keys()) if browser_session else []
        log_diagnostic(
            conn,
            category="auth_failure" if "403" in err_str or "Forbidden" in err_str else "api_error",
            endpoint=f"POST {VIEW_RESERVATION_URL}{confirmation_number}",
            expected_behavior="200 OK with viewReservationViewPage",
            actual_behavior=f"{err_str} | Headers: {header_keys}",
            headers_snapshot=json.dumps(header_keys),
            response_snapshot=resp_body[:500],
        )
        add_log(conn, f"Failed to retrieve reservation {confirmation_number}: {err}", "error")
        return []

    reservation_info = response.get("viewReservationViewPage", {})
    bounds = reservation_info.get("bounds", [])
    flights_data = []

    for bound in bounds:
        dep = bound.get("departureAirport", {})
        arr = bound.get("arrivalAirport", {})
        departure_airport = dep.get("code", dep.get("name", ""))
        destination_airport = arr.get("code", arr.get("name", ""))
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
            # Store reservation_info for fare checking
            try:
                update_flight_reservation_info(
                    conn, flight_id, json.dumps(reservation_info)
                )
            except Exception:
                pass
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
            browser_session=browser_session,
            flight_db_id=flight_id,
            confirmation_number=flight_row["confirmation_number"],
            first_name=flight_row["first_name"],
            last_name=flight_row["last_name"],
            departure_time=departure_time,
            departure_airport=flight_row["departure_airport"],
            destination_airport=flight_row["destination_airport"],
            is_same_day=False,
            db_conn_factory=get_db,
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
    """Process all active accounts - log in via browser and retrieve reservations."""
    accounts = get_active_accounts(conn)
    for account in accounts:
        account_id = account["id"]
        retrieval_interval = account.get("retrieval_interval", 24) * 3600

        last_check = last_account_check.get(account_id, 0)
        if time.time() - last_check < retrieval_interval:
            continue

        logger.info("Processing account: %s", account["username"])
        add_log(conn, f"Processing account: {account['username']}", "info")

        try:
            sw_reservations, first_name, last_name = browser_session.login_and_get_reservations(
                account["username"], account["password"]
            )
        except DriverTimeoutError:
            logger.warning("Timeout logging into account %s", account["username"])
            add_log(conn, f"Timeout logging into account {account['username']}", "warning")
            continue
        except LoginError as e:
            logger.error("Login failed for account %s: %s", account["username"], e)
            add_log(conn, f"Login failed for {account['username']}: {e}", "error")
            if e.status_code not in (429, 500):
                conn.execute("UPDATE accounts SET is_active = 0 WHERE id = ?", (account_id,))
                conn.commit()
                add_log(conn, f"Deactivated account {account['username']} due to login failure", "warning")
            continue
        except Exception as e:
            logger.error("Failed to process account %s: %s", account["username"], e)
            add_log(conn, f"Failed to process account {account['username']}: {e}", "error")
            continue

        logger.info("Retrieved %d reservations for account %s", len(sw_reservations), account["username"])
        add_log(conn, f"Retrieved {len(sw_reservations)} reservations for {account['username']}", "info")

        active_conf_numbers = []
        for sw_res in sw_reservations:
            conf_number = sw_res.get("record_locator", sw_res.get("recordLocator", ""))
            if not conf_number:
                continue
            active_conf_numbers.append(conf_number)
            upsert_reservation(conn, account_id, conf_number, first_name or account["username"], last_name or "")

        deactivate_stale_reservations(conn, account_id, active_conf_numbers)

        # Fetch flight details for each reservation via browser session
        reservations = conn.execute(
            "SELECT * FROM reservations WHERE account_id = ? AND is_active = 1",
            (account_id,),
        ).fetchall()

        for res_row in reservations:
            process_reservation(conn, dict(res_row))

        last_account_check[account_id] = time.time()


def process_manual_reservations(conn: sqlite3.Connection) -> None:
    """Process reservations not linked to any account."""
    reservations = conn.execute(
        "SELECT * FROM reservations WHERE account_id IS NULL AND is_active = 1"
    ).fetchall()

    for res_row in reservations:
        res = dict(res_row)
        res_id = res["id"]

        last_check = last_reservation_check.get(res_id, 0)
        if time.time() - last_check < RETRIEVAL_INTERVAL_DEFAULT:
            continue

        logger.info("Processing reservation: %s", res["confirmation_number"])
        process_reservation(conn, res)
        last_reservation_check[res_id] = time.time()


last_fare_check: float = 0
FARE_CHECK_INTERVAL = 4 * 3600  # Check fares every 4 hours


def check_fares(conn: sqlite3.Connection) -> None:
    """Check for fare drops on upcoming flights."""
    global last_fare_check

    if time.time() - last_fare_check < FARE_CHECK_INTERVAL:
        return

    if not browser_session:
        return

    flights = get_flights_for_fare_check(conn)
    if not flights:
        last_fare_check = time.time()
        return

    logger.info("Checking fares for %d flights", len(flights))
    add_log(conn, f"Checking fares for {len(flights)} flights", "info")

    from lib.fare_checker import FareChecker, get_fare_check_filter, same_flight_filter
    from lib.flight import Flight

    for flight_row in flights:
        try:
            reservation_info = json.loads(flight_row["reservation_info_json"])
            bounds = reservation_info.get("bounds", [])
            if not bounds:
                continue

            # Find the matching bound for this flight
            for bound in bounds:
                flight_nums = bound.get("flights", [])
                if flight_nums and flight_nums[0].get("number") == flight_row["flight_number"]:
                    flight_obj = Flight(bound, reservation_info, flight_row["confirmation_number"])

                    # Create a minimal fare checker that doesn't need ReservationMonitor
                    class FareCheckerStub:
                        def __init__(self):
                            self.headers = headers
                            self.filter = same_flight_filter

                    checker = FareCheckerStub()
                    # Use the _get_flight_price method logic
                    try:
                        fc = FareChecker.__new__(FareChecker)
                        fc.headers = browser_session.headers
                        fc.filter = same_flight_filter
                        price = fc._get_flight_price(flight_obj)
                        add_fare_check(
                            conn,
                            flight_row["id"],
                            price["amount"],
                            price.get("currencyCode", "USD"),
                        )
                        price_str = f"{price['amount']:+,} {price['currencyCode']}"
                        if price["amount"] < -1:
                            add_log(
                                conn,
                                f"Lower fare found for {flight_row['confirmation_number']} "
                                f"({flight_row['departure_airport']}->{flight_row['destination_airport']}): {price_str}",
                                "info",
                                flight_row["id"],
                            )
                        else:
                            add_log(
                                conn,
                                f"Fare check for {flight_row['confirmation_number']}: {price_str}",
                                "info",
                                flight_row["id"],
                            )
                    except (FlightChangeError, RequestError) as e:
                        logger.debug("Fare check skipped for %s: %s", flight_row["confirmation_number"], e)
                    except Exception as e:
                        logger.error("Fare check error: %s", e)
                        add_log(conn, f"Fare check error for {flight_row['confirmation_number']}: {e}", "error", flight_row["id"])
                    break
        except Exception as e:
            logger.error("Error processing fare check for flight %s: %s", flight_row["id"], e)

    last_fare_check = time.time()


def attempt_seat_upgrades(conn: sqlite3.Connection) -> None:
    """For A-List accounts, attempt seat upgrade 48 hours before departure."""
    if not browser_session:
        return

    flights = get_flights_for_seat_upgrade(conn)
    if not flights:
        return

    logger.info("Attempting seat upgrades for %d flights", len(flights))
    add_log(conn, f"Attempting seat upgrades for {len(flights)} A-List flights", "info")

    prefs = get_seat_preferences(conn)
    if not prefs:
        add_log(conn, "No seat preferences set, skipping seat upgrades", "info")
        return

    for flight_row in flights:
        flight_id = flight_row["id"]
        conf_num = flight_row["confirmation_number"]
        first_name = flight_row["first_name"]
        last_name = flight_row["last_name"]

        add_log(
            conn,
            f"Attempting seat upgrade for {conf_num} ({flight_row['departure_airport']}->{flight_row['destination_airport']})",
            "info",
            flight_id,
        )

        # Try to view the reservation to find seat-related links
        info = {
            "firstName": first_name,
            "lastName": last_name,
            "recordLocator": conf_num,
        }
        site = VIEW_RESERVATION_URL + conf_num

        try:
            response = browser_session.make_request("POST", site, {}, info)
            reservation_info = response.get("viewReservationViewPage", {})

            # Look for seat-related _links
            links = reservation_info.get("_links", {})
            seat_links = {k: v for k, v in links.items() if "seat" in k.lower()}

            if seat_links:
                add_log(conn, f"Seat links found for upgrade: {list(seat_links.keys())}", "info", flight_id)
                # TODO: Follow seat selection links once API structure is discovered
                # For now, log what we find for refinement
                for link_name, link_data in seat_links.items():
                    add_log(
                        conn,
                        f"Seat link '{link_name}': {json.dumps(link_data)[:300]}",
                        "info",
                        flight_id,
                    )
            else:
                available_links = list(links.keys()) if links else []
                add_log(conn, f"No seat links found. Available links: {available_links}", "info", flight_id)

        except RequestError as e:
            add_log(conn, f"Failed to retrieve reservation for seat upgrade: {e}", "error", flight_id)
        except Exception as e:
            logger.error("Seat upgrade error for %s: %s", conf_num, e)
            add_log(conn, f"Seat upgrade error: {e}", "error", flight_id)


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
    global browser_session

    logger.info("Worker started")
    conn = get_db()
    add_log(conn, "Worker started", "info")

    # Start persistent browser session
    browser_session = BrowserSession()
    try:
        browser_session.start()
        add_log(conn, f"Browser session started with {len(browser_session.headers)} headers", "info")
    except Exception as e:
        logger.error("Failed to start browser session: %s", e)
        add_log(conn, f"Failed to start browser session: {e}", "error")

    while not shutdown_event.is_set():
        try:
            conn = get_db()

            # Ensure browser is alive and session is fresh
            browser_session.ensure_alive()

            # Process accounts (login + retrieve reservations)
            process_accounts(conn)

            # Process manual reservations
            process_manual_reservations(conn)

            # Schedule check-ins for pending flights
            schedule_pending_flights(conn)

            # Check for fare drops
            check_fares(conn)

            # Attempt seat upgrades for A-List accounts (48h before departure)
            attempt_seat_upgrades(conn)

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

    # Shutdown
    logger.info("Worker shutting down...")
    for handler in active_handlers.values():
        handler.stop_check_in()
    if browser_session:
        browser_session.stop()


def signal_handler(signum, frame):
    logger.info("Received signal %d, shutting down...", signum)
    shutdown_event.set()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    main_loop()
