import { fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { ApiError } from './types';

const CSRF_COOKIE = 'caricue_csrftoken';
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export function readCookie(name: string): string | undefined {
  return document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${name}=`))
    ?.split('=')[1];
}

/**
 * Session-cookie auth with CSRF.
 *
 * `credentials: 'include'` sends the Django session cookie, and every unsafe
 * request carries the CSRF token that Django set on `/api/auth/csrf/`. Both
 * only work because dev (Vite proxy) and production (Nginx) put the SPA and
 * the API on the same origin.
 */
export const baseQuery = fetchBaseQuery({
  baseUrl: '/api/',
  credentials: 'include',
  prepareHeaders: (headers, { type }) => {
    // `type` is 'mutation' for anything that changes state.
    if (type === 'mutation') {
      const token = readCookie(CSRF_COOKIE);
      if (token) headers.set('X-CSRFToken', token);
    }
    return headers;
  },
  fetchFn: async (input, init) => {
    const method = (init?.method ?? 'GET').toUpperCase();
    if (UNSAFE_METHODS.has(method) && !readCookie(CSRF_COOKIE)) {
      // First unsafe request of a cold session: fetch the token, then proceed.
      await fetch('/api/auth/csrf/', { credentials: 'include' });
    }
    return fetch(input, init);
  },
});

/** Narrows an RTK Query error to our API error envelope. */
export function isApiError(error: unknown): error is { status: number; data: ApiError } {
  if (typeof error !== 'object' || error === null) return false;
  const candidate = error as { status?: unknown; data?: unknown };
  if (typeof candidate.status !== 'number') return false;
  return (
    typeof candidate.data === 'object' &&
    candidate.data !== null &&
    'detail' in (candidate.data as object)
  );
}

/** A message safe to show a user, for any error RTK Query can produce. */
export function errorMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (isApiError(error)) return error.data.detail || fallback;
  if (typeof error === 'object' && error !== null && 'error' in error) {
    return 'Could not reach the server. Check your connection.';
  }
  return fallback;
}

/** Field-level errors, for rendering next to the offending input. */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!isApiError(error)) return {};
  const result: Record<string, string> = {};
  for (const [field, value] of Object.entries(error.data.errors ?? {})) {
    if (Array.isArray(value) && value.length > 0) {
      result[field] = String(value[0]);
    } else if (typeof value === 'string') {
      result[field] = value;
    }
  }
  return result;
}
