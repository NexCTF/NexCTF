import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { getMe, login, logout, type User } from "@/lib/api";
import { type AuthContext, AuthProvider, useAuth } from "@/lib/auth";
import { user } from "@/test/fixtures";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getMe: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(login).mockResolvedValue(undefined);
  vi.mocked(logout).mockResolvedValue(undefined);
});

/** Mount the provider; `current()` is what its consumers rendered last. */
async function mountAuth(initial: User | null) {
  if (initial) vi.mocked(getMe).mockResolvedValue(initial);
  else vi.mocked(getMe).mockRejectedValue(new Error("401"));
  let current!: AuthContext;
  function Probe() {
    current = useAuth();
    return null;
  }
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );
  await waitFor(() => expect(current.isLoading).toBe(false));
  return () => current;
}

it("logout resolves once consumers render signed out", async () => {
  const current = await mountAuth(user());
  expect(current().user).not.toBeNull();

  await current().logout();

  expect(current().user).toBeNull();
});

it("login resolves once consumers render signed in", async () => {
  const current = await mountAuth(null);
  vi.mocked(getMe).mockResolvedValue(user({ username: "alice" }));

  await current().login("alice", "secret");

  expect(current().user?.username).toBe("alice");
});
