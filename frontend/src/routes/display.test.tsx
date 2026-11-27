import { screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { EventStatusBadge, STALE_AFTER_MS, StaleBadge } from "@/components/display/display-header";
import {
  ApiError,
  getMyNotifications,
  getPublicInfo,
  getScoreboard,
  getScoreboardHistory,
} from "@/lib/api";
import { recentBroadcasts } from "@/lib/display";
import { publicInfo, publicInfoWith, scoreboard, user } from "@/test/fixtures";
import { renderRoute, renderWithQuery } from "@/test/render";
import { Route } from "./display";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getPublicInfo: vi.fn(),
  getScoreboard: vi.fn(),
  getScoreboardHistory: vi.fn(),
  getMyNotifications: vi.fn(),
}));

const notification = (id: string, title: string, is_broadcast: boolean, created_at: string) => ({
  id,
  title,
  content: `${title} body`,
  is_broadcast,
  created_at,
});

afterEach(() => {
  window.location.hash = "";
});

beforeEach(() => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfo());
  vi.mocked(getScoreboard).mockResolvedValue(scoreboard());
  vi.mocked(getScoreboardHistory).mockResolvedValue({ series: [], computed_at: "" });
  vi.mocked(getMyNotifications).mockResolvedValue({ notifications: [], last_read_at: null });
});

it("lists every team, also those scrolled out of view", async () => {
  const names = ["Alpha", "Beta", "Gamma", "Delta"];
  vi.mocked(getScoreboard).mockResolvedValue(
    scoreboard({
      entries: names.map((team_name, i) => ({
        rank: i + 1,
        team_id: `t${i}`,
        team_name,
        team_bracket: null,
        total: 400 - i * 100,
        custom_fields: {},
      })),
    }),
  );
  renderRoute(Route, { path: "/display" });

  expect(await screen.findByText("Delta")).toBeDefined();
  expect(screen.getAllByRole("listitem")).toHaveLength(4);
});

it("offers to sign in when the scoreboard needs an account", async () => {
  vi.mocked(getScoreboard).mockRejectedValue(new ApiError(401, "Unauthorized"));
  renderRoute(Route, { path: "/display?rotate=30" });

  const link = await screen.findByRole("link", { name: "Sign in on this screen" });
  expect(link.getAttribute("href")).toBe("/login?next=%2Fdisplay%3Frotate%3D30");
});

const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

it("cycles through the last 30 minutes of broadcasts, never a team notification", async () => {
  vi.mocked(getMyNotifications).mockResolvedValue({
    last_read_at: null,
    notifications: [
      notification("1", "Too old", true, minutesAgo(45)),
      notification("2", "Team only", false, minutesAgo(1)),
      notification("3", "Pizza is here", true, minutesAgo(10)),
      notification("4", "Heap 3 fixed", true, minutesAgo(2)),
    ],
  });
  renderRoute(Route, { path: "/display", auth: { user: user() } });

  expect(await screen.findByText("Heap 3 fixed")).toBeDefined();
  expect(screen.getByText("1/2")).toBeDefined();
  expect(screen.queryByText("Pizza is here")).toBeNull();
  expect(screen.queryByText("Too old")).toBeNull();
  expect(screen.queryByText("Team only")).toBeNull();
});

it("orders recent broadcasts newest first and drops older ones", () => {
  const now = Date.now();
  const list = [
    notification("a", "A", true, minutesAgo(29)),
    notification("b", "B", true, minutesAgo(31)),
    notification("c", "C", true, minutesAgo(5)),
  ];

  expect(recentBroadcasts(list, now).map((n) => n.title)).toEqual(["C", "A"]);
});

it.each([
  [0, false],
  [STALE_AFTER_MS + 1_000, true],
])("flags a refresh %i ms old as stale: %s", (age, stale) => {
  renderWithQuery(<StaleBadge lastSuccess={{ current: Date.now() - age }} />);

  expect(screen.queryByText(/Last update/) !== null).toBe(stale);
});

it.each([
  [{}, "Live"],
  [{ start_time: "2099-01-01T00:00:00Z" }, "Not started"],
  [{ freeze_time: "2026-01-01T00:00:00Z" }, "Scoreboard frozen"],
  [{ freeze_time: "2026-01-01T00:00:00Z", end_time: "2026-01-02T00:00:00Z" }, "Finished"],
])("shows the event status for %j as %s", async (competition, label) => {
  vi.mocked(getPublicInfo).mockResolvedValue(publicInfoWith(competition));
  renderWithQuery(<EventStatusBadge />);

  expect(await screen.findByText(label)).toBeDefined();
  const others = ["Live", "Not started", "Scoreboard frozen", "Finished"].filter(
    (l) => l !== label,
  );
  for (const other of others) expect(screen.queryByText(other)).toBeNull();
});

it("authenticates with the token in the link, ticker included, without a sign-in", async () => {
  window.location.hash = "#token=nxt_secret";
  vi.mocked(getMyNotifications).mockResolvedValue({
    last_read_at: null,
    notifications: [notification("1", "Pizza is here", true, minutesAgo(1))],
  });
  renderRoute(Route, { path: "/display" });

  expect(await screen.findByText("Pizza is here")).toBeDefined();
  expect(getScoreboard).toHaveBeenCalledWith(undefined, "nxt_secret");
  expect(getMyNotifications).toHaveBeenCalledWith("nxt_secret");
});

it("says a revoked screen link is no longer valid instead of offering a sign-in", async () => {
  window.location.hash = "#token=nxt_revoked";
  vi.mocked(getScoreboard).mockRejectedValue(new ApiError(401, "Unauthorized"));
  renderRoute(Route, { path: "/display" });

  expect(await screen.findByText(/link is no longer valid/)).toBeDefined();
  expect(screen.queryByRole("link", { name: "Sign in on this screen" })).toBeNull();
});

it("flags the screen as stale while part of it keeps failing, even right after a refresh", () => {
  renderWithQuery(<StaleBadge lastSuccess={{ current: Date.now() }} failing />);

  expect(screen.getByText(/Last update/)).toBeDefined();
});
