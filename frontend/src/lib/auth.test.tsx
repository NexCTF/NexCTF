import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { getMe, login, logout, type User } from "@/lib/api";
import { type AuthContext, AuthProvider, useAuth } from "@/lib/auth";
import { closeSSE } from "@/lib/sse";
import { user } from "@/test/fixtures";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getMe: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("@/lib/sse", () => ({ closeSSE: vi.fn() }));

beforeEach(() => {
  vi.mocked(login).mockResolvedValue(undefined);
  vi.mocked(logout).mockResolvedValue(undefined);
});

/** Mount the provider; `current()` is what its consumers rendered last. */
async function mountAuth(initial: User | null, client = new QueryClient()) {
  if (initial) vi.mocked(getMe).mockResolvedValue(initial);
  else vi.mocked(getMe).mockRejectedValue(new Error("401"));
  let current!: AuthContext;
  function Probe() {
    current = useAuth();
    return null;
  }
  render(
    <QueryClientProvider client={client}>
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

it.each(["logout", "login"] as const)(
  "%s drops the previous account's cached data but keeps public info",
  async (action) => {
    const client = new QueryClient();
    const current = await mountAuth(action === "logout" ? user() : null, client);
    client.setQueryData(["my-team"], { invite_code: "SECRET01" });
    client.setQueryData(["info", "public"], { name: "CTF" });
    vi.mocked(getMe).mockResolvedValue(user({ username: "bob" }));

    if (action === "logout") await current().logout();
    else await current().login("bob", "secret");

    expect(client.getQueryData(["my-team"])).toBeUndefined();
    expect(client.getQueryData(["info", "public"])).toEqual({ name: "CTF" });
  },
);

it("login drops a stream still open for the previous account", async () => {
  const current = await mountAuth(null);
  vi.mocked(getMe).mockResolvedValue(user({ username: "bob" }));

  await current().login("bob", "secret");

  expect(closeSSE).toHaveBeenCalled();
});
