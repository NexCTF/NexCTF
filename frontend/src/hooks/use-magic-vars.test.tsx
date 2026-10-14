import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useMagicVars } from "@/hooks/use-magic-vars";
import { getPublicInfo } from "@/lib/api";
import { publicInfo, publicInfoWith } from "@/test/fixtures";

const FUTURE = "2099-01-01T00:00:00Z";
const PAST = "2000-01-01T00:00:00Z";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
);

beforeEach(() => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfo());
  vi.spyOn(globalThis, "setInterval");
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("does not tick for content without a countdown", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ start_time: FUTURE }));
  const { result } = renderHook(() => useMagicVars("Welcome to {{event_name}}"), { wrapper });

  await waitFor(() => expect(result.current.event_name).not.toBe(""));
  expect(setInterval).not.toHaveBeenCalledWith(expect.any(Function), 1000);
});

it("ticks while a countdown runs", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ start_time: FUTURE }));
  renderHook(() => useMagicVars("Starts in {{countdown_to_start}}"), { wrapper });

  await waitFor(() => expect(setInterval).toHaveBeenCalledWith(expect.any(Function), 1000));
});

it("stops ticking once every countdown is over", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith({ start_time: PAST, end_time: PAST }));
  const { result } = renderHook(() => useMagicVars("Ends in {{countdown_to_end}}"), { wrapper });

  await waitFor(() => expect(result.current.countdown_to_end).toBe("Ended"));
  expect(setInterval).not.toHaveBeenCalledWith(expect.any(Function), 1000);
});
