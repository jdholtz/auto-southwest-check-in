import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const db = getDb();
  // Ensure fare_history table exists
  db.exec(`
    CREATE TABLE IF NOT EXISTS fare_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      flight_id TEXT NOT NULL,
      price_change INTEGER NOT NULL,
      currency_code TEXT NOT NULL DEFAULT 'USD',
      checked_at TEXT DEFAULT (datetime('now'))
    )
  `);
  const fares = db
    .prepare("SELECT * FROM fare_history WHERE flight_id = ? ORDER BY checked_at DESC LIMIT 50")
    .all(params.id);
  return NextResponse.json(fares);
}
