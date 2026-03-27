import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export function GET(req: NextRequest) {
  const db = getDb();
  const { searchParams } = new URL(req.url);
  const level = searchParams.get("level");
  const limit = parseInt(searchParams.get("limit") || "50", 10);
  const offset = parseInt(searchParams.get("offset") || "0", 10);

  let query = `SELECT w.*, f.flight_number, f.departure_airport, f.destination_airport
               FROM worker_logs w
               LEFT JOIN flights f ON f.id = w.flight_id`;
  const params: unknown[] = [];

  if (level && level !== "all") {
    query += " WHERE w.level = ?";
    params.push(level);
  }

  query += " ORDER BY w.created_at DESC LIMIT ? OFFSET ?";
  params.push(limit, offset);

  const logs = db.prepare(query).all(...params);

  const totalQuery = level && level !== "all"
    ? db.prepare("SELECT COUNT(*) as count FROM worker_logs WHERE level = ?").get(level)
    : db.prepare("SELECT COUNT(*) as count FROM worker_logs").get();

  return NextResponse.json({
    logs,
    total: (totalQuery as { count: number }).count,
  });
}
