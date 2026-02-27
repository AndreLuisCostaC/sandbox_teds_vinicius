/**
 * Safely parse a Response body as JSON. Use for one-off fetch calls.
 */
export async function parseResponseJson<T = unknown>(response: Response): Promise<T & { detail?: string }> {
  const text = await response.text();
  if (!text.trim()) {
    return { detail: response.statusText || "Empty response" } as T & { detail?: string };
  }
  try {
    return JSON.parse(text) as T & { detail?: string };
  } catch {
    return { detail: "Invalid JSON response" } as T & { detail?: string };
  }
}

/**
 * Safe fetcher for SWR that handles empty response bodies.
 * Avoids JSON.parse errors when the server returns 204 or empty body.
 */
export async function safeFetcher<T>(url: string): Promise<T> {
  const response = await fetch(url);
  const payload = await parseResponseJson<T>(response);
  if (!response.ok) {
    throw new Error(payload.detail ?? `Request failed for ${url}`);
  }
  return payload;
}
