"use client";

// Single source of truth for talking to the backend. Replaces the
// `NEXT_PUBLIC_API_URL || 'http://localhost:8000'` + `localStorage token ||
// 'test-token'` idiom that was duplicated across ~13 call sites. There is NO
// test-token fallback: production requires a real JWT, and a missing/expired
// token surfaces as an explicit logged-out state rather than silently acting as
// the sandbox identity.

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "keralty_token";
export const UNAUTHORIZED_EVENT = "keralty:unauthorized";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  if (typeof window !== "undefined") localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  if (typeof window !== "undefined") localStorage.removeItem(TOKEN_KEY);
}

export function loginUrl(): string {
  return `${API_URL}/auth/login`;
}

export class UnauthorizedError extends Error {
  constructor() {
    super("unauthorized");
    this.name = "UnauthorizedError";
  }
}

function notifyUnauthorized() {
  clearToken();
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }
}

// Core fetch: attaches the bearer token and centralizes 401 handling. Returns
// the raw Response so streaming callers (SSE chat) can read the body. Throws
// UnauthorizedError on a missing token or a 401 — after signaling the app to
// drop to the login gate.
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  if (!token) {
    notifyUnauthorized();
    throw new UnauthorizedError();
  }
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (res.status === 401) {
    notifyUnauthorized();
    throw new UnauthorizedError();
  }
  return res;
}

// Convenience JSON helper: throws on !ok with the server's detail/error string.
export async function apiJson<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: string; error?: string });
    throw new Error(detail.detail || detail.error || `Request failed (${res.status})`);
  }
  return data as T;
}
