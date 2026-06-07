import type { PluginRegistration } from "./sdk";
import ChallengePanel from "./ChallengePanel";

const plugin: PluginRegistration = {
  key: "nexctf_orchestrator",
  slots: { challenge_panel: ChallengePanel },
  challenge_types: ["orchestrator"],
};

export default plugin;
