import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { pluginManifestEntry } from "@/test/fixtures";
import { registerFrom } from "@/test/plugins";

const entry = pluginManifestEntry({
  key: "demo",
  remote_entry: "/api/v1/plugins/demo/frontend/bundle.js?v=abc",
  slots: ["challenge_panel"],
});

async function freshPlugins() {
  vi.resetModules();
  return import("./plugins");
}

function mockManifest(body: unknown, ok = true) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok, json: async () => body }));
}

/** Resolve or fail the script tag the loader appended, as the browser would. */
async function settleScript(event: "load" | "error") {
  await vi.waitFor(() => expect(document.head.querySelector("script")).not.toBeNull());
  document.head.querySelector("script")?.dispatchEvent(new Event(event));
}

beforeEach(() => {
  document.head.replaceChildren();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("loads each bundle with its integrity hash", async () => {
  mockManifest([entry]);
  const { bootstrapPlugins } = await freshPlugins();

  const done = bootstrapPlugins();
  await settleScript("load");
  await done;

  const script = document.head.querySelector("script");
  expect(script?.getAttribute("src")).toBe(entry.remote_entry);
  expect(script?.integrity).toBe("sha384-abc");
  expect(fetch).toHaveBeenCalledWith("/api/v1/plugins/manifest");
});

it("fetches admin bundles from the admin manifest", async () => {
  mockManifest([]);
  const { bootstrapPlugins } = await freshPlugins();

  await bootstrapPlugins("admin");

  expect(fetch).toHaveBeenCalledWith("/api/v1/admin/plugins/manifest");
});

it("names the plugin whose bundle fails to load or verify", async () => {
  mockManifest([entry]);
  const error = vi.spyOn(console, "error").mockImplementation(() => {});
  const { bootstrapPlugins } = await freshPlugins();

  const done = bootstrapPlugins();
  await settleScript("error");
  await done;

  expect(error).toHaveBeenCalledWith(expect.stringContaining("[plugin:demo]"));
});

it("merges the slots a plugin's public and admin bundles register", async () => {
  const { getPluginsForSlot } = await freshPlugins();
  const Panel = () => null;
  const AdminPanel = () => null;

  await registerFrom("demo", { key: "demo", slots: { challenge_panel: Panel } });
  await registerFrom("demo", { key: "demo", slots: { admin_panel: AdminPanel } });

  const [plugin] = getPluginsForSlot("challenge_panel");
  expect(Object.keys(plugin.slots ?? {}).sort()).toEqual(["admin_panel", "challenge_panel"]);
  expect(getPluginsForSlot("admin_panel")).toHaveLength(1);
});

it("is ready only once a load started later has settled too", async () => {
  mockManifest([]);
  const { bootstrapPlugins, pluginsReady } = await freshPlugins();

  await bootstrapPlugins();
  let settled = false;
  let finishAdmin = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise((r) => (finishAdmin = () => r({ ok: true, json: async () => [] })))),
  );
  void bootstrapPlugins("admin");
  void pluginsReady().then(() => (settled = true));

  await Promise.resolve();
  expect(settled).toBe(false);
  finishAdmin();
  await vi.waitFor(() => expect(settled).toBe(true));
});

it("loads a bundle's stylesheet with its own integrity hash", async () => {
  const sheet = { url: "/api/v1/plugins/demo/frontend/bundle.css?v=def", integrity: "sha384-def" };
  mockManifest([{ ...entry, stylesheet: sheet }]);
  const { bootstrapPlugins } = await freshPlugins();

  const done = bootstrapPlugins();
  await settleScript("load");
  const link = document.head.querySelector<HTMLLinkElement>("link[rel=stylesheet]");
  link?.dispatchEvent(new Event("load"));
  await done;

  expect(link?.getAttribute("href")).toBe(sheet.url);
  expect(link?.integrity).toBe("sha384-def");
});

it("ignores a registration under a key other than the bundle's own", async () => {
  const error = vi.spyOn(console, "error").mockImplementation(() => {});
  const { getPluginsForSlot } = await freshPlugins();
  const Panel = () => null;

  await registerFrom("demo", { key: "other", slots: { challenge_panel: Panel } });
  await registerFrom(null, { key: "demo", slots: { challenge_panel: Panel } });

  expect(getPluginsForSlot("challenge_panel")).toEqual([]);
  expect(error).toHaveBeenCalledWith(expect.stringContaining('the bundle of "demo"'));
  expect(error).toHaveBeenCalledWith(expect.stringContaining("outside a plugin bundle"));
});

it("narrows a slot to the plugin's challenge types only when given one", async () => {
  const { getPluginsForSlot } = await freshPlugins();
  const Panel = () => null;

  await registerFrom("demo", {
    key: "demo",
    challenge_types: ["orchestrator"],
    slots: { challenge_panel: Panel, admin_panel: Panel },
  });

  expect(getPluginsForSlot("challenge_panel", "standard")).toEqual([]);
  expect(getPluginsForSlot("challenge_panel", "orchestrator")).toHaveLength(1);
  expect(getPluginsForSlot("admin_panel")).toHaveLength(1);
});

it("resolves the root to the index page, a subpath to its longest matching page", async () => {
  const { findPluginPage } = await freshPlugins();
  const Index = () => null;
  const Workers = () => null;

  await registerFrom("demo", { key: "demo", pages: { "": Index, workers: Workers } });

  expect(findPluginPage("user", "demo", "")?.Page).toBe(Index);
  expect(findPluginPage("user", "demo", "workers/42/")?.props).toEqual({
    path: "workers",
    rest: "42",
  });
  expect(findPluginPage("user", "demo", "workersx")).toBeNull();
  expect(findPluginPage("user", "other", "")).toBeNull();
  expect(findPluginPage("user", "demo", "instances")).toBeNull();
});

it("keeps the pages of a plugin's user and admin bundles apart", async () => {
  const { findPluginPage } = await freshPlugins();
  const Home = () => null;
  const Overview = () => null;

  await registerFrom("demo", { key: "demo", pages: { "": Home } });
  await registerFrom("demo", { key: "demo", pages: { "": Overview } }, "admin");

  expect(findPluginPage("user", "demo", "")?.Page).toBe(Home);
  expect(findPluginPage("admin", "demo", "")?.Page).toBe(Overview);
});

it("lets a loaded bundle register under its key, for the side it was loaded for", async () => {
  mockManifest([entry]);
  const { bootstrapPlugins, findPluginPage } = await freshPlugins();
  const Overview = () => null;

  const done = bootstrapPlugins("admin");
  await settleScript("load");
  await done;
  const script = document.head.querySelector("script");
  Object.defineProperty(document, "currentScript", { value: script, configurable: true });
  window.__nexctf_register__({ key: "demo", pages: { "": Overview } });
  Object.defineProperty(document, "currentScript", { value: null, configurable: true });

  expect(findPluginPage("admin", "demo", "")?.Page).toBe(Overview);
  expect(findPluginPage("user", "demo", "")).toBeNull();
});
