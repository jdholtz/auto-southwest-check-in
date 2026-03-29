import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const { flight_id } = await req.json();
  if (!flight_id) {
    return NextResponse.json({ error: "flight_id required" }, { status: 400 });
  }

  const db = getDb();
  db.prepare(
    "INSERT INTO worker_logs (level, message) VALUES ('info', ?)"
  ).run(`__CHECK_SEATS_${flight_id}__`);

  return NextResponse.json({
    ok: true,
    message: "Seat check queued. The worker will process it within 60 seconds.",
  });
}
