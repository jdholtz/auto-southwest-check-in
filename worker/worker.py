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
    get_last_fare_check,
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

    from lib.flight import Flight

    for bound in bounds:
        flight_number = bound.get("flights", [{}])[0].get("number", "") if bound.get("flights") else ""
        departure_date = bound.get("departureDate", "")
        departure_time_str = bound.get("departureTime", "")
        is_international = bound.get("isInternational", False)

        if departure_date and departure_time_str:
            # Extract airports - try multiple approaches
            dep_raw = bound.get("departureAirport", {})
            arr_raw = bound.get("arrivalAirport", {})

            # Primary: get "code" field (3-letter airport code)
            departure_airport = dep_raw.get("code", "")
            destination_airport = arr_raw.get("code", "")

            # Fallback: get "name" field only if it looks like a code (3-4 chars)
            if not departure_airport:
                name = dep_raw.get("name", "")
                departure_airport = name if len(name) <= 4 else ""
            if not destination_airport:
                name = arr_raw.get("name", "")
                destination_airport = name if len(name) <= 4 else ""

            # Last resort: try Flight class (which uses "name" fields)
            if not departure_airport or not destination_airport:
                try:
                    flight_obj = Flight(bound, reservation_info, confirmation_number)
                    if not departure_airport:
                        val = flight_obj.departure_airport
                        departure_airport = val if len(val) <= 4 else ""
                    if not destination_airport:
                        val = flight_obj.destination_airport
                        destination_airport = val if len(val) <= 4 else ""
                except Exception:
                    pass

            # Log what we extracted for diagnostic purposes
            add_log(
                conn,
                f"Flight {flight_number} airports: {departure_airport} -> {destination_airport} "
                f"(raw dep={json.dumps(dep_raw)}, raw arr={json.dumps(arr_raw)})",
                "info",
            )

            # Convert departure time to UTC
            departure_utc = f"{departure_date}T{departure_time_str}:00"
            try:
                flight_obj = Flight(bound, reservation_info, confirmation_number)
                departure_utc = flight_obj.departure_time.isoformat()
            except Exception:
                pass

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
                info_json = json.dumps(reservation_info)
                update_flight_reservation_info(conn, flight_id, info_json)
            except Exception as e:
                logger.error("Failed to store reservation_info for %s: %s", flight_id, e)
                add_log(conn, f"Failed to store reservation info for fare checking: {e}", "warning")
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
            logger.error("Login failed for account %s: %s (status: %s)", account["username"], e, e.status_code)
            add_log(conn, f"Login failed for {account['username']}: {e} (status: {e.status_code})", "error")

            # Only deactivate for confirmed invalid credentials (Southwest code 400518024)
            # All other errors (429, 500, 502, 503, 401, 403, etc.) are treated as transient
            is_bad_credentials = "Invalid credentials" in str(e)
            if is_bad_credentials:
                # Increment failure counter, deactivate after 3 consecutive failures
                failure_count = (account.get("login_failure_count") or 0) + 1
                conn.execute(
                    "UPDATE accounts SET login_failure_count = ? WHERE id = ?",
                    (failure_count, account_id),
                )
                conn.commit()
                if failure_count >= 3:
                    conn.execute("UPDATE accounts SET is_active = 0 WHERE id = ?", (account_id,))
                    conn.commit()
                    add_log(conn, f"Deactivated account {account['username']} after {failure_count} consecutive credential failures", "warning")
                else:
                    add_log(conn, f"Login failure #{failure_count} for {account['username']} (will deactivate after 3)", "warning")
            else:
                add_log(conn, f"Transient login error for {account['username']} (status {e.status_code}), will retry next cycle", "warning")
            continue
        except Exception as e:
            logger.error("Failed to process account %s: %s", account["username"], e)
            add_log(conn, f"Failed to process account {account['username']}: {e} (transient, will retry)", "error")
            continue

        # Reset failure counter on successful login
        conn.execute("UPDATE accounts SET login_failure_count = 0 WHERE id = ?", (account_id,))
        conn.commit()

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
    """Check for fare drops on upcoming flights using the browser session."""
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

    from lib.flight import Flight

    for flight_row in flights:
        try:
            # Re-fetch reservation to get fresh passenger-search-token
            # (stored tokens expire due to inactivity)
            res_info = {
                "firstName": flight_row["first_name"],
                "lastName": flight_row["last_name"],
                "recordLocator": flight_row["confirmation_number"],
            }
            res_site = VIEW_RESERVATION_URL + flight_row["confirmation_number"]
            try:
                fresh_response = browser_session.make_request("POST", res_site, {}, res_info, max_attempts=3)
                reservation_info = fresh_response.get("viewReservationViewPage", {})
                # Update stored reservation_info with fresh data
                update_flight_reservation_info(conn, flight_row["id"], json.dumps(reservation_info))
            except RequestError as e:
                add_log(conn, f"Fare check: failed to refresh reservation {flight_row['confirmation_number']}: {e}", "warning", flight_row["id"])
                continue

            bounds = reservation_info.get("bounds", [])
            if not bounds:
                add_log(conn, f"No bounds in reservation_info for {flight_row['confirmation_number']}", "warning", flight_row["id"])
                continue

            # Check for change link
            links = reservation_info.get("_links", {})
            change_link = links.get("change")
            if not change_link:
                add_log(conn, f"No change link for {flight_row['confirmation_number']} - fare check not available", "info", flight_row["id"])
                continue

            # Step 1: Get the change flight page
            change_site = "mobile-air-booking/" + change_link["href"]
            try:
                change_response = browser_session.make_request(
                    "GET", change_site, {}, change_link.get("query"), max_attempts=3
                )
            except RequestError as e:
                add_log(
                    conn,
                    f"Fare check failed (change page) for {flight_row['confirmation_number']}: {e}",
                    "warning",
                    flight_row["id"],
                )
                # Log diagnostic with the full change_link for debugging
                log_diagnostic(
                    conn,
                    category="fare_check_failure",
                    endpoint=f"GET {change_site}",
                    expected_behavior="200 OK with changeFlightPage",
                    actual_behavior=str(e),
                    headers_snapshot=json.dumps(list(browser_session.headers.keys())),
                    response_snapshot=json.dumps({
                        "change_link": change_link,
                        "error_response_body": getattr(e, "response_body", ""),
                    })[:1000],
                )
                continue

            change_flight_page = change_response.get("changeFlightPage", {})
            if not change_flight_page:
                add_log(conn, f"No changeFlightPage in response for {flight_row['confirmation_number']}", "warning", flight_row["id"])
                continue

            # Build search query
            bound_references = change_flight_page.get("_links", {}).get("changeShopping", {})
            shopping_body = bound_references.get("body", [])
            bound_selections = change_flight_page.get("boundSelections", [])

            query = {}
            bound_keys = ["outbound", "inbound"]
            target_bound_page = None
            for idx, bound_sel in enumerate(bound_selections):
                if idx < len(bound_keys) and idx < len(shopping_body):
                    is_match = bound_sel.get("flight") == flight_row["flight_number"]
                    query[bound_keys[idx]] = {
                        "boundReference": shopping_body[idx].get("boundReference", ""),
                        "date": bound_sel.get("originalDate", ""),
                        "destination-airport": bound_sel.get("toAirportCode", ""),
                        "origin-airport": bound_sel.get("fromAirportCode", ""),
                        "isChangeBound": is_match,
                    }
                    if is_match:
                        target_bound_page = f"{bound_keys[idx]}Page"

            if not target_bound_page:
                add_log(conn, f"Flight number {flight_row['flight_number']} didn't match any bound", "warning", flight_row["id"])
                continue

            # Step 2: Get matching flights
            shopping_href = bound_references.get("href", "")
            if not shopping_href:
                continue
            shopping_site = "mobile-air-booking/" + shopping_href

            time.sleep(2)  # Be polite
            try:
                shopping_response = browser_session.make_request(
                    "POST", shopping_site, {}, query, max_attempts=3
                )
            except RequestError as e:
                add_log(conn, f"Fare check failed (shopping) for {flight_row['confirmation_number']}: {e}", "warning", flight_row["id"])
                continue

            # Extract fare type from reservation bounds
            fare_type_bounds = reservation_info.get("bounds", [])
            bound_idx = 0 if target_bound_page == "outboundPage" else 1
            if bound_idx < len(fare_type_bounds):
                fare_details = fare_type_bounds[bound_idx].get("fareProductDetails", {})
                fare_type = fare_details.get("fareProductId", "")
            else:
                continue

            cards = shopping_response.get("changeShoppingPage", {}).get("flights", {}).get(target_bound_page, {}).get("cards", [])

            # Read fare check mode preference
            prefs = get_seat_preferences(conn)
            fare_mode = (prefs or {}).get("fare_check_mode", "same_day_nonstop")

            # Find lowest fare based on mode
            lowest_fare = None
            best_alt_flight = None
            best_alt_nonstop = False
            best_alt_stops = None
            best_alt_depart_time = None
            my_flight_fare_val = None

            for card in cards:
                card_flight_num = card.get("flightNumbers", "")
                card_nonstop = card.get("stopDescription", "") == "Nonstop"
                card_stops = card.get("stopDescription", "")
                card_depart_time = card.get("departureTime", "")
                is_my_flight = card_flight_num == flight_row["flight_number"]

                # Apply filter based on mode
                if fare_mode == "same_flight" and not is_my_flight:
                    continue
                elif fare_mode == "same_day_nonstop" and not card_nonstop:
                    continue
                # "same_day" mode: check all cards

                for fare in (card.get("fares") or []):
                    if fare.get("_meta", {}).get("fareProductId") == fare_type:
                        if "priceDifference" in fare:
                            price_diff = fare["priceDifference"]
                            sign = price_diff.get("sign", "")
                            amount = int(sign + price_diff["amount"].replace(",", ""))
                            currency = price_diff.get("currencyCode", "USD")

                            # Track my flight's fare separately
                            if is_my_flight:
                                my_flight_fare_val = amount

                            # Track overall lowest
                            if not lowest_fare or amount < lowest_fare["amount"]:
                                lowest_fare = {"amount": amount, "currencyCode": currency}
                                if not is_my_flight:
                                    best_alt_flight = card_flight_num
                                    best_alt_nonstop = card_nonstop
                                    best_alt_stops = card_stops
                                    best_alt_depart_time = card_depart_time
                                else:
                                    best_alt_flight = None
                                    best_alt_nonstop = False
                                    best_alt_stops = None
                                    best_alt_depart_time = None

            if not lowest_fare:
                lowest_fare = {"amount": 0, "currencyCode": "USD"}

            # Only keep alternative if it's actually cheaper than booked flight
            if best_alt_flight and my_flight_fare_val is not None:
                if lowest_fare["amount"] >= my_flight_fare_val:
                    best_alt_flight = None
                    best_alt_nonstop = False
                    best_alt_stops = None
                    best_alt_depart_time = None

            add_fare_check(
                conn, flight_row["id"], lowest_fare["amount"],
                lowest_fare.get("currencyCode", "USD"),
                best_flight_number=best_alt_flight,
                best_flight_nonstop=best_alt_nonstop,
                best_flight_stops=best_alt_stops,
                best_flight_depart_time=best_alt_depart_time,
                my_flight_fare=my_flight_fare_val,
            )
            price_str = f"{lowest_fare['amount']:+,} {lowest_fare['currencyCode']}"

            # Get previous fare check for deduplication
            prev_rows = conn.execute(
                "SELECT price_change FROM fare_history WHERE flight_id = ? ORDER BY checked_at DESC LIMIT 2",
                (flight_row["id"],),
            ).fetchall()
            prev_amount = prev_rows[1]["price_change"] if len(prev_rows) > 1 else None

            route = f"{flight_row['departure_airport']} -> {flight_row.get('destination_airport', '?')}"

            if best_alt_flight:
                stops_label = f" ({best_alt_stops})" if best_alt_stops else ""
                time_label = f" departs {best_alt_depart_time}" if best_alt_depart_time else ""
                my_fare_label = f" (your flight: {my_flight_fare_val:+,})" if my_flight_fare_val is not None else ""
                add_log(
                    conn,
                    f"Better flight for {flight_row['confirmation_number']} ({route}): "
                    f"WN {best_alt_flight}{stops_label}{time_label} at {price_str}{my_fare_label}",
                    "info",
                    flight_row["id"],
                )

            if lowest_fare["amount"] < -1:

                # Only send notification if fare dropped FURTHER than last check
                if prev_amount is None or lowest_fare["amount"] < prev_amount:
                    alt_info = ""
                    if best_alt_flight:
                        stops_tag = f" ({best_alt_stops})" if best_alt_stops else ""
                        time_tag = f" departs {best_alt_depart_time}" if best_alt_depart_time else ""
                        alt_info = f" - Better option: WN {best_alt_flight}{stops_tag}{time_tag}"
                    add_log(conn, f"NEW fare drop for {flight_row['confirmation_number']}: {price_str}{alt_info} (was {prev_amount})", "info", flight_row["id"])
                    try:
                        from notifications import notify_fare_drop
                        notify_msg = f"{price_str}{alt_info}"
                        notify_fare_drop(flight_row["confirmation_number"], route, notify_msg)
                    except Exception:
                        pass
                else:
                    add_log(conn, f"Fare unchanged since last check ({price_str}), skipping notification", "info", flight_row["id"])
            else:
                add_log(conn, f"Fare check for {flight_row['confirmation_number']}: {price_str}", "info", flight_row["id"])

        except Exception as e:
            logger.error("Error processing fare check for flight %s: %s", flight_row["id"], e)
            add_log(conn, f"Fare check error for {flight_row['confirmation_number']}: {e}", "error", flight_row["id"])

    last_fare_check = time.time()


