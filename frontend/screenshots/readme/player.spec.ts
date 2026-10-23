import {
  ADMIN,
  expect,
  openChallenges,
  openScoreboard,
  openSqlInjection,
  PLAYER,
  shot,
  TEAM1_ID,
} from "../support";

shot("challenges", PLAYER, openChallenges);

shot("challenge_details", PLAYER, openSqlInjection);

shot("scoreboard", PLAYER, openScoreboard);

shot("settings", ADMIN, async (page) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
});

shot("team_details", ADMIN, async (page) => {
  await page.goto(`/teams/${TEAM1_ID}`);
  await expect(page.getByRole("heading", { name: "team1", exact: true })).toBeVisible();
  await page.getByText("Binary Reversing").click();
  await expect(page.getByText("Find the license key")).toBeVisible();
});
