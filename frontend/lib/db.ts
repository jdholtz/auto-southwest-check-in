import Database from "better-sqlite3";
import path from "path";
import fs from "fs";

const DB_PATH = process.env.DB_PATH || path.resolve("/app", "data", "checkin.db");

// Ensure data directory exists
fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });

let _db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!_db) {
    _db = new Database(DB_PATH);
    _db.pragma("journal_mode = WAL");
    _db.pragma("foreign_keys = ON");
    initTables(_db);
  }
  return _db;
}

function initTables(db: Database.Database) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS accounts (
      id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
      username TEXT NOT NULL,
      password TEXT NOT NULL,
      is_active INTEGER DEFAULT 1,
      retrieval_interval INTEGER DEFAULT 24,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS reservations (
      id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
      account_id TEXT REFERENCES accounts(id) ON DELETE CASCADE,
      confirmation_number TEXT NOT NULL,
      first_name TEXT NOT NULL,
      last_name TEXT NOT NULL,
      is_active INTEGER DEFAULT 1,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS flights (
      id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
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
      id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
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
  `);
}