SEAT_UPGRADE_COOLDOWN = 3 * 3600  # 3 hours between successful attempts per flight


def attempt_seat_upgrades(conn: sqlite3.Connection, force_flight_id: str | None = None) -> None:
    """For A-List accounts, attempt seat upgrade from 48h to 2h before departure.
    If force_flight_id is provided, only check that specific flight (bypasses cooldown)."""
    if not browser_session:
        add_log(conn, "Seat upgrade check: browser session not available", "warning")
        return

    if force_flight_id:
        # Manual check for a specific flight - bypass normal query
        rows = conn.execute(
            "SELECT f.*, r.confirmation_number, r.first_name, r.last_name "
            "FROM flights f JOIN reservations r ON r.id = f.reservation_id "
            "WHERE f.id = ?",
            (force_flight_id,),
        ).fetchall()
        flights = [dict(r) for r in rows]
        add_log(conn, f"Manual seat check triggered for flight {force_flight_id}", "info")
    else:
        flights = get_flights_for_seat_upgrade(conn)

    if not flights:
        return

    if not flights:
        return

    # Ensure browser is alive
    try:
        browser_session.ensure_alive()
    except Exception as e:
        add_log(conn, f"Browser session not available for seat upgrades: {e}", "error")
        return

    prefs = get_seat_preferences(conn)
    if not prefs:
        add_log(conn, "No seat preferences set, skipping seat upgrades", "info")
        return

    # Parse preferences
    preferred_letters = [l.strip() for l in prefs.get("preferred_letters", "A,F").split(",")]
    preferred_rows = [int(r.strip()) for r in prefs.get("preferred_rows", "1,2,3,4,5,6").split(",") if r.strip().isdigit()]
    fallback_letters = [l.strip() for l in prefs.get("fallback_letters", "A,C,D,F").split(",")]

    for flight_row in flights:
        flight_id = flight_row["id"]
        conf_num = flight_row["confirmation_number"]
        first_name = flight_row["first_name"]
        last_name = flight_row["last_name"]
        route = f"{flight_row['departure_airport']}->{flight_row.get('destination_airport', '?')}"
        current_seat = flight_row.get("assigned_seat", "")

        # Cooldown between automatic attempts (skipped for manual checks)
        if not force_flight_id:
            last_attempt = flight_row.get("last_seat_upgrade_attempt")
            if last_attempt:
                try:
                    last_dt = datetime.fromisoformat(last_attempt)
                    elapsed = (datetime.utcnow() - last_dt).total_seconds()
                    if elapsed < SEAT_UPGRADE_COOLDOWN:
                        logger.debug("Seat upgrade for %s: cooldown (%d min remaining)", conf_num, int((SEAT_UPGRADE_COOLDOWN - elapsed) / 60))
                        continue
                except Exception:
                    pass

        add_log(conn, f"Attempting seat upgrade for {conf_num} ({route}). Current seat: {current_seat or 'none'}", "info", flight_id)

        try:
            import os
            cap_dir = f"/app/data/captures/{flight_id}"
            os.makedirs(cap_dir, exist_ok=True)

            # Step 1: Find account credentials for this flight
            account_row = conn.execute(
                "SELECT a.username, a.password FROM accounts a "
                "JOIN reservations r ON r.account_id = a.id "
                "JOIN flights f ON f.reservation_id = r.id "
                "WHERE f.id = ?",
                (flight_id,),
            ).fetchone()

            if not account_row:
                add_log(conn, f"No account found for flight {conf_num}, cannot upgrade seat", "warning", flight_id)
                continue

            # Step 2: Restart browser and log into www.southwest.com directly
            # (DO NOT use login_and_get_reservations which navigates back to mobile.southwest.com)
            add_log(conn, f"Logging into www.southwest.com for seat upgrade of {conf_num}", "info", flight_id)
            browser_session.start()

            with browser_session._lock:
                driver = browser_session._driver

                # Navigate to login page on www.southwest.com
                driver.get("https://www.southwest.com/loyalty/myaccount")
                try:
                    driver.wait_for_element_visible('input[id="username"]', timeout=30)
                except Exception:
                    add_log(conn, f"Login form not found on www.southwest.com", "error", flight_id)
                    driver.save_screenshot(f"{cap_dir}/00_login_form_missing.png")
                    continue

                time.sleep(2)
                driver.type('input[id="username"]', account_row["username"])
                driver.type('input[id="password"]', f"{account_row['password']}\n")

                # Wait for login to complete
                time.sleep(8)
                driver.save_screenshot(f"{cap_dir}/00_after_login.png")
                add_log(conn, f"Login complete. URL: {driver.current_url}", "info", flight_id)

                # Step 3: Stay on account page (login landed us here)
                # The account page shows all trips with "Modify seats" buttons
                # No need to navigate to a lookup form
                time.sleep(5)  # Wait for trips to load
                driver.save_screenshot(f"{cap_dir}/01_account_page.png")
                add_log(conn, f"Account page loaded. URL: {driver.current_url}", "info", flight_id)

                # Step 4: Find and click "Modify seats" for the target confirmation number
                # Use JavaScript since CSS :contains() doesn't work in Selenium
                modify_result = driver.execute_script(f"""
                    // Strategy 1: Find the card/section with our confirmation number, then click its Modify seats link
                    var allElements = document.querySelectorAll('*');
                    var confFound = false;
                    for (var i = 0; i < allElements.length; i++) {{
                        var el = allElements[i];
                        var text = el.textContent || '';
                        // Find an element that contains our confirmation number
                        if (text.includes('{conf_num}') && el.children.length > 0) {{
                            // Look for a Modify seats link within this element's subtree
                            var links = el.querySelectorAll('a, button');
                            for (var j = 0; j < links.length; j++) {{
                                var linkText = links[j].textContent.trim().toLowerCase();
                                if (linkText.includes('modify seat') || linkText.includes('change seat')) {{
                                    links[j].click();
                                    return 'clicked: ' + links[j].textContent.trim() + ' for ' + '{conf_num}';
                                }}
                            }}
                        }}
                    }}

                    // Strategy 2: Just click the first "Modify seats" link on the page
                    var allLinks = document.querySelectorAll('a, button');
                    for (var k = 0; k < allLinks.length; k++) {{
                        var lt = allLinks[k].textContent.trim().toLowerCase();
                        if (lt === 'modify seats' || lt === 'modify seat') {{
                            allLinks[k].click();
                            return 'clicked first: ' + allLinks[k].textContent.trim();
                        }}
                    }}

                    // Strategy 3: Collect all visible link texts for diagnostics
                    var linkTexts = [];
                    var allA = document.querySelectorAll('a, button');
                    for (var m = 0; m < Math.min(allA.length, 50); m++) {{
                        var t = allA[m].textContent.trim().substring(0, 40);
                        if (t) linkTexts.push(t);
                    }}
                    return 'not found. Page links: ' + linkTexts.join(' | ');
                """)

                add_log(conn, f"Modify seats click result: {str(modify_result)[:300]}", "info", flight_id)

                if modify_result and modify_result.startswith("clicked"):
                    # Wait for seat map page to load
                    time.sleep(8)
                    driver.save_screenshot(f"{cap_dir}/02_after_modify_click.png")
                    add_log(conn, f"After Modify seats click. URL: {driver.current_url}", "info", flight_id)
                else:
                    # Modify seats not found on account page
                    driver.save_screenshot(f"{cap_dir}/02_no_modify_seats.png")
                    page_text = driver.execute_script("return document.body ? document.body.textContent.substring(0, 800) : ''")
                    add_log(conn, f"Modify seats button not found on account page. Body: {page_text[:300]}", "warning", flight_id)
                    log_diagnostic(conn, "seat_modify_not_found", driver.current_url,
                                   "Modify seats button on account page", str(modify_result)[:300],
                                   response_snapshot=page_text[:500])
                    continue

                # Step 5: Look for seat map OR check if we're already on seat map

                seat_loaded = False
                seat_selectors = [
                    "[data-seat-number]",
                    "[class*='seat'][class*='available']",
                    "button[class*='seat']",
                    "[class*='SeatMap']",
                    "[class*='seatMap']",
                    "[class*='seat-map']",
                    "[class*='seatmap']",
                    "table[class*='seat']",
                    "[role='grid']",
                ]
                for sel in seat_selectors:
                    try:
                        driver.wait_for_element_visible(sel, timeout=5)
                        seat_loaded = True
                        add_log(conn, f"Seat map loaded (selector: {sel})", "info", flight_id)
                        break
                    except Exception:
                        continue

                if not seat_loaded:
                    time.sleep(10)
                    add_log(conn, f"Seat map selectors not found, waited 10s. URL: {driver.current_url}", "warning", flight_id)

                # Step 5: Capture the seat map
                driver.save_screenshot(f"{cap_dir}/04_seat_map.png")
                dom = driver.execute_script("return document.documentElement.outerHTML")
                with open(f"{cap_dir}/seat_map_dom.html", "w") as f:
                    f.write(dom)
                add_log(conn, f"Seat map captured. URL: {driver.current_url}", "info", flight_id)

                # Record cooldown
                conn.execute("UPDATE flights SET last_seat_upgrade_attempt = ? WHERE id = ?",
                             (datetime.utcnow().isoformat(), flight_id))
                conn.commit()

                # Record in captures table
                manifest = json.dumps({
                    "flight_id": flight_id, "type": "seat_upgrade",
                    "files": [
                        {"name": "01_reservation_page.png", "type": "screenshot"},
                        {"name": "03_seat_map_loading.png", "type": "screenshot"},
                        {"name": "04_seat_map.png", "type": "screenshot"},
                        {"name": "seat_map_dom.html", "type": "dom"},
                    ],
                })
                conn.execute(
                    "INSERT INTO checkin_captures (flight_id, capture_dir, manifest_json, file_count, total_size_bytes) VALUES (?, ?, ?, ?, ?)",
                    (flight_id, cap_dir, manifest, 4, 0),
                )
                conn.commit()

                # Step 6: Extract seats from DOM
                seats_js = driver.execute_script("""
                    var seats = [];
                    // Strategy 1: data-seat-number attributes
                    document.querySelectorAll('[data-seat-number]').forEach(function(el) {
                        seats.push({seat: el.getAttribute('data-seat-number'), className: el.className, disabled: el.disabled || el.getAttribute('aria-disabled') === 'true', text: el.textContent.trim().substring(0, 20), tag: el.tagName});
                    });
                    // Strategy 2: buttons/divs with seat classes containing seat IDs
                    if (seats.length === 0) {
                        document.querySelectorAll('button[class*="seat"], div[class*="seat"], td[class*="seat"]').forEach(function(el) {
                            var text = el.textContent.trim();
                            if (text.match(/^\\d{1,2}[A-F]$/)) {
                                seats.push({seat: text, className: el.className, disabled: el.disabled || el.getAttribute('aria-disabled') === 'true', text: text, tag: el.tagName});
                            }
                        });
                    }
                    // Strategy 3: aria-label with seat info
                    if (seats.length === 0) {
                        document.querySelectorAll('[aria-label*="Seat"], [aria-label*="seat"], [aria-label*="Row"]').forEach(function(el) {
                            var label = el.getAttribute('aria-label') || '';
                            var match = label.match(/(\\d{1,2}[A-F])/);
                            if (match) {
                                seats.push({seat: match[1], className: el.className, disabled: el.disabled || el.getAttribute('aria-disabled') === 'true', text: label.substring(0, 50), tag: el.tagName});
                            }
                        });
                    }
                    var meta = {url: window.location.href, title: document.title, seatCount: seats.length, allButtons: document.querySelectorAll('button').length};
                    return JSON.stringify({seats: seats, meta: meta});
                """)

                try:
                    seats_data = json.loads(seats_js)
                except (json.JSONDecodeError, TypeError):
                    seats_data = {"seats": [], "meta": {}}

                all_seats = seats_data.get("seats", [])
                page_meta = seats_data.get("meta", {})
                add_log(conn, f"Page: {page_meta.get('title', '?')} | Found {len(all_seats)} seat elements | URL: {page_meta.get('url', '?')}", "info", flight_id)

                with open(f"{cap_dir}/seat_data.json", "w") as f:
                    json.dump(seats_data, f, indent=2)

                if not all_seats:
                    page_text = driver.execute_script("return document.body ? document.body.textContent.substring(0, 500) : ''")
                    add_log(conn, f"No seat elements found on page. Body preview: {page_text[:200]}", "warning", flight_id)
                    log_diagnostic(conn, "seat_map_empty", driver.current_url,
                                   "Seat elements", f"0 found. Buttons: {page_meta.get('allButtons')}",
                                   response_snapshot=page_text[:500])
                else:
                    # Step 7: Filter and score seats
                    available_seats = []
                    for s in all_seats:
                        seat_id = s.get("seat", "")
                        if not seat_id or s.get("disabled"):
                            continue
                        cls = (s.get("className") or "").lower()
                        if "unavailable" in cls or "occupied" in cls or "blocked" in cls:
                            continue
                        row_str, letter = "", ""
                        for ch in str(seat_id):
                            if ch.isdigit(): row_str += ch
                            elif ch.isalpha(): letter = ch.upper(); break
                        if row_str and letter:
                            row = int(row_str)
                            score = 20
                            if letter in preferred_letters and row in preferred_rows: score = 100
                            elif letter in preferred_letters: score = 80
                            elif letter in fallback_letters and row in preferred_rows: score = 60
                            elif letter in fallback_letters: score = 40
                            available_seats.append({"seat": seat_id, "row": row, "letter": letter, "score": score})

                    available_seats.sort(key=lambda x: (-x["score"], x["row"]))
                    add_log(conn, f"Available seats: {len(available_seats)} | Top 5: {[s['seat'] for s in available_seats[:5]]}", "info", flight_id)

                    if available_seats:
                        best = available_seats[0]
                        add_log(conn, f"Best seat: {best['seat']} (score {best['score']}), clicking...", "info", flight_id)

                        clicked = False
                        for click_sel in [f"[data-seat-number='{best['seat']}']", f"button:contains('{best['seat']}')", f"[aria-label*='{best['seat']}']"]:
                            try:
                                driver.click(click_sel)
                                clicked = True
                                add_log(conn, f"Clicked seat {best['seat']}", "info", flight_id)
                                break
                            except Exception:
                                continue

                        if clicked:
                            time.sleep(2)
                            driver.save_screenshot(f"{cap_dir}/05_after_click.png")

                            for confirm_sel in ["button:contains('Continue')", "button:contains('Confirm')", "button:contains('Save')", "button:contains('Done')", "button[type='submit']"]:
                                try:
                                    if driver.is_element_visible(confirm_sel):
                                        driver.click(confirm_sel)
                                        add_log(conn, f"Clicked confirm: {confirm_sel}", "info", flight_id)
                                        time.sleep(3)
                                        driver.save_screenshot(f"{cap_dir}/06_after_confirm.png")
                                        break
                                except Exception:
                                    continue

                            update_flight_seat(conn, flight_id, best["seat"])
                            add_log(conn, f"Seat {best['seat']} selected for {conf_num}!", "info", flight_id)
                            try:
                                from notifications import send_notification
                                send_notification(f"Seat Selected: {conf_num}", f"Seat {best['seat']} selected for {route}")
                            except Exception:
                                pass
                        else:
                            add_log(conn, f"Could not click seat {best['seat']}", "warning", flight_id)

                # Step 8: Navigate back to mobile site
                driver.get("https://mobile.southwest.com/login?webView=true")
                time.sleep(2)
                browser_session._headers_set = False
                try:
                    browser_session._wait_for_headers()
                except Exception:
                    pass

        except Exception as e:
            logger.error("Seat upgrade error for %s: %s", conf_num, e)
            add_log(conn, f"Seat upgrade error: {e}", "error", flight_id)
            try:
                browser_session._driver.save_screenshot(f"/app/data/captures/{flight_id}/error.png")
            except Exception:
                pass



