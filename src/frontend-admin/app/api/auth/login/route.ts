import { NextResponse } from "next/server";
import { assertCsrf } from "@/lib/csrf";
import { BACKEND_API_URL } from "@/lib/backend-url";
import { safeJsonFromResponse } from "@/lib/safe-json";

type LoginBody = {
  email?: string;
  password?: string;
};

export async function POST(request: Request) {
  try {
    await assertCsrf(request);
  } catch {
    return NextResponse.json({ detail: "CSRF validation failed." }, { status: 403 });
  }
  const body = (await request.json()) as LoginBody;
  const email = body.email?.trim().toLowerCase();
  const password = body.password;

  if (!email || !password) {
    return NextResponse.json({ detail: "Email and password are required." }, { status: 400 });
  }

  const loginResponse = await fetch(`${BACKEND_API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!loginResponse.ok) {
    const payload = await safeJsonFromResponse<{ detail?: string }>(loginResponse, {
      detail: "Invalid credentials",
    });
    return NextResponse.json(
      { detail: payload.detail ?? "Invalid credentials" },
      { status: loginResponse.status }
    );
  }

  const tokenPayload = await safeJsonFromResponse<{ access_token: string }>(loginResponse, {
    access_token: "",
  });
  const token = tokenPayload.access_token;
  if (!token) {
    return NextResponse.json({ detail: "Invalid credentials" }, { status: 401 });
  }

  const meResponse = await fetch(`${BACKEND_API_URL}/api/v1/me`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!meResponse.ok) {
    return NextResponse.json({ detail: "Could not validate authenticated user." }, { status: 401 });
  }

  const adminPing = await fetch(`${BACKEND_API_URL}/api/v1/admin/ping`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });

  const role = adminPing.ok ? "admin" : "employee";
  const redirectTo = role === "admin" ? "/dashboard" : "/employee";

  const response = NextResponse.json({ redirectTo }, { status: 200 });
  const secure = process.env.NODE_ENV === "production";

  response.cookies.set("access_token", token, {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60,
  });
  response.cookies.set("user_role", role, {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60,
  });

  return response;
}
