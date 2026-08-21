import { expect, it } from "vitest";
import type { TableState } from "@/components/data-table";
import type { ChallengeStats } from "@/lib/api";
import { byCategory, clientPage, scoreBuckets } from "./index";

it("groups team totals into equal-width brackets", () => {
  const buckets = scoreBuckets([0, 100, 250, 800]);
  expect(buckets).toHaveLength(9);
  expect(buckets[0]).toEqual({ label: "0–99", teams: 1 });
  expect(buckets.at(-1)).toEqual({ label: "800–899", teams: 1 });
  expect(buckets.reduce((n, b) => n + b.teams, 0)).toBe(4);
});

it("returns nothing while no team has scored", () => {
  expect(scoreBuckets([])).toEqual([]);
  expect(scoreBuckets([0, 0, 0])).toEqual([]);
});

it("keeps negative totals in the first bracket rather than dropping them", () => {
  const buckets = scoreBuckets([-50, 10]);
  expect(buckets[0].teams).toBe(1);
  expect(buckets.reduce((n, b) => n + b.teams, 0)).toBe(2);
});

function cs(overrides: Partial<ChallengeStats> & { challenge_title: string }): ChallengeStats {
  return {
    challenge_id: overrides.challenge_title,
    category: null,
    points: 100,
    question_count: 1,
    attempt_count: 0,
    correct_count: 0,
    teams_attempted: 0,
    teams_solved: 0,
    hint_unlock_count: 0,
    hint_cost_spent: 0,
    first_blood_team_id: null,
    first_blood_team_name: null,
    first_blood_at: null,
    questions: [],
    ...overrides,
  };
}

const ROWS = [
  cs({ challenge_title: "Alpha", category: "web", teams_solved: 3 }),
  cs({ challenge_title: "Beta", category: "pwn", teams_solved: 9 }),
  cs({ challenge_title: "Gamma", category: "web", teams_solved: 1 }),
];

const STATE: TableState = {
  page: 1,
  perPage: 2,
  search: "",
  searchColumn: "",
  filters: {},
  sortColumn: null,
  sortDirection: "asc",
};

it("pages the list and defaults to the most-solved first", () => {
  const first = clientPage(ROWS, STATE);
  expect(first.data.map((r) => r.challenge_title)).toEqual(["Beta", "Alpha"]);
  expect(first.pagination).toMatchObject({ total_count: 3, pages: 2, has_more: true });

  const second = clientPage(ROWS, { ...STATE, page: 2 });
  expect(second.data.map((r) => r.challenge_title)).toEqual(["Gamma"]);
  expect(second.pagination.has_more).toBe(false);
});

it("searches title and category, and filters by category", () => {
  expect(clientPage(ROWS, { ...STATE, search: "amm" }).data).toHaveLength(1);
  expect(clientPage(ROWS, { ...STATE, search: "pwn" }).data[0].challenge_title).toBe("Beta");

  const filtered = clientPage(ROWS, { ...STATE, filters: { category: ["web"] } });
  expect(filtered.data.map((r) => r.challenge_title)).toEqual(["Alpha", "Gamma"]);
  expect(filtered.filter_attributes.category).toEqual(["pwn", "web"]);
});

it("sorts by the requested column in both directions", () => {
  const asc = clientPage(ROWS, { ...STATE, perPage: 10, sortColumn: "challenge_title" });
  expect(asc.data.map((r) => r.challenge_title)).toEqual(["Alpha", "Beta", "Gamma"]);

  const desc = clientPage(ROWS, {
    ...STATE,
    perPage: 10,
    sortColumn: "challenge_title",
    sortDirection: "desc",
  });
  expect(desc.data.map((r) => r.challenge_title)).toEqual(["Gamma", "Beta", "Alpha"]);
});

it("rolls challenges up per category, richest first", () => {
  const rows = byCategory([...ROWS, cs({ challenge_title: "Delta", points: 40 })]);
  expect(rows).toEqual([
    { category: "web", challenges: 2, points: 200 },
    { category: "pwn", challenges: 1, points: 100 },
    { category: "—", challenges: 1, points: 40 },
  ]);
});