def process_manual_seat_checks(conn: sqlite3.Connection) -> None:
    """Check for manual seat check requests and execute them."""
    rows = conn.execute(
        "SELECT id, message FROM worker_logs WHERE message LIKE '__CHECK_SEATS_%' ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    for row in rows:
        conn.execute("DELETE FROM worker_logs WHERE id = ?", (row["id"],))
        conn.commit()
        # Extract flight_id from marker: __CHECK_SEATS_{flight_id}__
        marker = row["message"]
        flight_id = marker.replace("__CHECK_SEATS_", "").replace("__", "")
        if flight_id:
            add_log(conn, f"Manual seat check requested for flight {flight_id}", "info")
            attempt_seat_upgrades(conn, force_flight_id=flight_id)


def process_test_notifications(conn: sqlite3.Connection) -> None:
    """Check for test notification requests and send them."""
    rows = conn.execute(
        "SELECT id FROM worker_logs WHERE message = '__TEST_NOTIFICATION__' ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    if rows:
        # Delete the test markers
        for row in rows:
            conn.execute("DELETE FROM worker_logs WHERE id = ?", (row["id"],))
        conn.commit()
        # Send the test notification
        try:
            from notifications import notify_test
            notify_test()
            add_log(conn, "Test notification sent successfully", "info")
        except Exception as e:
            add_log(conn, f"Test notification failed: {e}", "error")


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

            # Process manual seat check requests
            process_manual_seat_checks(conn)

            # Process test notification requests
            process_test_notifications(conn)

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
