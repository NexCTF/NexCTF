import type { PluginRegistration, PluginScope } from "@/lib/plugins";

/**
 * Register `plugin` as though the `scope` bundle served for `servedAs` were running.
 *
 * Imported lazily so it tags scripts in the same module instance a test got
 * after `vi.resetModules()`.
 */
export async function registerFrom(
  servedAs: string | null,
  plugin: PluginRegistration,
  scope: PluginScope = "user",
) {
  const { tagBundleScript } = await import("@/lib/plugins");
  const script = document.createElement("script");
  if (servedAs) tagBundleScript(script, servedAs, scope);
  Object.defineProperty(document, "currentScript", { value: script, configurable: true });
  try {
    window.__nexctf_register__(plugin);
  } finally {
    Object.defineProperty(document, "currentScript", { value: null, configurable: true });
  }
}
