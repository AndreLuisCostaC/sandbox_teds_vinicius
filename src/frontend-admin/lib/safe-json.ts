/**
 * Safely parse a fetch Response body as JSON.
 * Handles empty bodies (204, network errors, etc.) that cause JSON.parse to throw.
 */
export async function safeJsonFromResponse<T = unknown>(
  response: Response,
  fallback: T = {} as T
): Promise<T> {
  const text = await response.text();
  if (!text.trim()) {
    return fallback;
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    return { detail: "Invalid JSON response" } as T;
  }
}
