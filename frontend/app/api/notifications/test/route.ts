import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function POST() {
  const db = getDb();
  const configs = db.prepare("SELECT * FROM notification_configs WHERE is_active = 1").all();

  if (!configs || configs.length === 0) {
    return NextResponse.json({ error: "No notification services configured" }, { status: 400 });
  }

  // Write a command to the worker_logs that the worker will pick up to send test notification
  db.prepare(
    "INSERT INTO worker_logs (level, message) VALUES ('info', '__TEST_NOTIFICATION__')"
  ).run();

  const count = (configs as unknown[]).length;
  return NextResponse.json({
    ok: true,
    message: `Test notification queued for ${count} service(s). Check your device shortly.`,
    count,
  });
}
