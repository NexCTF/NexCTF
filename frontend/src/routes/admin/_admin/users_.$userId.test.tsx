import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import {
  getAdminUser,
  getAdminUserClients,
  getAdminUserEvents,
  getAdminUserSessions,
  revokeAdminUserSession,
} from "@/lib/api";
import { paginated, user, userClient, userSession } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./users_.$userId";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminUser: vi.fn(),
  getAdminUserClients: vi.fn(),
  getAdminUserEvents: vi.fn(),
  getAdminUserSessions: vi.fn(),
  revokeAdminUserSession: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

beforeEach(() => {
  vi.mocked(getAdminUser).mockResolvedValue({
    ...user({ id: "u1" }),
    ips: [],
    last_login_at: null,
    custom_field_values: [],
  });
  vi.mocked(getAdminUserEvents).mockResolvedValue(paginated([]));
  vi.mocked(getAdminUserSessions).mockResolvedValue([userSession()]);
  vi.mocked(getAdminUserClients).mockResolvedValue([]);
  vi.mocked(revokeAdminUserSession).mockResolvedValue(undefined);
});

function render() {
  return renderRoute(Route, { path: "/admin/users/u1", routePath: "/admin/users/$userId" });
}

it("describes a session's device and addresses", async () => {
  render();

  const row = (await screen.findByText(/Chrome on Windows/)).closest("div");
  expect(row).not.toBeNull();
  expect(within(row as HTMLElement).getByText("203.0.113.7")).toBeTruthy();
});

it("revokes a session", async () => {
  render();

  await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));
  const dialog = await screen.findByRole("dialog");
  await userEvent.click(within(dialog).getByRole("button", { name: "Sign out" }));

  expect(revokeAdminUserSession).toHaveBeenCalledWith("u1", userSession().id);
});

it("does not offer to revoke the admin's own session", async () => {
  vi.mocked(getAdminUserSessions).mockResolvedValue([userSession({ current: true })]);
  render();

  await screen.findByText("Your session");
  expect(screen.queryByRole("button", { name: "Sign out" })).toBeNull();
});

it("lists the clients the user was seen with", async () => {
  vi.mocked(getAdminUserClients).mockResolvedValue([
    userClient({
      id: "c1",
      user_agent: "curl/8.10.1",
      category: "automation",
      source: "token",
      token_name: "solver",
    }),
    userClient({ id: "c2", user_agent: "" }),
  ]);
  render();

  expect(await screen.findByText("curl/8.10.1")).toBeTruthy();
  expect(screen.getByText("Automation")).toBeTruthy();
  expect(screen.getByText("API token: solver")).toBeTruthy();
  expect(screen.getByText("No user-agent sent")).toBeTruthy();
  expect(getAdminUserClients).toHaveBeenCalledWith("u1");
});

it("says so when no client was recorded", async () => {
  render();

  expect(await screen.findByText("No client recorded yet.")).toBeTruthy();
});
