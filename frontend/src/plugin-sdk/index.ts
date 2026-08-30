/**
 * NexCTF Plugin SDK — types for plugin developers.
 *
 * Copy this file into your plugin's frontend/src/ as sdk.ts.
 *
 * React and ReactDOM are provided by the host via window.__nexctf__ at runtime.
 * Mark them as external in your build and register with window.__nexctf_register__.
 * Ship the built bundle in your wheel; the host never builds plugin frontends.
 *
 * Slots (v1):
 *   challenge_panel — rendered between challenge header and questions.
 *     Expose as: slots: { challenge_panel: YourComponent }
 *     Props: ChallengePanelProps
 */

import type { ComponentType } from "react";

declare global {
  interface Window {
    __nexctf__: {
      React: typeof import("react");
      ReactDOM: typeof import("react-dom");
      jsxRuntime: typeof import("react/jsx-runtime");
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

export interface PluginRegistration {
  key: string;
  slots: Record<string, ComponentType<Record<string, unknown>>>;
  challenge_types?: string[] | null;
}
