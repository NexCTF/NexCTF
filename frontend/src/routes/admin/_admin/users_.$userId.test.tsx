import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import {
  getAdminUser,
  getAdminUserEvents,
  getAdminUserSessions,
  revokeAdminUserSession,
} from "@/lib/api";
import { paginated, user, userSession } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./users_.$userId";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminUser: vi.fn(),
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
