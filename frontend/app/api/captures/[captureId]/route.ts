import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export function GET(_req: NextRequest, { params }: { params: { captureId: string } }) {
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
  const capture = db
    .prepare("SELECT * FROM checkin_captures WHERE id = ?")
    .get(params.captureId);
  if (!capture) {
    return NextResponse.json({ error: "Capture not found" }, { status: 404 });
  }
  return NextResponse.json(capture);
}
