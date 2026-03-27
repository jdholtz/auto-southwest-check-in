"""SQLite database client for the check-in worker."""

import json
import os
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.environ.get("DB_PATH", os.path.join("/app", "data", "checkin.db"))


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_tables(conn)
    _migrate(conn)
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            retrieval_interval INTEGER DEFAULT 24,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS reservations (
            id TEXT PRIMARY KEY,
            account_id TEXT REFERENCES accounts(id) ON DELETE CASCADE,
            confirmation_number TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS flights (
            id TEXT PRIMARY KEY,
            reservation_id TEXT NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
            flight_number TEXT,
            departure_airport TEXT,
            destination_airport TEXT,
            departure_time TEXT NOT NULL,
            is_international INTEGER DEFAULT 0,
            checkin_status TEXT DEFAULT 'pending',
            checkin_result TEXT,
            checkin_attempted_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS fare_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_id TEXT NOT NULL REFERENCES flights(id) ON DELETE CASCADE,
            price_change INTEGER NOT NULL,
            currency_code TEXT NOT NULL DEFAULT 'USD',
            checked_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS seat_preferences (
            id TEXT PRIMARY KEY DEFAULT 'default',
            preferred_letters TEXT DEFAULT 'A,F',
            preferred_rows TEXT DEFAULT '1,2,3,4,5,6',
            fallback_letters TEXT DEFAULT 'A,C,D,F',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS notification_configs (
            id TEXT PRIMARY KEY,
            service_url TEXT NOT NULL,
            notification_level INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS worker_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_id TEXT REFERENCES flights(id) ON DELETE SET NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS diagnostics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            endpoint TEXT,
            expected_behavior TEXT,
            actual_behavior TEXT,
            headers_snapshot TEXT,
            response_snapshot TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS checkin_captures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flight_id TEXT NOT NULL REFERENCES flights(id) ON DELETE CASCADE,
            capture_dir TEXT NOT NULL,
            manifest_json TEXT,
            file_count INTEGER DEFAULT 0,
            total_size_bytes INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )


def _migrate(conn: sqlite3.Connection) -> None:
    """Run schema migrations that can't be handled by CREATE TABLE IF NOT EXISTS."""
    # Flights table migrations
    flight_cols = [row[1] for row in conn.execute("PRAGMA table_info(flights)").fetchall()]
    if "reservation_info_json" not in flight_cols:
        conn.execute("ALTER TABLE flights ADD COLUMN reservation_info_json TEXT")
    if "assigned_seat" not in flight_cols:
        conn.execute("ALTER TABLE flights ADD COLUMN assigned_seat TEXT")

    # Accounts table migrations
    account_cols = [row[1] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()]
    if "is_alist" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN is_alist INTEGER DEFAULT 0")
    if "auto_upgrade_seats" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN auto_upgrade_seats INTEGER DEFAULT 0")
    if "display_name" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN display_name TEXT DEFAULT ''")

    conn.commit()


def get_active_accounts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM accounts WHERE is_active = 1").fetchall()
    return [dict(r) for r in rows]


def get_active_reservations(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM reservations WHERE is_active = 1").fetchall()
    return [dict(r) for r in rows]


def get_pending_flights(conn: sqlite3.Connection) -> list[dict]:
    now = datetime.utcnow().isoformat()
    rows = conn.execute(
        "SELECT f.*, r.confirmation_number, r.first_name, r.last_name "
        "FROM flights f JOIN reservations r ON r.id = f.reservation_id "
        "WHERE f.checkin_status IN ('pending', 'scheduled') "
        "AND f.departure_time > ? "
        "ORDER BY f.departure_time ASC",
        (now,),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_flight(
    conn: sqlite3.Connection,
    reservation_id: str,
    flight_number: str,
    departure_airport: str,
    destination_airport: str,
    departure_time: str,
    is_international: bool,
) -> str:
    """Insert a flight or return existing flight id if it already exists."""
    existing = conn.execute(
        "SELECT id FROM flights WHERE reservation_id = ? AND flight_number = ? AND departure_time = ?",
        (reservation_id, flight_number, departure_time),
    ).fetchone()
    if existing:
        # Always update airports if the new value is non-empty (fixes stale/wrong data)
        conn.execute(
            "UPDATE flights SET "
            "departure_airport = CASE WHEN ? != '' THEN ? ELSE departure_airport END, "
            "destination_airport = CASE WHEN ? != '' THEN ? ELSE destination_airport END "
            "WHERE id = ?",
            (departure_airport, departure_airport, destination_airport, destination_airport, existing["id"]),
        )
        conn.commit()
        return existing["id"]

    import uuid

    flight_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO flights (id, reservation_id, flight_number, departure_airport, "
        "destination_airport, departure_time, is_international) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            flight_id,
            reservation_id,
            flight_number,
            departure_airport,
            destination_airport,
            departure_time,
            1 if is_international else 0,
        ),
    )
    conn.commit()
    return flight_id


def update_flight_status(
    conn: sqlite3.Connection,
    flight_id: str,
    status: str,
    result: str | None = None,
) -> None:
    if result:
        conn.execute(
            "UPDATE flights SET checkin_status = ?, checkin_result = ?, "
            "checkin_attempted_at = datetime('now') WHERE id = ?",
            (status, result, flight_id),
        )
    else:
        conn.execute(
            "UPDATE flights SET checkin_status = ? WHERE id = ?",
            (status, flight_id),
        )
    conn.commit()


def add_log(
    conn: sqlite3.Connection,
    message: str,
    level: str = "info",
    flight_id: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO worker_logs (flight_id, level, message) VALUES (?, ?, ?)",
        (flight_id, level, message),
    )
    conn.commit()


def upsert_reservation(
    conn: sqlite3.Connection,
    account_id: str,
    confirmation_number: str,
    first_name: str,
    last_name: str,
) -> str:
    """Insert or update a reservation tied to an account. Returns the reservation id."""
    existing = conn.execute(
        "SELECT id FROM reservations WHERE account_id = ? AND confirmation_number = ?",
        (account_id, confirmation_number),
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE reservations SET first_name = ?, last_name = ?, is_active = 1, "
            "updated_at = datetime('now') WHERE id = ?",
            (first_name, last_name, existing["id"]),
        )
        conn.commit()
        return existing["id"]

    import uuid
    res_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO reservations (id, account_id, confirmation_number, first_name, last_name) "
        "VALUES (?, ?, ?, ?, ?)",
        (res_id, account_id, confirmation_number, first_name, last_name),
    )
    conn.commit()
    return res_id


def deactivate_stale_reservations(
    conn: sqlite3.Connection,
    account_id: str,
    active_confirmation_numbers: list[str],
) -> None:
    """Mark reservations as inactive if they're no longer returned by the API."""
    if not active_confirmation_numbers:
        return
    placeholders = ",".join("?" for _ in active_confirmation_numbers)
    conn.execute(
        f"UPDATE reservations SET is_active = 0, updated_at = datetime('now') "
        f"WHERE account_id = ? AND confirmation_number NOT IN ({placeholders})",
        [account_id] + active_confirmation_numbers,
    )
    conn.commit()


def log_diagnostic(
    conn: sqlite3.Connection,
    category: str,
    endpoint: str = "",
    expected_behavior: str = "",
    actual_behavior: str = "",
    headers_snapshot: str = "",
    response_snapshot: str = "",
) -> None:
    """Log a structured diagnostic entry for API/behavior changes."""
    conn.execute(
        "INSERT INTO diagnostics (category, endpoint, expected_behavior, actual_behavior, "
        "headers_snapshot, response_snapshot) VALUES (?, ?, ?, ?, ?, ?)",
        (category, endpoint, expected_behavior, actual_behavior,
         headers_snapshot, response_snapshot[:1000]),
    )
    conn.commit()
    # Also write to worker_logs for visibility in the activity feed
    add_log(
        conn,
        f"[DIAGNOSTIC:{category}] {endpoint} - Expected: {expected_behavior}, Got: {actual_behavior}",
        "warning",
    )


def add_fare_check(
    conn: sqlite3.Connection,
    flight_id: str,
    price_change: int,
    currency_code: str = "USD",
) -> None:
    conn.execute(
        "INSERT INTO fare_history (flight_id, price_change, currency_code) VALUES (?, ?, ?)",
        (flight_id, price_change, currency_code),
    )
    conn.commit()


def update_flight_reservation_info(
    conn: sqlite3.Connection,
    flight_id: str,
    reservation_info_json: str,
) -> None:
    conn.execute(
        "UPDATE flights SET reservation_info_json = ? WHERE id = ?",
        (reservation_info_json, flight_id),
    )
    conn.commit()


def get_flights_for_fare_check(conn: sqlite3.Connection) -> list[dict]:
    """Get flights that have reservation_info and are still upcoming."""
    now = datetime.utcnow().isoformat()
    rows = conn.execute(
        "SELECT f.*, r.confirmation_number, r.first_name, r.last_name "
        "FROM flights f JOIN reservations r ON r.id = f.reservation_id "
        "WHERE f.reservation_info_json IS NOT NULL "
        "AND f.reservation_info_json != '' "
        "AND f.departure_time > ? "
        "AND f.checkin_status IN ('pending', 'scheduled') "
        "ORDER BY f.departure_time ASC",
        (now,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_seat_preferences(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT * FROM seat_preferences WHERE id = 'default'").fetchone()
    return dict(row) if row else None


def update_flight_seat(conn: sqlite3.Connection, flight_id: str, seat: str) -> None:
    conn.execute("UPDATE flights SET assigned_seat = ? WHERE id = ?", (seat, flight_id))
    conn.commit()


def get_flights_for_seat_upgrade(conn: sqlite3.Connection) -> list[dict]:
    """Get flights departing in 47-49 hours linked to A-List accounts with auto_upgrade enabled."""
    now = datetime.utcnow().isoformat()
    hours_47 = (datetime.utcnow() + timedelta(hours=47)).isoformat()
    hours_49 = (datetime.utcnow() + timedelta(hours=49)).isoformat()
    rows = conn.execute(
        "SELECT f.*, r.confirmation_number, r.first_name, r.last_name, a.is_alist, a.auto_upgrade_seats "
        "FROM flights f "
        "JOIN reservations r ON r.id = f.reservation_id "
        "LEFT JOIN accounts a ON a.id = r.account_id "
        "WHERE f.departure_time BETWEEN ? AND ? "
        "AND a.is_alist = 1 AND a.auto_upgrade_seats = 1 "
        "AND (f.assigned_seat IS NULL OR f.assigned_seat = '') "
        "ORDER BY f.departure_time ASC",
        (hours_47, hours_49),
    ).fetchall()
    return [dict(r) for r in rows]


def get_notification_configs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM notification_configs WHERE is_active = 1"
    ).fetchall()
    return [dict(r) for r in rows]
