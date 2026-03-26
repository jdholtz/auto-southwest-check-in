import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export function GET() {
  const db = getDb();
  const reservations = db
    .prepare(
      `SELECT r.*, a.username as account_username
       FROM reservations r
       LEFT JOIN accounts a ON a.id = r.account_id
       ORDER BY r.created_at DESC`
    )
    .all();

  // Attach flights to each reservation
  const flights = db.prepare("SELECT * FROM flights ORDER BY departure_time ASC").all();
  const flightsByReservation = new Map<string, unknown[]>();
  for (const f of flights as { reservation_id: string }[]) {
    const list = flightsByReservation.get(f.reservation_id) || [];
    list.push(f);
    flightsByReservation.set(f.reservation_id, list);
  }

  const result = (reservations as { id: string }[]).map((r) => ({
    ...r,
    flights: flightsByReservation.get(r.id) || [],
  }));

  return NextResponse.json(result);
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
