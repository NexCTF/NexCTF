import { screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { getTeamProfile, getTeamScore } from "@/lib/api";
import { team } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./teams_.$teamId";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getTeamProfile: vi.fn(),
  getTeamScore: vi.fn(),
}));

const score = {
  team_id: "t1",
  team_name: "Alpha",
  total: 300,
  solve_points: 320,
  adjustment_points: 0,
  hint_points: -20,
  solves: [],
  adjustments: [],
  computed_at: "2026-01-01T12:00:00Z",
};

beforeEach(() => {
  vi.mocked(getTeamProfile).mockResolvedValue(team());
  vi.mocked(getTeamScore).mockResolvedValue(score);
});

function renderProfile(teamId = "t1") {
  return renderRoute(Route, { path: `/teams/${teamId}`, routePath: "/teams/$teamId" });
}

it("loads the profile of the team named in the URL", async () => {
  renderProfile("t42");

  expect(await screen.findByRole("heading", { name: "Alpha" })).toBeDefined();
  expect(getTeamProfile).toHaveBeenCalledWith("t42");
  expect(getTeamScore).toHaveBeenCalledWith("t42");
});

it("lists the members and the score breakdown", async () => {
  renderProfile();

  expect(await screen.findByText("player")).toBeDefined();
  expect(screen.getByText("Score breakdown")).toBeDefined();
});

it("links back to the scoreboard", async () => {
  renderProfile();

  const back = await screen.findByRole("link", { name: "Back to Scoreboard" });
  expect(back.getAttribute("href")).toBe("/scoreboard");
});

it("reports a failed load", async () => {
  vi.mocked(getTeamProfile).mockRejectedValue(new Error("boom"));
  renderProfile();

  expect(await screen.findByText("Failed to load team")).toBeDefined();
});
