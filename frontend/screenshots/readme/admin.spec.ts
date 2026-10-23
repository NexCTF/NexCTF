import {
  ADMIN,
  expect,
  openDashboard,
  openPlugins,
  SQL_INJECTION_ID,
  shot,
  TEAM1_ID,
  USER1_ID,
} from "../support";

shot("admin_dashboard", ADMIN, openDashboard);

shot("admin_challenge_edit", ADMIN, async (page) => {
  await page.goto(`/admin/challenges/${SQL_INJECTION_ID}`);
  await expect(page.getByRole("heading", { name: "SQL Injection 101", exact: true })).toBeVisible();
  await expect(page.getByText("Bypass the login")).toBeVisible();
});

shot("admin_submissions", ADMIN, async (page) => {
  await page.goto("/admin/submissions");
  await expect(page.getByRole("heading", { name: "Submissions", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "team1" }).first()).toBeVisible();
});

shot("admin_user_details", ADMIN, async (page) => {
  await page.goto(`/admin/users/${USER1_ID}`);
  await expect(page.getByRole("heading", { name: "user1", exact: true })).toBeVisible();
});

shot("admin_team_details", ADMIN, async (page) => {
  await page.goto(`/admin/teams/${TEAM1_ID}`);
  await expect(page.getByRole("heading", { name: "team1", exact: true })).toBeVisible();
});

shot("admin_plugins", ADMIN, openPlugins);
