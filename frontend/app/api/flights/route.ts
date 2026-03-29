import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export function GET() {
  const db = getDb();

  // Ensure fare_history table exists with all columns
  db.exec(`
    CREATE TABLE IF NOT EXISTS fare_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      flight_id TEXT NOT NULL,
      price_change INTEGER NOT NULL,
      currency_code TEXT NOT NULL DEFAULT 'USD',
      best_flight_number TEXT,
      best_flight_nonstop INTEGER DEFAULT 0,
      best_flight_stops TEXT,
      best_flight_depart_time TEXT,
      my_flight_fare INTEGER,
      checked_at TEXT DEFAULT (datetime('now'))
    )
  `);

  const now = new Date().toISOString();
  const flights = db
    .prepare(
      `SELECT f.*, r.confirmation_number, r.first_name, r.last_name
       FROM flights f
       JOIN reservations r ON r.id = f.reservation_id
       WHERE f.departure_time > ?
       ORDER BY f.departure_time ASC`
    )
    .all(now);

  // Attach latest fare check for each flight (with alternative flight data)
  const result = (flights as { id: string }[]).map((f) => {
    const latestFare = db
      .prepare(
        `SELECT price_change, currency_code, checked_at,
                best_flight_number, best_flight_nonstop, best_flight_stops,
                best_flight_depart_time, my_flight_fare
         FROM fare_history WHERE flight_id = ? ORDER BY checked_at DESC LIMIT 1`
      )
      .get(f.id);

    const firstFare = db
      .prepare(
        "SELECT price_change, currency_code, checked_at FROM fare_history WHERE flight_id = ? ORDER BY checked_at ASC LIMIT 1"
      )
      .get(f.id);

    return {
      ...f,
      latest_fare: latestFare || null,
      baseline_fare: firstFare || null,
    };
  });

  return NextResponse.json(result);
}
