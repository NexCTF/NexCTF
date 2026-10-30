import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { getPublicInfo } from "@/lib/api";
import { syncServerClock } from "@/lib/server-clock";
import { useEventPhase, useRefetchChallengesOnStart } from "@/lib/use-event-phase";
import { publicInfoWith } from "@/test/fixtures";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
);

function shiftServerClock(ms: number): void {
  const now = Date.now();
  syncServerClock(new Date(now + ms).toISOString(), now, now);
}

beforeEach(() => {
  const inThirtySeconds = new Date(Date.now() + 30_000).toISOString();
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ start_time: inThirtySeconds }));
});

afterEach(() => {
  shiftServerClock(0);
});

it("opens on the server's start even when the browser clock lags", async () => {
  shiftServerClock(60_000);
  const { result } = renderHook(() => useEventPhase(), { wrapper });

  await waitFor(() => expect(result.current.start).not.toBeNull());
  expect(result.current.open).toBe(true);
});

it("stays closed until the start on an accurate clock", async () => {
  const { result } = renderHook(() => useEventPhase(), { wrapper });

  await waitFor(() => expect(result.current.start).not.toBeNull());
  expect(result.current.upcoming).toBe(true);
  expect(result.current.open).toBe(false);
});

it("re-reads the clock once the first info response syncs it", async () => {
  const thirtySecondsAgo = new Date(Date.now() - 30_000).toISOString();
  vi.mocked(getPublicInfo).mockImplementation(async () => {
    shiftServerClock(-60_000);
    return publicInfoWith({ start_time: thirtySecondsAgo });
  });
  const { result } = renderHook(() => useEventPhase(), { wrapper });

  await waitFor(() => expect(result.current.start).not.toBeNull());
  await waitFor(() => expect(result.current.upcoming).toBe(true));
  expect(result.current.open).toBe(false);
});

it("refetches the challenges when the start passes", async () => {
  const soon = new Date(Date.now() + 300).toISOString();
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ start_time: soon }));
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  renderHook(() => useRefetchChallengesOnStart(), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });

  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["challenges"] }), {
    timeout: 2_000,
  });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["challenge"] });
});

it("does not refetch on mount once the event is running", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(
    publicInfoWith({ start_time: new Date(Date.now() - 60_000).toISOString() }),
  );
  const client = new QueryClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const { result } = renderHook(
    () => {
      useRefetchChallengesOnStart();
      return useEventPhase();
    },
    {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    },
  );

  await waitFor(() => expect(result.current.running).toBe(true));
  expect(invalidate).not.toHaveBeenCalled();
});
