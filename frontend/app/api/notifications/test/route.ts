import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function POST() {
  const db = getDb();
  const configs = db.prepare("SELECT * FROM notification_configs WHERE is_active = 1").all();

  if (!configs || configs.length === 0) {
    return NextResponse.json({ error: "No notification services configured" }, { status: 400 });
  }

  // Write a test log entry so the worker can pick it up
  db.prepare(
    "INSERT INTO worker_logs (level, message) VALUES ('info', 'Test notification triggered from Settings page')"
  ).run();

  // Return the URLs so the frontend knows what was tested
  const urls = (configs as { service_url: string }[]).map((c) => c.service_url);
  return NextResponse.json({
    ok: true,
    message: `Test notification queued for ${urls.length} service(s)`,
    count: urls.length,
  });
}
