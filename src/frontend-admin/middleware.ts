import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

function decodeJwtPayload(token: string): { exp?: number } | null {
  const parts = token.split(".");
  if (parts.length !== 3) {
    return null;
  }
  try {
    const payload = parts[1];
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const decoded = atob(padded);
    return JSON.parse(decoded) as { exp?: number };
  } catch {
    return null;
  }
}

function hasValidToken(token: string | undefined): boolean {
  if (!token) {
    return false;
  }
  const payload = decodeJwtPayload(token);
  if (!payload || !payload.exp) {
    return false;
  }
  return payload.exp * 1000 > Date.now();
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("access_token")?.value;
  const role = request.cookies.get("user_role")?.value;
  const authenticated = hasValidToken(token);

  const loginUrl = new URL("/login", request.url);

  if (pathname === "/login") {
    if (!authenticated) {
      return NextResponse.next();
    }
    const redirectTo = role === "admin" ? "/dashboard" : "/employee";
    return NextResponse.redirect(new URL(redirectTo, request.url));
  }

  if (pathname === "/") {
    if (!authenticated) {
      return NextResponse.redirect(loginUrl);
    }
    const redirectTo = role === "admin" ? "/dashboard" : "/employee";
    return NextResponse.redirect(new URL(redirectTo, request.url));
  }

  if (pathname.startsWith("/dashboard")) {
    if (!authenticated) {
      return NextResponse.redirect(loginUrl);
    }
    if (role !== "admin") {
      return NextResponse.redirect(new URL("/employee", request.url));
    }
  }

  if (pathname.startsWith("/employee")) {
    if (!authenticated) {
      return NextResponse.redirect(loginUrl);
    }
    if (role === "admin") {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/login", "/dashboard/:path*", "/employee/:path*"],
};
