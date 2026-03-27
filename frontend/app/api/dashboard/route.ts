import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export function GET() {
  const db = getDb();
  const now = new Date().toISOString();

  const activeAccounts = (db.prepare("SELECT COUNT(*) as count FROM accounts WHERE is_active = 1").get() as { count: number }).count;
  const totalReservations = (db.prepare("SELECT COUNT(*) as count FROM reservations WHERE is_active = 1").get() as { count: number }).count;
  const upcomingCheckins = (db.prepare(
    "SELECT COUNT(*) as count FROM flights WHERE checkin_status IN ('pending', 'scheduled') AND departure_time > ?"
  ).get(now) as { count: number }).count;
  const successfulCheckins = (db.prepare("SELECT COUNT(*) as count FROM flights WHERE checkin_status = 'success'").get() as { count: number }).count;
  const failedCheckins = (db.prepare("SELECT COUNT(*) as count FROM flights WHERE checkin_status = 'failed'").get() as { count: number }).count;

  const upcomingFlights = db
    .prepare(
      `SELECT f.*, r.confirmation_number, r.first_name, r.last_name
       FROM flights f
       JOIN reservations r ON r.id = f.reservation_id
       WHERE f.checkin_status IN ('pending', 'scheduled')
       AND f.departure_time > ?
       ORDER BY f.departure_time ASC
       LIMIT 5`
    )
    .all(now);

  const recentLogs = db
    .prepare("SELECT * FROM worker_logs ORDER BY created_at DESC LIMIT 20")
    .all();

  return NextResponse.json({
    stats: {
      active_accounts: activeAccounts,
      total_reservations: totalReservations,
      upcoming_checkins: upcomingCheckins,
      successful_checkins: successfulCheckins,
      failed_checkins: failedCheckins,
    },
    upcoming_flights: upcomingFlights,
    recent_logs: recentLogs,
  });
}
