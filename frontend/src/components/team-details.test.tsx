import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import type { TeamChallengeStats } from "@/lib/api";
import { renderWithRouter } from "@/test/render";
import { ChallengeProgressTable } from "./team-details";

// The admin ("detailed") variant keeps the public columns and adds the per-question rows.

const stats: TeamChallengeStats[] = [
  {
    challenge_id: "c-1",
    challenge_title: "Pwn me",
    question_count: 1,
    solved_question_count: 1,
    is_solved: true,
    attempt_count: 2,
    points_earned: 100,
    first_solve_at: "2026-08-20T10:00:00Z",
    last_solve_at: "2026-08-20T10:00:00Z",
    questions: [
      {
        question_id: "q-1",
        question_label: "Q1",
        is_solved: true,
        points_earned: 75,
        hint_unlock_count: 1,
        wrong_attempt_count: 1,
        solved_at: "2026-08-20T10:00:00Z",
        hints: [
          { hint_id: "h-1", title: "A nudge", cost_paid: 25, unlocked_at: "2026-08-20T09:00:00Z" },
        ],
      },
    ],
  },
];

// The public payload carries neither solve dates nor hint titles.
const publicStats: TeamChallengeStats[] = stats.map((c) => ({
  ...c,
  questions: c.questions.map(({ solved_at: _s, hints: _h, ...q }) => q),
}));

it("shows each solve date and unlocked hint", async () => {
  renderWithRouter(<ChallengeProgressTable stats={stats} detailed />);

  expect(await screen.findByText("Pwn me")).toBeTruthy();
  expect(screen.getAllByRole("columnheader")).toHaveLength(3);

  await userEvent.click(screen.getByText("1/1"));
  const expanded = document.querySelector("td[colspan]");
  expect(expanded?.getAttribute("colspan")).toBe("3");
  expect(screen.getByText("A nudge")).toBeTruthy();
  expect(screen.getByText("-25")).toBeTruthy();

  const solvedAt = new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date("2026-08-20T10:00:00Z"));
  expect(screen.getByText(solvedAt)).toBeTruthy();
});

it("hides the admin-only rows on the public table", async () => {
  renderWithRouter(<ChallengeProgressTable stats={publicStats} />);
  expect(await screen.findByText("Pwn me")).toBeTruthy();

  await userEvent.click(screen.getByText("1/1"));
  expect(screen.queryByText("A nudge")).toBeNull();
});
