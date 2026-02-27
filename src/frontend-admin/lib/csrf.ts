import { cookies } from "next/headers";

export async function assertCsrf(request: Request): Promise<void> {
  const cookieStore = await cookies();
  const csrfCookie = cookieStore.get("csrf_token")?.value;
  const csrfHeader = request.headers.get("x-csrf-token");
  if (!csrfCookie || !csrfHeader || csrfCookie !== csrfHeader) {
    throw new Error("CSRF validation failed");
  }
}
