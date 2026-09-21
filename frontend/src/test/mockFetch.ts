import { vi } from 'vitest';

export interface MockRoute {
  status?: number;
  body?: unknown;
}

type Handler = (url: string, init: { method: string; body?: unknown }) => MockRoute;

/**
 * Stubs the global `fetch` with a route handler.
 *
 * Returned as a spy so tests can assert on what the component actually asked
 * the API for — the request shape is part of the contract these forms have to
 * honour.
 */
export function stubFetch(handler: Handler) {
  const spy = vi.fn((input: unknown, init?: RequestInit) => {
    const request = input as { url?: string; method?: string; body?: unknown };
    const url = typeof input === 'string' ? input : (request.url ?? String(input));
    const method = (request.method ?? init?.method ?? 'GET').toUpperCase();
    const { status = 200, body = {} } = handler(url, { method, body: request.body });

    return Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      })
    );
  });

  vi.stubGlobal('fetch', spy);
  return spy;
}

/** URLs requested so far, for assertions that a lookup used the right code. */
export function requestedUrls(spy: ReturnType<typeof stubFetch>): string[] {
  return spy.mock.calls.map(([input]) => {
    const request = input as { url?: string };
    return typeof input === 'string' ? input : (request.url ?? String(input));
  });
}
