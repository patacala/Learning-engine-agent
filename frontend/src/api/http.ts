// Shared fetch wrapper. Auth is a session cookie set by POST /auth/login (see
// api/auth.ts) — the browser attaches it automatically on every same-origin
// request (nginx proxies /api to the backend on the same origin in every
// deployment), so there's no token to manage here anymore.

export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  return fetch(input, { ...init, credentials: 'same-origin' });
}
