/**
 * Backend API base URL for server-side requests.
 * Use BACKEND_URL in Docker (http://backend:8000); NEXT_PUBLIC_API_URL for local dev.
 */
export const BACKEND_API_URL =
  process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
