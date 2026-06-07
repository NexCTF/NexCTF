/**
 * NexCTF Plugin SDK — copy this file into your plugin's frontend/src/.
 *
 * React and ReactDOM are provided by the host via window.__nexctf__.
 * You can import them normally; the build config externalises them.
 *
 * Slots (v1):
 *   challenge_panel — rendered between challenge header and questions.
 *     Expose as: slots: { challenge_panel: YourComponent }
 *     Props: ChallengePanelProps
 */

import type { ComponentType } from "react";

export interface PublicChallenge {
  id: string;
  title: string;
  challenge_type: string;
  category_id: string | null;
  category_name: string | null;
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
