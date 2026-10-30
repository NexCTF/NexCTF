import { afterEach, expect, it, vi } from "vitest";
import { serverNow, syncServerClock } from "@/lib/server-clock";

afterEach(() => {
  vi.useRealTimers();
  syncServerClock(new Date(Date.now()).toISOString(), Date.now(), Date.now());
});

it("follows a server clock that runs ahead of the browser", () => {
  vi.useFakeTimers({ now: Date.parse("2026-06-01T12:00:00Z") });

  syncServerClock("2026-06-01T12:01:00Z", Date.now() - 200, Date.now());

  expect(serverNow()).toBe(Date.parse("2026-06-01T12:01:00.100Z"));
});

it("keeps the last offset when the server time is unreadable", () => {
  vi.useFakeTimers({ now: Date.parse("2026-06-01T12:00:00Z") });
  syncServerClock("2026-06-01T11:59:00Z", Date.now(), Date.now());

  syncServerClock("not a date", Date.now(), Date.now());

  expect(serverNow()).toBe(Date.parse("2026-06-01T11:59:00Z"));
});
