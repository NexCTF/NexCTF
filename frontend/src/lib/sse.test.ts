import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { InertEventSource } from "@/test/setup";

class FakeEventSource extends InertEventSource {
  static instances: FakeEventSource[] = [];
  onopen: (() => void) | null = null;
  private listeners = new Map<string, Set<(e: MessageEvent<string>) => void>>();

  constructor() {
    super();
    FakeEventSource.instances.push(this);
  }
  override addEventListener(type: string, fn: (e: MessageEvent<string>) => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)?.add(fn);
  }
  emit(type: string, data: unknown) {
    for (const fn of this.listeners.get(type) ?? []) {
      fn(new MessageEvent(type, { data: JSON.stringify(data) }));
    }
  }
  fail(readyState: number) {
    this.readyState = readyState;
    this.onerror?.call(this as unknown as EventSource, new Event("error"));
  }
}

const latest = () => FakeEventSource.instances[FakeEventSource.instances.length - 1];

beforeEach(() => {
  vi.resetModules();
  vi.useFakeTimers();
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 200 }));
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it("reconnects after a refused connection and keeps its listeners", async () => {
  const { addSSEListener } = await import("@/lib/sse");
  const handler = vi.fn();
  addSSEListener("notification", handler);

  latest().fail(InertEventSource.CLOSED);
  await vi.advanceTimersByTimeAsync(30_000);

  expect(FakeEventSource.instances).toHaveLength(2);
  latest().emit("notification", { id: "n1" });
  expect(handler).toHaveBeenCalledWith({ id: "n1" });
});

it("leaves the browser's own retry alone while it is reconnecting", async () => {
  const { addSSEListener } = await import("@/lib/sse");
  addSSEListener("notification", vi.fn());

  latest().fail(InertEventSource.CONNECTING);
  await vi.advanceTimersByTimeAsync(30_000);

  expect(FakeEventSource.instances).toHaveLength(1);
});

it("does not reconnect once the session is gone", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status: 401 }));
  vi.stubGlobal("location", { ...window.location, href: "" });
  const { addSSEListener } = await import("@/lib/sse");
  addSSEListener("notification", vi.fn());

  latest().fail(InertEventSource.CLOSED);
  await vi.advanceTimersByTimeAsync(30_000);

  expect(window.location.href).toBe("/login");
  expect(FakeEventSource.instances).toHaveLength(1);
});
