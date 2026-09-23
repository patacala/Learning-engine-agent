// Shared fetch wrapper: attaches the internal API token to every request.
// In development the backend allows requests without a token; in production
// the token is baked in at build time via VITE_INTERNAL_TOKEN.

const INTERNAL_TOKEN: string = import.meta.env.VITE_INTERNAL_TOKEN ?? '';

export function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...(extra ?? {}) };
  if (INTERNAL_TOKEN) headers['X-Internal-Token'] = INTERNAL_TOKEN;
  return headers;
}

export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (INTERNAL_TOKEN && !headers.has('X-Internal-Token')) {
    headers.set('X-Internal-Token', INTERNAL_TOKEN);
  }
  return fetch(input, { ...init, headers });
}
