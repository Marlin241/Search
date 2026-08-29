import { NextRequest, NextResponse } from "next/server";

const COOKIE = "search_app_token";
const MAX_AGE = 60 * 60 * 24; // 24h, matches backend JWT default expiry

export async function POST(req: NextRequest) {
  const { token } = await req.json();
  if (typeof token !== "string" || !token) {
    return NextResponse.json({ error: "missing token" }, { status: 400 });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: MAX_AGE,
  });
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE, "", { path: "/", maxAge: 0 });
  return res;
}
