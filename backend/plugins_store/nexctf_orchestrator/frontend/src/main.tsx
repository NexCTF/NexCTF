// Dev-only entry point — not used when loaded as a federation remote.
import { createRoot } from "react-dom/client";
import ChallengePanel from "./ChallengePanel";

createRoot(document.getElementById("root")!).render(
  <ChallengePanel
    challenge={{
      id: "preview",
      title: "Preview",
      challenge_type: "container",
      category_id: null,
      category_name: null,
      question_count: 1,
      solved_count: 0,
    }}
  />
);
