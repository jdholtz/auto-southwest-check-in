import { cookies } from "next/headers";
import crypto from "crypto";

const AUTH_COOKIE = "sw-checkin-auth";
const TOKEN_EXPIRY = 7 * 24 * 60 * 60 * 1000; // 7 days

function getSecret(): string {
  return process.env.AUTH_SECRET || "change-me-in-production";
}

function getPassword(): string {
  return process.env.AUTH_PASSWORD || "admin";
}

function getUsername(): string {
  return process.env.AUTH_USERNAME || "admin";
}

export function verifyCredentials(username: string, password: string): boolean {
  return username === getUsername() && password === getPassword();
}

export function createToken(): string {
  const expiry = Date.now() + TOKEN_EXPIRY;
  const payload = `${expiry}`;
  const hmac = crypto.createHmac("sha256", getSecret()).update(payload).digest("hex");
  return `${payload}.${hmac}`;
}

export function verifyToken(token: string): boolean {
  const [payload, hmac] = token.split(".");
  if (!payload || !hmac) return false;

  const expiry = parseInt(payload, 10);
  if (isNaN(expiry) || Date.now() > expiry) return false;

  const expected = crypto.createHmac("sha256", getSecret()).update(payload).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(hmac), Buffer.from(expected));
}

export function isAuthenticated(): boolean {
  const cookieStore = cookies();
  const token = cookieStore.get(AUTH_COOKIE)?.value;
  if (!token) return false;
  return verifyToken(token);
}
