import React from "react";
import * as jsxRuntime from "react/jsx-runtime";
import ReactDOM from "react-dom";
import type { PluginRegistration } from "@/plugin-sdk/index";

export type { PluginRegistration };

/** Public bundles load for every visitor; admin bundles once the admin area opens. */
export type PluginScope = "user" | "admin";

interface PluginManifestEntry {
  key: string;
  remote_entry: string;
  integrity: string;
  slots: string[];
  challenge_types: string[] | null;
}

const MANIFEST_URLS: Record<PluginScope, string> = {
  user: "/api/v1/plugins/manifest",
  admin: "/api/v1/admin/plugins/manifest",
};

const pluginRegistry: Record<string, PluginRegistration> = {};

window.__nexctf__ = { React, ReactDOM, jsxRuntime };
window.__nexctf_register__ = (plugin) => {
  const existing = pluginRegistry[plugin.key];
  pluginRegistry[plugin.key] = {
    ...existing,
    ...plugin,
    slots: { ...existing?.slots, ...plugin.slots },
  };
};

export function getPluginsForSlot(slotName: string, challengeType?: string): PluginRegistration[] {
  return Object.values(pluginRegistry).filter(
    (p) =>
      slotName in p.slots &&
      (!p.challenge_types ||
        (challengeType !== undefined && p.challenge_types.includes(challengeType))),
  );
}

const bootstraps: Partial<Record<PluginScope, Promise<void>>> = {};
let ready: Promise<unknown> = Promise.resolve();

export function bootstrapPlugins(scope: PluginScope = "user"): Promise<void> {
  if (!bootstraps[scope]) {
    bootstraps[scope] = _bootstrap(scope);
    ready = Promise.all(Object.values(bootstraps));
  }
  return bootstraps[scope];
}

/** Settles once every bundle load started so far has settled. */
export function pluginsReady(): Promise<unknown> {
  return ready;
}

async function _bootstrap(scope: PluginScope): Promise<void> {
  let manifest: PluginManifestEntry[];
  try {
    const res = await fetch(MANIFEST_URLS[scope]);
    if (!res.ok) return;
    manifest = (await res.json()) as PluginManifestEntry[];
  } catch {
    return;
  }

  await Promise.allSettled(manifest.map(_loadScript));
}

function _loadScript(entry: PluginManifestEntry): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${entry.remote_entry}"]`)) {
      resolve();
      return;
    }
    const s = document.createElement("script");
    s.src = entry.remote_entry;
    s.integrity = entry.integrity;
    s.onload = () => resolve();
    s.onerror = () => {
      console.error(`[plugin:${entry.key}] bundle failed to load or verify: ${entry.remote_entry}`);
      reject(new Error(`plugin script failed: ${entry.remote_entry}`));
    };
    document.head.appendChild(s);
  });
}
