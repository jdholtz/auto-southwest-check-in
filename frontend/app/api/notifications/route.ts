import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export function GET() {
  const db = getDb();
  const configs = db.prepare("SELECT * FROM notification_configs ORDER BY rowid").all();
  return NextResponse.json(configs);
}

export async function POST(req: NextRequest) {
  const { service_url, notification_level } = await req.json();
  if (!service_url) {
    return NextResponse.json({ error: "Service URL required" }, { status: 400 });
  }
  const db = getDb();
  const id = crypto.randomUUID();
  db.prepare(
    "INSERT INTO notification_configs (id, service_url, notification_level) VALUES (?, ?, ?)"
  ).run(id, service_url, notification_level || 1);
  const config = db.prepare("SELECT * FROM notification_configs WHERE id = ?").get(id);
  return NextResponse.json(config, { status: 201 });
}
