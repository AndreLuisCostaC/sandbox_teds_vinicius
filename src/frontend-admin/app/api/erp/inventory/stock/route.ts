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
  const variantIds = searchParams.get("variant_ids");
  if (!variantIds) {
    return NextResponse.json({ items: [] }, { status: 200 });
  }

  const response = await fetch(
    `${BACKEND_API_URL}/api/v1/inventory/stock?variant_ids=${encodeURIComponent(variantIds)}`,
    {
      method: "GET",
      headers,
      cache: "no-store",
    }
  );
  const payload = await safeJsonFromResponse<{ items?: unknown[]; detail?: string }>(
    response,
    response.ok ? { items: [] } : { detail: "Request failed" }
  );
  return NextResponse.json(payload, { status: response.status });
}
