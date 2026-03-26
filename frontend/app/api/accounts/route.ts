import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export function GET() {
  const db = getDb();
  const accounts = db
    .prepare(
      `SELECT a.*, COUNT(r.id) as reservation_count
       FROM accounts a
       LEFT JOIN reservations r ON r.account_id = a.id
       GROUP BY a.id
       ORDER BY a.created_at DESC`
    )
    .all();
  return NextResponse.json(accounts);
}

export async function POST(req: NextRequest) {
  const { username, password } = await req.json();
  if (!username || !password) {
    return NextResponse.json({ error: "Username and password required" }, { status: 400 });
  }
  const db = getDb();
  const id = crypto.randomUUID();
  db.prepare(
    "INSERT INTO accounts (id, username, password) VALUES (?, ?, ?)"
  ).run(id, username, password);
  const account = db.prepare("SELECT * FROM accounts WHERE id = ?").get(id);
  return NextResponse.json(account, { status: 201 });
}
