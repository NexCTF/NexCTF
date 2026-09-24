import { screen } from "@testing-library/react";
import { beforeAll, expect, it, vi } from "vitest";
import type { PluginPageProps } from "@/lib/plugins";
import { registerFrom } from "@/test/plugins";
import { renderRoute } from "@/test/render";
import { Route } from "./plugins.$key.$";

vi.mock("@/lib/plugins", async (importOriginal) => {
  const loaded = Promise.resolve();
  return {
    ...(await importOriginal<typeof import("@/lib/plugins")>()),
    bootstrapPlugins: () => loaded,
  };
});

const renderPage = (path: string) =>
  renderRoute(Route, { path, routePath: "/admin/plugins/$key/$" });

function Workers({ path, rest }: PluginPageProps) {
  return <p>{`workers page ${path}:${rest}`}</p>;
}

function Broken(): never {
  throw new Error("boom");
}

beforeAll(async () => {
  await registerFrom(
    "demo",
    {
      key: "demo",
      pages: { "": () => <p>index page</p>, workers: Workers, broken: Broken },
    },
    "admin",
  );
  await registerFrom("demo", { key: "demo", pages: { "": () => <p>user index page</p> } });
});

it("renders the page a plugin registered for the path", async () => {
  renderPage("/admin/plugins/demo/workers/42");

  expect(await screen.findByText("workers page workers:42")).toBeDefined();
});

it("renders the index page at the plugin root", async () => {
  renderPage("/admin/plugins/demo");

  expect(await screen.findByText("index page")).toBeDefined();
});

it("says so when the plugin has no such page, even with an index page", async () => {
  renderPage("/admin/plugins/demo/instances");

  expect(await screen.findByText("Page not found")).toBeDefined();
  expect(screen.queryByText("index page")).toBeNull();
});

it("contains a page that fails to render", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  renderPage("/admin/plugins/demo/broken");

  expect(await screen.findByText(/This plugin page failed to render/)).toBeDefined();
});
