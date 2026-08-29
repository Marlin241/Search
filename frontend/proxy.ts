import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const TOKEN_COOKIE = "search_app_token";
const PROTECTED_PREFIXES = [
  "/dashboard",
  "/offres",
  "/candidatures",
  "/diagnostic",
  "/profil",
  "/onboarding",
];
const AUTH_PATHS = ["/login", "/mot-de-passe-oublie", "/reset-password"];

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
}

/**
 * Server-side auth gate. This only checks whether the token cookie exists —
 * it never validates the token itself (the backend is the only source of
 * truth for that, via fetchMe client-side). The point is purely to avoid
 * the client-only-guard flash-of-spinner v2 had: an anonymous visitor
 * hitting a protected route gets redirected before the page ever renders,
 * and a logged-in visitor hitting /login gets bounced straight to the app.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasToken = Boolean(request.cookies.get(TOKEN_COOKIE)?.value);

  if (isProtectedPath(pathname) && !hasToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (AUTH_PATHS.includes(pathname) && hasToken) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/offres/:path*",
    "/candidatures/:path*",
    "/diagnostic/:path*",
    "/profil/:path*",
    "/onboarding/:path*",
    "/login",
    "/mot-de-passe-oublie",
    "/reset-password",
  ],
};
