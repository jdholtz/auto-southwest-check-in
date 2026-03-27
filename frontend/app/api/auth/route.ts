import { NextRequest, NextResponse } from "next/server";
import { verifyCredentials, createToken, isAuthenticated } from "@/lib/auth";

export async function POST(req: NextRequest) {
  const { username, password } = await req.json();

  if (!verifyCredentials(username, password)) {
    return NextResponse.json({ error: "Invalid credentials" }, { status: 401 });
  }

  const token = createToken();
  const response = NextResponse.json({ ok: true });
  response.cookies.set("sw-checkin-auth", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 7 * 24 * 60 * 60, // 7 days
  });
  return response;
}

export async function GET() {
  return NextResponse.json({ authenticated: isAuthenticated() });
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.delete("sw-checkin-auth");
  return response;
}
