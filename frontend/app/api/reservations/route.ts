import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export function GET() {
  const db = getDb();

  // Single JOIN query instead of fetching all flights separately
  const rows = db
    .prepare(
      `SELECT r.*, a.username as account_username,
              f.id as flight_id, f.flight_number, f.departure_airport,
              f.destination_airport, f.departure_time, f.is_international,
              f.checkin_status, f.checkin_result, f.checkin_attempted_at,
              f.assigned_seat, f.original_price, f.original_currency
       FROM reservations r
       LEFT JOIN accounts a ON a.id = r.account_id
       LEFT JOIN flights f ON f.reservation_id = r.id
       ORDER BY r.created_at DESC, f.departure_time ASC`
    )
    .all() as Record<string, unknown>[];

  // Group flights under their reservation
  const reservationMap = new Map<string, Record<string, unknown>>();
  for (const row of rows) {
    const resId = row.id as string;
    if (!reservationMap.has(resId)) {
      const { flight_id, flight_number, departure_airport, destination_airport,
              departure_time, is_international, checkin_status, checkin_result,
              checkin_attempted_at, assigned_seat, original_price, original_currency,
              ...reservation } = row;
      reservationMap.set(resId, { ...reservation, flights: [] });
    }
    if (row.flight_id) {
      (reservationMap.get(resId)!.flights as unknown[]).push({
        id: row.flight_id,
        flight_number: row.flight_number,
        departure_airport: row.departure_airport,
        destination_airport: row.destination_airport,
        departure_time: row.departure_time,
        is_international: row.is_international,
        checkin_status: row.checkin_status,
        checkin_result: row.checkin_result,
        checkin_attempted_at: row.checkin_attempted_at,
        assigned_seat: row.assigned_seat,
        original_price: row.original_price,
        original_currency: row.original_currency,
      });
    }
  }

  return NextResponse.json(Array.from(reservationMap.values()));
}

export async function POST(req: NextRequest) {
  const { confirmation_number, first_name, last_name } = await req.json();
  if (!confirmation_number || !first_name || !last_name) {
    return NextResponse.json(
      { error: "Confirmation number, first name, and last name required" },
      { status: 400 }
    );
  }
  const db = getDb();
  const id = crypto.randomUUID();
  db.prepare(
    "INSERT INTO reservations (id, confirmation_number, first_name, last_name) VALUES (?, ?, ?, ?)"
  ).run(id, confirmation_number.toUpperCase(), first_name, last_name);
  const reservation = db.prepare("SELECT * FROM reservations WHERE id = ?").get(id);
  return NextResponse.json(reservation, { status: 201 });
}
