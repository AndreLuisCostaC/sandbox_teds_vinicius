import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { BACKEND_API_URL } from "@/lib/backend-url";
import { safeJsonFromResponse } from "@/lib/safe-json";

async function authHeaders() {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  if (!token) {
    return null;
  }
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export async function GET(request: Request) {
  const headers = await authHeaders();
  if (!headers) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const query = new URLSearchParams();
  query.set("limit", searchParams.get("limit") ?? "20");
  query.set("offset", searchParams.get("offset") ?? "0");
  const status = searchParams.get("status");
  if (status && status !== "all") {
    query.set("status", status);
  }

  const response = await fetch(`${BACKEND_API_URL}/api/v1/orders?${query.toString()}`, {
    method: "GET",
    headers,
    cache: "no-store",
  });
  const payload = await safeJsonFromResponse(response, { items: [], total: 0, limit: 0, offset: 0 });
  return NextResponse.json(payload, { status: response.status });
}
