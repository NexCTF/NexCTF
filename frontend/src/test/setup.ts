import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import "@/i18n";

// jsdom has no scrollTo; the router calls it on every navigation.
window.scrollTo = () => {};

// jsdom has no matchMedia; ThemeProvider resolves the "system" theme with it.
window.matchMedia = (query: string) =>
  ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }) as unknown as MediaQueryList;

// jsdom has no EventSource; the SSE singleton opens one as soon as a signed-in
// layout mounts. Inert stub — tests drive state through the query client.
class InertEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  readyState = InertEventSource.OPEN;
  onerror: ((this: EventSource, ev: Event) => unknown) | null = null;
  addEventListener() {}
  removeEventListener() {}
  close() {
    this.readyState = InertEventSource.CLOSED;
  }
}
globalThis.EventSource = InertEventSource as unknown as typeof EventSource;

// jsdom does not load the altcha CDN script, so the custom element never
// upgrades. Stub stands in for it: tests call solveCaptcha() to emit the
// "verified" event the real widget fires once it has solved its challenge.
export function solveCaptcha(payload: string) {
  const el = document.querySelector("altcha-widget");
  el?.dispatchEvent(new CustomEvent("verified", { detail: { payload } }));
}

class StubAltchaWidget extends HTMLElement {
  verify() {
    return Promise.resolve(null);
  }
  reset() {}
}
customElements.define("altcha-widget", StubAltchaWidget);

// @testing-library/react only auto-cleans when vitest globals are on.
afterEach(cleanup);
