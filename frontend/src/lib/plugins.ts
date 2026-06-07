import React from "react";
import * as jsxRuntime from "react/jsx-runtime";
import ReactDOM from "react-dom";
import type { PluginRegistration } from "@/plugin-sdk/index";

export type { PluginRegistration };

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PluginManifestEntry {
  key: string;
  remote_entry: string;
  slots: string[];
  challenge_types: string[] | null;
}

// ---------------------------------------------------------------------------
// Global declarations for plugin IIFE bundles
// ---------------------------------------------------------------------------

declare global {
  interface Window {
    __nexctf__: {
      React: typeof React;
      ReactDOM: typeof ReactDOM;
      jsxRuntime: typeof jsxRuntime;
    };
    __nexctf_register__: (plugin: PluginRegistration) => void;
  }
}

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

const pluginRegistry: Record<string, PluginRegistration> = {};

window.__nexctf__ = { React, ReactDOM, jsxRuntime };
window.__nexctf_register__ = (plugin) => {
  pluginRegistry[plugin.key] = plugin;
};

export function getPluginsForSlot(slotName: string, challengeType?: string): PluginRegistration[] {
  return Object.values(pluginRegistry).filter(
    (p) =>
      slotName in p.slots &&
      (!p.challenge_types ||
        (challengeType !== undefined && p.challenge_types.includes(challengeType))),
  );
}

// ---------------------------------------------------------------------------
// Bootstrap — fetch manifest and inject plugin scripts
// ---------------------------------------------------------------------------

let bootstrapPromise: Promise<void> | null = null;

export function bootstrapPlugins(): Promise<void> {
  if (!bootstrapPromise) bootstrapPromise = _bootstrap();
  return bootstrapPromise;
}

async function _bootstrap(): Promise<void> {
  let manifest: PluginManifestEntry[];
  try {
    const res = await fetch("/api/v1/plugins/manifest");
    if (!res.ok) return;
    manifest = (await res.json()) as PluginManifestEntry[];
  } catch {
    return;
  }

  await Promise.allSettled(manifest.map((e) => _loadScript(e.remote_entry)));
}

function _loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`plugin script failed: ${src}`));
    document.head.appendChild(s);
  });
}
