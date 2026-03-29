import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const id = searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });

  const db = getDb();
  db.exec(`
    CREATE TABLE IF NOT EXISTS checkin_captures (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      flight_id TEXT NOT NULL,
      capture_dir TEXT NOT NULL,
      manifest_json TEXT,
      file_count INTEGER DEFAULT 0,
      total_size_bytes INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now'))
    )
  `);
  const captures = db
    .prepare("SELECT * FROM checkin_captures WHERE flight_id = ? ORDER BY created_at DESC")
    .all(id);
  return NextResponse.json(captures);
}
