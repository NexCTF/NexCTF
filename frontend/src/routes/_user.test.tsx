import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { getMyNotifications, getPublicInfo, getPublishedPages } from "@/lib/api";
import type { AuthContext } from "@/lib/auth";
import { publicInfo, user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./_user";

const renderLayout = (auth: Partial<AuthContext> = { user: user() }) =>
  renderRoute(Route, { path: "/", auth });

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  getPublishedPages: vi.fn(),
  getMyNotifications: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfo());
  vi.mocked(getPublishedPages).mockResolvedValue([]);
  vi.mocked(getMyNotifications).mockResolvedValue({ notifications: [], last_read_at: null });
});

it("shows the main navigation", async () => {
  renderLayout();

  expect(await screen.findByRole("link", { name: "Challenges" })).toBeDefined();
  expect(screen.getByRole("link", { name: "Scoreboard" })).toBeDefined();
  expect(screen.getByRole("link", { name: "Teams" })).toBeDefined();
});

it("signs a user out and sends them to the login page", async () => {
  const logout = vi.fn().mockResolvedValue(undefined);
  const { router } = renderLayout({ user: user(), logout });

  await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));

  expect(logout).toHaveBeenCalled();
  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
});

it("offers sign-in to an anonymous visitor and hides the account controls", async () => {
  renderLayout({ user: null });

  expect(await screen.findByRole("link", { name: "Sign in" })).toBeDefined();
  expect(screen.queryByRole("button", { name: "Sign out" })).toBeNull();
});

it("hides the admin shortcut from regular users", async () => {
  renderLayout();

  expect(await screen.findByRole("link", { name: "Challenges" })).toBeDefined();
  expect(screen.queryByRole("link", { name: "Admin" })).toBeNull();
});

it("shows the admin shortcut to admins", async () => {
  renderLayout({ user: user({ role: "admin" }) });

  expect(await screen.findByRole("link", { name: "Admin" })).toBeDefined();
});

it("splits published pages between the nav bar and the footer", async () => {
  vi.mocked(getPublishedPages).mockResolvedValue([
    { slug: "rules", title: "Rules", nav_placement: "nav" },
    { slug: "legal", title: "Legal", nav_placement: "footer" },
    { slug: "hidden", title: "Hidden", nav_placement: null },
  ]);
  renderLayout();

  await screen.findByRole("link", { name: "Rules" });
  expect(within(screen.getByRole("banner")).getByRole("link", { name: "Rules" })).toBeDefined();
  expect(
    within(screen.getByRole("contentinfo")).getByRole("link", { name: "Legal" }),
  ).toBeDefined();
  expect(screen.queryByRole("link", { name: "Hidden" })).toBeNull();
});

it("renders external links from the public info", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(
    publicInfo({ links: [{ name: "Discord", url: "https://discord.gg/x" }] }),
  );
  renderLayout();

  const link = await screen.findByRole("link", { name: /Discord/ });
  expect(link.getAttribute("href")).toBe("https://discord.gg/x");
  expect(link.getAttribute("rel")).toContain("noopener");
});
