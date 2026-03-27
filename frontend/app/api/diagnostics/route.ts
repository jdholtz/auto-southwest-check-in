import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export function GET(req: NextRequest) {
  const db = getDb();

  // Ensure diagnostics table exists
  db.exec(`
    CREATE TABLE IF NOT EXISTS diagnostics (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      category TEXT NOT NULL,
      endpoint TEXT,
      expected_behavior TEXT,
      actual_behavior TEXT,
      headers_snapshot TEXT,
      response_snapshot TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    )
  `);

  const { searchParams } = new URL(req.url);
  const category = searchParams.get("category");
  const limit = parseInt(searchParams.get("limit") || "50", 10);
  const offset = parseInt(searchParams.get("offset") || "0", 10);

  let query = "SELECT * FROM diagnostics";
  const params: unknown[] = [];

  if (category && category !== "all") {
    query += " WHERE category = ?";
    params.push(category);
  }

  query += " ORDER BY created_at DESC LIMIT ? OFFSET ?";
  params.push(limit, offset);

  const diagnostics = db.prepare(query).all(...params);
  const total = (
    category && category !== "all"
      ? db.prepare("SELECT COUNT(*) as count FROM diagnostics WHERE category = ?").get(category)
      : db.prepare("SELECT COUNT(*) as count FROM diagnostics").get()
  ) as { count: number };

  // Get distinct categories
  const categories = db
    .prepare("SELECT DISTINCT category FROM diagnostics ORDER BY category")
    .all()
    .map((r: unknown) => (r as { category: string }).category);

  return NextResponse.json({
    diagnostics,
    total: total.count,
    categories,
  });
}
