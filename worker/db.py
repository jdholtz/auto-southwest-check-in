"""SQLite database client for the check-in worker."""

import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "checkin.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_tables(conn)
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
        """
    )


def get_active_accounts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM accounts WHERE is_active = 1").fetchall()
    return [dict(r) for r in rows]


def get_active_reservations(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM reservations WHERE is_active = 1").fetchall()
    return [dict(r) for r in rows]


def get_pending_flights(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT f.*, r.confirmation_number, r.first_name, r.last_name "
        "FROM flights f JOIN reservations r ON r.id = f.reservation_id "
        "WHERE f.checkin_status IN ('pending', 'scheduled') "
        "AND f.departure_time > datetime('now') "
        "ORDER BY f.departure_time ASC"
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


def get_notification_configs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM notification_configs WHERE is_active = 1"
    ).fetchall()
    return [dict(r) for r in rows]
