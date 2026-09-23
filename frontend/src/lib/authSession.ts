import { OpenAPI } from "@/lib/api";

export const AUTH_COOKIE_NAME = "auth_token";
const SESSION_MAX_AGE_SECONDS = 60 * 60 * 24; // 24 hours

function setAuthCookie(token: string) {
  if (typeof document === "undefined") return;
  document.cookie = `${AUTH_COOKIE_NAME}=${encodeURIComponent(token)}; path=/; max-age=${SESSION_MAX_AGE_SECONDS}; SameSite=Lax`;
}

function clearAuthCookie() {
  if (typeof document === "undefined") return;
  document.cookie = `${AUTH_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax`;
}

export function setSession(token: string) {
  localStorage.setItem(AUTH_COOKIE_NAME, token);
  OpenAPI.TOKEN = token;
  setAuthCookie(token);
}

export function clearSession() {
  localStorage.removeItem(AUTH_COOKIE_NAME);
  OpenAPI.TOKEN = undefined;
  clearAuthCookie();
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(AUTH_COOKIE_NAME);
}
