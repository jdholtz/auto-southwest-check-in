import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export function GET() {
  const db = getDb();
  const flights = db
    .prepare(
      `SELECT f.*, r.confirmation_number, r.first_name, r.last_name
       FROM flights f
       JOIN reservations r ON r.id = f.reservation_id
       ORDER BY f.departure_time ASC`
    )
    .all();
  return NextResponse.json(flights);
}
