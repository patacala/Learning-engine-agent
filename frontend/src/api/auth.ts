import { apiFetch } from './http';

const BASE = '/api/v1/auth';

export async function login(password: string): Promise<boolean> {
  const res = await apiFetch(`${BASE}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });
  return res.ok;
}

export async function logout(): Promise<void> {
  await apiFetch(`${BASE}/logout`, { method: 'POST' });
}

export async function checkSession(): Promise<boolean> {
  const res = await apiFetch(`${BASE}/session`);
  return res.ok;
}
