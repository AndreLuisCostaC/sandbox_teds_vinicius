import crypto from "crypto";
import { NextResponse } from "next/server";

export async function GET() {
  const token = crypto.randomBytes(24).toString("hex");
  const response = NextResponse.json({ csrfToken: token }, { status: 200 });
  response.cookies.set("csrf_token", token, {
    httpOnly: false,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60,
  });
  return response;
}
