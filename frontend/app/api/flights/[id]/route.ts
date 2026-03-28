import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const body = await req.json();
  const db = getDb();

  const fields: string[] = [];
  const values: unknown[] = [];

  if (body.original_price !== undefined) {
    fields.push("original_price = ?");
    values.push(body.original_price === null || body.original_price === "" ? null : Number(body.original_price));
  }
  if (body.original_currency !== undefined) {
    fields.push("original_currency = ?");
    values.push(body.original_currency || "USD");
  }

  if (fields.length === 0) {
    return NextResponse.json({ error: "No fields to update" }, { status: 400 });
  }

  values.push(params.id);
  db.prepare(`UPDATE flights SET ${fields.join(", ")} WHERE id = ?`).run(...values);
  const flight = db.prepare("SELECT * FROM flights WHERE id = ?").get(params.id);
  return NextResponse.json(flight);
}
