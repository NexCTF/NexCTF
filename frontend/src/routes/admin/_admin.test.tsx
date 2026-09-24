import { screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { getAdminStats } from "@/lib/api";
import { pluginManifest } from "@/lib/plugins";
import { pluginManifestEntry, user } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./_admin";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminStats: vi.fn(),
}));
vi.mock("@/lib/plugins", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/plugins")>()),
  bootstrapPlugins: vi.fn(),
  pluginManifest: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

const renderAdmin = (path = "/admin") =>
  renderRoute(Route, {
    path,
    routePath: path,
    auth: { user: user({ role: "admin" }), isLoading: false },
  });

beforeEach(() => {
  vi.mocked(getAdminStats).mockRejectedValue(new Error("not needed"));
  vi.mocked(pluginManifest).mockResolvedValue([]);
});

it("sends a signed-out visitor to the login page", async () => {
  const { router } = renderRoute(Route, {
    path: "/admin",
    routePath: "/admin",
    auth: { user: null, isLoading: false },
  });

  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
});

it("waits for the identity before deciding", () => {
  const { router } = renderRoute(Route, {
    path: "/admin",
    routePath: "/admin",
    auth: { user: null, isLoading: true },
  });

  expect(router.state.location.pathname).toBe("/admin");
});

it("renders the panel for a signed-in admin", async () => {
  renderAdmin();

  expect(await screen.findByText("Admin")).toBeTruthy();
});

it("groups the read-only views under Audit", async () => {
  renderAdmin();

  expect(await screen.findByText("Audit")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Events" })).toBeTruthy();
  expect(screen.getByRole("link", { name: /Security/ })).toBeTruthy();
});

it("lists plugin admin pages in their section, the rest under Plugins", async () => {
  vi.mocked(pluginManifest).mockResolvedValue([
    pluginManifestEntry({
      pages: [
        { path: "workers", label: "Workers", icon: "server", section: "plugins" },
        { path: "", label: "Overview", icon: null, section: "manage" },
      ],
    }),
  ]);
  renderAdmin();

  const workers = await screen.findByRole("link", { name: "Workers" });
  expect(workers.getAttribute("href")).toBe("/admin/plugins/nexctf_demo/workers");
  const section = workers.closest("div")?.parentElement as HTMLElement;
  expect(within(section).getByText("Plugins")).toBeDefined();
  const overview = screen.getByRole("link", { name: "Overview" });
  expect(overview.getAttribute("href")).toBe("/admin/plugins/nexctf_demo");
  expect(overview.parentElement?.textContent).toContain("Challenges");
});

it("shows no Plugins section when no plugin lists an admin page", async () => {
  renderAdmin();

  await screen.findByRole("link", { name: "Dashboard" });
  expect(screen.getAllByText("Plugins")).toHaveLength(1);
});

it("does not mark the plugin list active on a plugin's own page", async () => {
  vi.mocked(pluginManifest).mockResolvedValue([
    pluginManifestEntry({
      pages: [{ path: "", label: "Demo", icon: null, section: "plugins" }],
    }),
  ]);
  renderAdmin("/admin/plugins/nexctf_demo");

  const demo = await screen.findByRole("link", { name: "Demo" });
  expect(demo.getAttribute("data-status")).toBe("active");
  const list = screen.getByRole("link", { name: "Plugins" });
  expect(list.getAttribute("data-status")).not.toBe("active");
});
