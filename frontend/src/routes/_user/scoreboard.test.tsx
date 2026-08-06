import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { getPublicInfo, getScoreboard, getScoreboardHistory } from "@/lib/api";
import { publicInfoWith, scoreboard } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./scoreboard";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  getScoreboard: vi.fn(),
  getScoreboardHistory: vi.fn(),
}));

const FUTURE = "2099-01-01T00:00:00Z";
const PAST = "2020-01-01T00:00:00Z";

beforeEach(() => {
  // Running competition: started, not frozen, not ended.
  vi.mocked(getPublicInfo).mockResolvedValue(
    publicInfoWith({ start_time: PAST, freeze_time: FUTURE, end_time: FUTURE }),
  );
  vi.mocked(getScoreboard).mockResolvedValue(scoreboard());
  vi.mocked(getScoreboardHistory).mockResolvedValue({
    series: [],
    computed_at: "2026-01-01T12:00:00Z",
  });
});

it("ranks the teams by score", async () => {
  renderRoute(Route, { path: "/scoreboard" });

  const rows = await screen.findAllByRole("row");
  // rows[0] is the header
  expect(within(rows[1]).getByText("Alpha")).toBeDefined();
  expect(within(rows[1]).getByText("300")).toBeDefined();
  expect(within(rows[2]).getByText("Beta")).toBeDefined();
});

it("opens a team profile when its row is clicked", async () => {
  const { router } = renderRoute(Route, { path: "/scoreboard" });

  await userEvent.click(await screen.findByText("Beta"));

  await waitFor(() => expect(router.state.location.pathname).toBe("/teams/t2"));
});

it("shows an empty state when no team has scored", async () => {
  vi.mocked(getScoreboard).mockResolvedValue(scoreboard({ entries: [] }));
  renderRoute(Route, { path: "/scoreboard" });

  expect(await screen.findByText("No teams on the scoreboard yet.")).toBeDefined();
});

it("renders bracket and custom-field columns only when the data has them", async () => {
  vi.mocked(getScoreboard).mockResolvedValue(
    scoreboard({
      brackets: ["students"],
      custom_fields: [{ name: "school", label: "School" }],
      entries: [
        {
          rank: 1,
          team_id: "t1",
          team_name: "Alpha",
          team_bracket: "students",
          total: 300,
          custom_fields: { school: "MIT" },
        },
      ],
    }),
  );
  renderRoute(Route, { path: "/scoreboard" });

  expect(await screen.findByRole("columnheader", { name: "Bracket" })).toBeDefined();
  expect(screen.getByRole("columnheader", { name: "School" })).toBeDefined();
  expect(screen.getByText("MIT")).toBeDefined();
});

it("announces a competition that has not started", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(
    publicInfoWith({ start_time: FUTURE, freeze_time: FUTURE, end_time: FUTURE }),
  );
  renderRoute(Route, { path: "/scoreboard" });

  expect(await screen.findByText(/Competition starts on/)).toBeDefined();
});

it("announces a frozen scoreboard", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(
    publicInfoWith({ start_time: PAST, freeze_time: PAST, end_time: FUTURE }),
  );
  renderRoute(Route, { path: "/scoreboard" });

  expect(await screen.findByText(/Scoreboard frozen at/)).toBeDefined();
});

it("announces the end of the competition and drops the freeze notice", async () => {
  vi.mocked(getPublicInfo).mockResolvedValue(
    publicInfoWith({ start_time: PAST, freeze_time: PAST, end_time: PAST }),
  );
  renderRoute(Route, { path: "/scoreboard" });

  expect(await screen.findByText(/Competition ended on/)).toBeDefined();
  expect(screen.queryByText(/Scoreboard frozen at/)).toBeNull();
});

it("reports a failed load", async () => {
  vi.mocked(getScoreboard).mockRejectedValue(new Error("boom"));
  renderRoute(Route, { path: "/scoreboard" });

  expect(await screen.findByText("Failed to load scoreboard")).toBeDefined();
});
