import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

function ensureTable(db: ReturnType<typeof getDb>) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS seat_preferences (
      id TEXT PRIMARY KEY DEFAULT 'default',
      preferred_letters TEXT DEFAULT 'A,F',
      preferred_rows TEXT DEFAULT '1,2,3,4,5,6',
      fallback_letters TEXT DEFAULT 'A,C,D,F',
      fare_check_mode TEXT DEFAULT 'same_day_nonstop',
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now'))
    )
  `);
  // Migration: add fare_check_mode if missing
  const cols = db.prepare("PRAGMA table_info(seat_preferences)").all() as { name: string }[];
  if (!cols.some((c) => c.name === "fare_check_mode")) {
    db.exec("ALTER TABLE seat_preferences ADD COLUMN fare_check_mode TEXT DEFAULT 'same_day_nonstop'");
  }
}

export function GET() {
  const db = getDb();
  ensureTable(db);
  let prefs = db.prepare("SELECT * FROM seat_preferences WHERE id = 'default'").get();
  if (!prefs) {
    db.prepare("INSERT INTO seat_preferences (id) VALUES ('default')").run();
    prefs = db.prepare("SELECT * FROM seat_preferences WHERE id = 'default'").get();
  }
  return NextResponse.json(prefs);
}

export async function POST(req: NextRequest) {
  const db = getDb();
  ensureTable(db);
  const { preferred_letters, preferred_rows, fallback_letters, fare_check_mode } = await req.json();

  const existing = db.prepare("SELECT id FROM seat_preferences WHERE id = 'default'").get();
  if (existing) {
    db.prepare(
      "UPDATE seat_preferences SET preferred_letters = ?, preferred_rows = ?, fallback_letters = ?, fare_check_mode = ?, updated_at = datetime('now') WHERE id = 'default'"
    ).run(preferred_letters, preferred_rows, fallback_letters, fare_check_mode || "same_day_nonstop");
  } else {
    db.prepare(
      "INSERT INTO seat_preferences (id, preferred_letters, preferred_rows, fallback_letters, fare_check_mode) VALUES ('default', ?, ?, ?, ?)"
    ).run(preferred_letters, preferred_rows, fallback_letters, fare_check_mode || "same_day_nonstop");
  }

  const prefs = db.prepare("SELECT * FROM seat_preferences WHERE id = 'default'").get();
  return NextResponse.json(prefs);
}
