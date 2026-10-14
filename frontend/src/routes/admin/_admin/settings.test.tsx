import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError, type ConfigItem, getConfig, updateConfig } from "@/lib/api";
import { renderRoute } from "@/test/render";
import { Route } from "./settings";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getConfig: vi.fn(),
  updateConfig: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

function item(key: string, category: string, label: string): ConfigItem {
  return {
    key,
    type: "string",
    value: "",
    default: "",
    label,
    description: "",
    choices: [],
    min: null,
    max: null,
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

it("bounds a number input by the setting's min and max", async () => {
  vi.mocked(getConfig).mockResolvedValue([
    { ...item("a.port", "general", "Port"), type: "int", value: 587, min: 1, max: 65535 },
  ]);
  renderRoute(Route, { path: "/admin/settings" });

  const input = await screen.findByRole("spinbutton");
  expect(input.getAttribute("min")).toBe("1");
  expect(input.getAttribute("max")).toBe("65535");
});

it("shows why a save was rejected", async () => {
  vi.mocked(updateConfig).mockRejectedValue(
    new ApiError(
      422,
      "Configuration validation failed",
      "ctf.end_time: must be after ctf.start_time",
    ),
  );
  renderRoute(Route, { path: "/admin/settings" });

  await userEvent.type(await screen.findByRole("textbox"), "x");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() =>
    expect(toast.error).toHaveBeenCalledWith("ctf.end_time: must be after ctf.start_time"),
  );
});
