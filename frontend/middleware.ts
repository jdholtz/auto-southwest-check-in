import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

function getSecret(): string {
  return process.env.AUTH_SECRET || "change-me-in-production";
}

function verifyToken(token: string): boolean {
  const [payload, hmac] = token.split(".");
  if (!payload || !hmac) return false;

  const expiry = parseInt(payload, 10);
  if (isNaN(expiry) || Date.now() > expiry) return false;

  const expected = crypto.createHmac("sha256", getSecret()).update(payload).digest("hex");
  try {
    return crypto.timingSafeEqual(Buffer.from(hmac), Buffer.from(expected));
  } catch {
    return false;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow login page and auth API without authentication
  if (pathname === "/login" || pathname === "/api/auth") {
    return NextResponse.next();
  }

  // Allow static assets
  if (pathname.startsWith("/_next") || pathname === "/favicon.ico") {
    return NextResponse.next();
  }

  const token = request.cookies.get("sw-checkin-auth")?.value;

  if (!token || !verifyToken(token)) {
    // API routes return 401
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    // Pages redirect to login
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
