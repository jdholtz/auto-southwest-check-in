import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

export function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const id = searchParams.get("id");
  const fileName = searchParams.get("name");

  if (!id || !fileName) {
    return NextResponse.json({ error: "id and name required" }, { status: 400 });
  }

  const safeName = path.basename(fileName);
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

  const capture = db.prepare("SELECT capture_dir FROM checkin_captures WHERE id = ?").get(id) as { capture_dir: string } | undefined;
  if (!capture) return NextResponse.json({ error: "Capture not found" }, { status: 404 });

  const filePath = path.join(capture.capture_dir, safeName);
  if (!fs.existsSync(filePath)) return NextResponse.json({ error: "File not found" }, { status: 404 });

  const fileBuffer = fs.readFileSync(filePath);
  const ext = path.extname(safeName).toLowerCase();
  const mimeTypes: Record<string, string> = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".json": "application/json", ".html": "text/html", ".txt": "text/plain",
  };

  return new NextResponse(fileBuffer, {
    headers: {
      "Content-Type": mimeTypes[ext] || "application/octet-stream",
      "Content-Disposition": `inline; filename="${safeName}"`,
    },
  });
}
