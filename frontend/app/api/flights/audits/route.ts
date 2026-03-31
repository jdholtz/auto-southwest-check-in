import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const id = searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });

  const db = getDb();
  db.exec(`
    CREATE TABLE IF NOT EXISTS seat_upgrade_audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      flight_id TEXT NOT NULL,
      started_at TEXT,
      completed_at TEXT,
      status TEXT DEFAULT 'in_progress',
      steps_json TEXT,
      browser_console_json TEXT,
      capture_dir TEXT,
      error_message TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    )
  `);

  const audits = db
    .prepare("SELECT * FROM seat_upgrade_audit WHERE flight_id = ? ORDER BY created_at DESC LIMIT 10")
    .all(id);
  return NextResponse.json(audits);
}
