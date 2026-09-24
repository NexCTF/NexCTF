/**
 * NexCTF Plugin SDK — types for plugin developers.
 *
 * Copy this file into your plugin's frontend/src/ as sdk.ts.
 *
 * React and ReactDOM are provided by the host via window.__nexctf__ at runtime.
 * Mark them as external in your build and register with window.__nexctf_register__.
 * Ship the built bundle in your wheel; the host never builds plugin frontends.
 *
 * A plugin may ship a second, admin-only bundle (FrontendDef.admin_entry_file)
 * that only admins can download. Both register under the plugin key, which must
 * equal the key the host serves the bundle under, and must happen while the
 * bundle first runs (not after an await): registrations under any other key,
 * or from anywhere else, are ignored. Their slots are merged; pages are not,
 * so each bundle may define its own index page "". Each bundle must be a
 * single file: only the declared entry file is served, and its integrity hash
 * is checked by the browser.
 *
 * Each bundle may come with one stylesheet (FrontendDef.entry_css,
 * admin_entry_css), loaded alongside the script with its own integrity hash.
 * The host theme is exposed as CSS variables (--primary, --background, ...),
 * so a plugin's own Tailwind build follows the host look, dark mode included.
 *
 * Slots (v1):
 *   challenge_panel — rendered between challenge header and questions.
 *     Expose as: slots: { challenge_panel: YourComponent }
 *     Props: ChallengePanelProps
 *
 * Pages:
 *   Admin pages render at /admin/plugins/<key>/<path>, user pages at
 *   /plugins/<key>/<path>. Expose as: pages: { "": Index, workers: Workers }.
 *   The index page "" serves the plugin root only. Any other URL renders the
 *   page with the longest path that is a prefix of it, so "workers" also serves
 *   "workers/42" and the rest arrives in PluginPageProps; with no such page the
 *   host shows its own not-found message.
 *   Pages listed in FrontendDef.admin_pages / user_pages get a nav link.
 *
 * Host (window.__nexctf__.host):
 *   user, navigate, language and sdkVersion. Read them when rendering; they
 *   are kept current but changes do not re-render plugin components.
 */

import type { ComponentType } from "react";

/** Bumped on every breaking change to the host contract below. */
export const SDK_VERSION = 1;

export interface HostUser {
  id: string;
  username: string;
  role: string;
}

export interface PluginHost {
  /** The signed-in user, or null for a visitor. */
  user: HostUser | null;
  /** Navigate the host app to an absolute path, e.g. "/admin/plugins/demo/workers". */
  navigate: (path: string) => void;
  /** The active locale, e.g. "en". */
  language: string;
  sdkVersion: number;
}

declare global {
  interface Window {
    __nexctf__: {
      React: typeof import("react");
      ReactDOM: typeof import("react-dom");
      jsxRuntime: typeof import("react/jsx-runtime");
      host: PluginHost;
    };
    __nexctf_register__: (plugin: PluginRegistration) => void;
  }
}

export interface PublicChallenge {
  id: string;
  title: string;
  challenge_type: string;
  category: string | null;
  question_count: number;
  solved_count: number;
}

export interface ChallengePanelProps {
  challenge: PublicChallenge;
}

export interface PluginPageProps {
  /** The page's own path, as registered in `pages`. */
  path: string;
  /** What follows the page path in the URL, e.g. "42" for "workers/42" under "workers". */
  rest: string;
}

export interface PluginRegistration {
  key: string;
  slots?: Record<string, ComponentType<Record<string, unknown>>>;
  pages?: Record<string, ComponentType<PluginPageProps>>;
  /** Limits slots rendered for a challenge to these challenge types; pages are unaffected. */
  challenge_types?: string[] | null;
}
