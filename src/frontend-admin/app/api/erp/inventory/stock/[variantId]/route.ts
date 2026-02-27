import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { assertCsrf } from "@/lib/csrf";

import { BACKEND_API_URL } from "@/lib/backend-url";

type RouteContext = {
  params: Promise<{ variantId: string }>;
};

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

export async function PATCH(request: Request, context: RouteContext) {
  try {
    await assertCsrf(request);
  } catch {
    return NextResponse.json({ detail: "CSRF validation failed." }, { status: 403 });
  }
  const headers = await authHeaders();
  if (!headers) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const { variantId } = await context.params;
  const body = await request.json();
  const response = await fetch(
    `${BACKEND_API_URL}/api/v1/inventory/stock/${variantId}`,
    {
      method: "PATCH",
      headers,
      body: JSON.stringify(body),
    }
  );
  const payload = await response.json();
  return NextResponse.json(payload, { status: response.status });
}
