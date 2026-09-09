import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import {
  createAdminScoreAdjustment,
  getAdminChallenges,
  getAdminScoreAdjustments,
  updateAdminScoreAdjustment,
} from "@/lib/api";
import { paginated } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./score-adjustments";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminScoreAdjustments: vi.fn(),
  getAdminChallenges: vi.fn(),
  createAdminScoreAdjustment: vi.fn(),
  updateAdminScoreAdjustment: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

beforeEach(() => {
  vi.mocked(getAdminScoreAdjustments).mockResolvedValue(paginated([]));
  vi.mocked(getAdminChallenges).mockResolvedValue(
    // biome-ignore lint/suspicious/noExplicitAny: only id/title are read here
    paginated([{ id: "c-1", title: "Caesar Cipher" }]) as any,
  );
  vi.mocked(createAdminScoreAdjustment).mockResolvedValue({} as never);
  vi.mocked(updateAdminScoreAdjustment).mockResolvedValue({} as never);
});

const ROW = {
  id: "a-1",
  team_id: "t-1",
  team_name: "Alpha",
  amount: 25,
  reason: "Clean writeup",
  challenge_id: "c-1",
  challenge_title: "Caesar Cipher",
  created_by_id: "u-1",
  created_by_username: "admin",
};

async function openDialog() {
  renderRoute(Route, { path: "/admin/score-adjustments" });
  await userEvent.click(await screen.findByRole("button", { name: /add adjustment/i }));
  return screen.findByRole("dialog");
}

it("picks an optional challenge, defaulting to none", async () => {
  const dialog = await openDialog();
  expect(within(dialog).getByText("None")).toBeTruthy();

  await userEvent.click(within(dialog).getByText("None"));
  await userEvent.click(await screen.findByRole("option", { name: "Caesar Cipher" }));

  expect(within(dialog).getByText("Caesar Cipher")).toBeTruthy();
});

it("clears the challenge from an existing adjustment", async () => {
  // biome-ignore lint/suspicious/noExplicitAny: only the picked fields are read
  vi.mocked(getAdminScoreAdjustments).mockResolvedValue(paginated([ROW]) as any);
  renderRoute(Route, { path: "/admin/score-adjustments" });

  await userEvent.click(await screen.findByRole("button", { name: /edit/i }));
  const dialog = await screen.findByRole("dialog");
  await userEvent.click(within(dialog).getByText("Caesar Cipher"));
  await userEvent.click(await screen.findByRole("option", { name: "None" }));
  await userEvent.click(within(dialog).getByRole("button", { name: /save/i }));

  expect(vi.mocked(updateAdminScoreAdjustment)).toHaveBeenCalledWith(
    "a-1",
    expect.objectContaining({ challenge_id: null }),
  );
});
