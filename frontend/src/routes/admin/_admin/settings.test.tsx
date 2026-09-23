import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { type ConfigItem, getConfig } from "@/lib/api";
import { renderRoute } from "@/test/render";
import { Route } from "./settings";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getConfig: vi.fn(),
}));

function item(key: string, category: string, label: string): ConfigItem {
  return {
    key,
    type: "string",
    value: "",
    default: "",
    label,
    description: "",
    choices: [],
    category,
    category_label: category,
    category_icon: null,
    category_section: "settings",
    is_plugin_category: false,
  };
}

beforeEach(() => {
  vi.mocked(getConfig).mockResolvedValue([
    item("a.one", "general", "First field"),
    item("b.two", "nexctf_demo", "Plugin field"),
  ]);
});

it("opens the category named in the URL", async () => {
  renderRoute(Route, { path: "/admin/settings?category=nexctf_demo" });

  expect(await screen.findByText("Plugin field")).toBeDefined();
  expect(screen.queryByText("First field")).toBeNull();
});

it("falls back to the first category when the URL names an unknown one", async () => {
  renderRoute(Route, { path: "/admin/settings?category=gone" });

  expect(await screen.findByText("First field")).toBeDefined();
});

it("records the selected tab in the URL", async () => {
  const { router } = renderRoute(Route, { path: "/admin/settings" });

  await userEvent.click(await screen.findByRole("button", { name: "nexctf_demo" }));

  await waitFor(() => expect(router.state.location.search).toEqual({ category: "nexctf_demo" }));
  expect(await screen.findByText("Plugin field")).toBeDefined();
});
