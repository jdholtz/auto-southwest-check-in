import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export function GET() {
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

  const flights = db
    .prepare(
      `SELECT f.*, r.confirmation_number, r.first_name, r.last_name
       FROM flights f
       JOIN reservations r ON r.id = f.reservation_id
       ORDER BY f.departure_time ASC`
    )
    .all();

  // Attach latest fare check for each flight
  const result = (flights as { id: string }[]).map((f) => {
    const latestFare = db
      .prepare(
        "SELECT price_change, currency_code, checked_at FROM fare_history WHERE flight_id = ? ORDER BY checked_at DESC LIMIT 1"
      )
      .get(f.id) as { price_change: number; currency_code: string; checked_at: string } | undefined;

    const firstFare = db
      .prepare(
        "SELECT price_change, currency_code, checked_at FROM fare_history WHERE flight_id = ? ORDER BY checked_at ASC LIMIT 1"
      )
      .get(f.id) as { price_change: number; currency_code: string; checked_at: string } | undefined;

    return {
      ...f,
      latest_fare: latestFare || null,
      baseline_fare: firstFare || null,
    };
  });

  return NextResponse.json(result);
}
