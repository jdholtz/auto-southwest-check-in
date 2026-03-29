import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export function GET() {
  let dbStatus = "unknown";
  let flightCount = 0;
  let accountCount = 0;

  try {
    const db = getDb();
    flightCount = (db.prepare("SELECT COUNT(*) as count FROM flights").get() as { count: number }).count;
    accountCount = (db.prepare("SELECT COUNT(*) as count FROM accounts").get() as { count: number }).count;
    dbStatus = "connected";
  } catch (e) {
    dbStatus = `error: ${e}`;
  }

  const routes = [
    "/api/flights",
    "/api/flights/logs",
    "/api/flights/fares",
    "/api/flights/captures",
    "/api/flights/update",
    "/api/accounts",
    "/api/reservations",
    "/api/dashboard",
    "/api/activity",
    "/api/diagnostics",
    "/api/notifications",
    "/api/preferences",
    "/api/captures/detail",
    "/api/captures/files",
    "/api/health",
  ];

  return NextResponse.json({
    status: "ok",
    timestamp: new Date().toISOString(),
    database: dbStatus,
    flights: flightCount,
    accounts: accountCount,
    routes,
  });
}
