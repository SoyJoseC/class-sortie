import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});

// Chakra reads `matchMedia` for responsive props and colour mode; jsdom does
// not implement it.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }),
});

// Chakra's `Progress`/`Tooltip` animations use these in jsdom.
Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  value: class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
});

/**
 * Under jsdom, `AbortSignal` comes from jsdom while `Request` comes from
 * Node's fetch implementation, which brand-checks the signal it is handed.
 * RTK Query builds a `Request` from the thunk's abort signal, so the two
 * implementations collide before our stubbed `fetch` is ever called. A
 * permissive `Request` keeps that plumbing out of the way — tests assert on
 * the stubbed `fetch` and the rendered output, not on `Request` semantics.
 */
class TestRequest {
  readonly url: string;
  readonly method: string;
  readonly headers: Headers;
  readonly body: unknown;
  readonly signal: unknown;

  constructor(url: string, init: Record<string, unknown> = {}) {
    this.url = String(url);
    this.method = String(init.method ?? 'GET').toUpperCase();
    this.headers = new Headers((init.headers as HeadersInit) ?? {});
    this.body = init.body;
    this.signal = init.signal;
  }

  clone() {
    return this;
  }

  toString() {
    return this.url;
  }
}

Object.defineProperty(globalThis, 'Request', { writable: true, value: TestRequest });
