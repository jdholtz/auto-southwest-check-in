import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const body = await req.json();
  const db = getDb();
  const fields: string[] = [];
  const values: unknown[] = [];

  if (body.is_active !== undefined) {
    fields.push("is_active = ?");
    values.push(body.is_active ? 1 : 0);
  }
  if (body.retrieval_interval !== undefined) {
    fields.push("retrieval_interval = ?");
    values.push(body.retrieval_interval);
  }

  if (fields.length === 0) {
    return NextResponse.json({ error: "No fields to update" }, { status: 400 });
  }

  fields.push("updated_at = datetime('now')");
  values.push(params.id);
  db.prepare(`UPDATE accounts SET ${fields.join(", ")} WHERE id = ?`).run(...values);
  const account = db.prepare("SELECT * FROM accounts WHERE id = ?").get(params.id);
  return NextResponse.json(account);
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  const db = getDb();
  db.prepare("DELETE FROM accounts WHERE id = ?").run(params.id);
  return NextResponse.json({ ok: true });
}
