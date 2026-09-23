import { screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { getAdminPlugins } from "@/lib/api";
import { plugin } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./plugins";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminPlugins: vi.fn(),
}));

const renderPlugins = () => renderRoute(Route, { path: "/admin/plugins" });

it("links a loaded plugin to its settings category", async () => {
  vi.mocked(getAdminPlugins).mockResolvedValue([plugin({ has_config: true })]);
  renderPlugins();

  const link = await screen.findByRole("link", { name: "Settings" });
  expect(link.getAttribute("href")).toBe("/admin/settings?category=nexctf_demo");
});

it("tells the operator how to enable a disabled plugin", async () => {
  vi.mocked(getAdminPlugins).mockResolvedValue([plugin({ is_active: false, is_disabled: true })]);
  renderPlugins();

  expect(await screen.findByText("Disabled")).toBeDefined();
  expect(screen.getByText(/NEXCTF_DISABLED_PLUGINS/)).toBeDefined();
});

it("warns when a declared bundle was not built", async () => {
  vi.mocked(getAdminPlugins).mockResolvedValue([plugin({ missing_bundles: ["bundle.js"] })]);
  renderPlugins();

  expect(await screen.findByText(/Frontend not built, its UI is missing: bundle.js/)).toBeDefined();
});
