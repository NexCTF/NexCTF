import React from "react";
import * as jsxRuntime from "react/jsx-runtime";
import ReactDOM from "react-dom";
import {
  type PluginHost,
  type PluginPageProps,
  type PluginRegistration,
  SDK_VERSION,
} from "@/plugin-sdk/index";

export type { PluginHost, PluginPageProps, PluginRegistration };

/** Public bundles load for every visitor; admin bundles once the admin area opens. */
export type PluginScope = "user" | "admin";

export interface PluginPageEntry {
  path: string;
  label: string | Record<string, string>;
  icon: string | null;
  section: string;
}

export interface PluginManifestEntry {
  key: string;
  remote_entry: string;
  integrity: string;
  stylesheet: { url: string; integrity: string } | null;
  slots: string[];
  pages: PluginPageEntry[];
  challenge_types: string[] | null;
}

const MANIFEST_URLS: Record<PluginScope, string> = {
  user: "/api/v1/plugins/manifest",
  admin: "/api/v1/admin/plugins/manifest",
};

type SlotMap = NonNullable<PluginRegistration["slots"]>;
type PageMap = NonNullable<PluginRegistration["pages"]>;
type StoredRegistration = Omit<PluginRegistration, "slots" | "pages"> & { slots: SlotMap };

interface BundleIdentity {
  key: string;
  scope: PluginScope;
}

/** The plugin and side each loaded bundle script was served for. */
const bundleScripts = new WeakMap<Element, BundleIdentity>();

const pluginRegistry: Record<string, StoredRegistration> = {};

/** Pages per bundle: a plugin's user and admin bundles may both define `""`. */
const pluginPages: Record<PluginScope, Record<string, PageMap>> = { user: {}, admin: {} };

/** Kept current by `PluginHostBridge` once the app has mounted. */
export const pluginHost: PluginHost = {
  user: null,
  navigate: (path) => window.location.assign(path),
  language: "en",
  sdkVersion: SDK_VERSION,
};

window.__nexctf__ = { React, ReactDOM, jsxRuntime, host: pluginHost };
window.__nexctf_register__ = (plugin) => {
  const bundle = document.currentScript && bundleScripts.get(document.currentScript);
  if (bundle?.key !== plugin.key) {
    console.error(
      `[plugin:${plugin.key}] ignored: registered from ${bundle ? `the bundle of "${bundle.key}"` : "outside a plugin bundle"}`,
    );
    return;
  }
  const { pages, ...rest } = plugin;
  const existing = pluginRegistry[plugin.key];
  pluginRegistry[plugin.key] = {
    ...existing,
    ...rest,
    slots: { ...existing?.slots, ...plugin.slots },
  };
  pluginPages[bundle.scope][plugin.key] = { ...pluginPages[bundle.scope][plugin.key], ...pages };
};

/** Mark `script` as the bundle of plugin `key` for `scope`, the only source it may register from. */
export function tagBundleScript(script: Element, key: string, scope: PluginScope): void {
  bundleScripts.set(script, { key, scope });
}

/** Plugins filling `slotName`; with a `challengeType`, only those allowed for that type. */
export function getPluginsForSlot(slotName: string, challengeType?: string): StoredRegistration[] {
  return Object.values(pluginRegistry).filter(
    (p) =>
      slotName in p.slots &&
      (challengeType === undefined ||
        !p.challenge_types ||
        p.challenge_types.includes(challengeType)),
  );
}

export interface ResolvedPluginPage {
  Page: React.ComponentType<PluginPageProps>;
  props: PluginPageProps;
}

/**
 * Return the page the `scope` bundle of plugin `key` registered for `subpath`:
 * the index page `""` for the plugin root only, otherwise the page with the
 * longest path that prefixes it.
 */
export function findPluginPage(
  scope: PluginScope,
  key: string,
  subpath: string,
): ResolvedPluginPage | null {
  const pages = pluginPages[scope][key] ?? {};
  const target = subpath.replace(/^\/+|\/+$/g, "");
  const path = Object.keys(pages)
    .filter((p) => target === p || (p !== "" && target.startsWith(`${p}/`)))
    .sort((a, b) => b.length - a.length)[0];
  if (path === undefined) return null;
  const rest = target.slice(path.length).replace(/^\//, "");
  return { Page: pages[path], props: { path, rest } };
}

const manifests: Partial<Record<PluginScope, Promise<PluginManifestEntry[]>>> = {};

/** The bundles listed for `scope`, empty when the manifest cannot be fetched. */
export function pluginManifest(scope: PluginScope): Promise<PluginManifestEntry[]> {
  manifests[scope] ??= _fetchManifest(scope);
  return manifests[scope];
}

async function _fetchManifest(scope: PluginScope): Promise<PluginManifestEntry[]> {
  try {
    const res = await fetch(MANIFEST_URLS[scope]);
    return res.ok ? ((await res.json()) as PluginManifestEntry[]) : [];
  } catch {
    return [];
  }
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
  const manifest = await pluginManifest(scope);
  await Promise.allSettled(
    manifest.flatMap((entry) => [_loadStyle(entry), _loadScript(entry, scope)]),
  );
}

function _loadStyle({ key, stylesheet }: PluginManifestEntry): Promise<void> {
  if (!stylesheet) return Promise.resolve();
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = stylesheet.url;
  link.integrity = stylesheet.integrity;
  return _append(key, link, "href");
}

function _loadScript(entry: PluginManifestEntry, scope: PluginScope): Promise<void> {
  const script = document.createElement("script");
  script.src = entry.remote_entry;
  script.integrity = entry.integrity;
  tagBundleScript(script, entry.key, scope);
  return _append(entry.key, script, "src");
}

/** Append `el` unless an element with the same URL is already in the head. */
function _append(key: string, el: HTMLElement, urlAttr: "src" | "href"): Promise<void> {
  const url = el.getAttribute(urlAttr);
  if (document.head.querySelector(`${el.tagName}[${urlAttr}="${url}"]`)) return Promise.resolve();
  return new Promise((resolve, reject) => {
    el.onload = () => resolve();
    el.onerror = () => {
      console.error(`[plugin:${key}] file failed to load or verify: ${url}`);
      reject(new Error(`plugin file failed: ${url}`));
    };
    document.head.appendChild(el);
  });
}
