import { afterEach, beforeEach, expect, it, vi } from "vitest";

const entry = {
  key: "demo",
  remote_entry: "/api/v1/plugins/demo/frontend/bundle.js?v=abc",
  integrity: "sha384-abc",
  slots: ["challenge_panel"],
  challenge_types: null,
};

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

  window.__nexctf_register__({ key: "demo", slots: { challenge_panel: Panel } });
  window.__nexctf_register__({ key: "demo", slots: { admin_panel: AdminPanel } });

  const [plugin] = getPluginsForSlot("challenge_panel");
  expect(Object.keys(plugin.slots).sort()).toEqual(["admin_panel", "challenge_panel"]);
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
