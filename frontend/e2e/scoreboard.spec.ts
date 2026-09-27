import { submitFlag } from "./support/api";
import { WEB_BASICS_HIDDEN } from "./support/challenges";
import { expect, test } from "./support/fixtures";

test("a team that scores shows on the scoreboard and links to its page", async ({
  page,
  signedIn,
  team,
}) => {
  await submitFlag(page.request, WEB_BASICS_HIDDEN);

  await page.goto("/scoreboard");
  const row = page.getByRole("row").filter({ hasText: team.name });
  await expect(row).toContainText("100");

  await row.click();

  await expect(page).toHaveURL(new RegExp(`/teams/${team.id}$`));
  await expect(page.getByRole("heading", { level: 1, name: team.name })).toBeVisible();
  await expect(page.getByText(signedIn.username)).toBeVisible();
});

test("the scoreboard narrows to one bracket, chart included", async ({ page }) => {
  // Seeded teams: team1 and team3 are students, team2 professionals.
  await page.goto("/scoreboard");
  const cell = (name: string) => page.getByRole("cell", { name, exact: true });
  const chart = page.getByRole("heading", { name: "Score Evolution" }).locator("xpath=..");
  const legend = (name: string) => chart.getByText(name, { exact: true });
  await expect(cell("team2")).toBeVisible();

  await page.getByRole("combobox", { name: "Bracket" }).click();
  await page.getByRole("option", { name: "student" }).click();

  await expect(cell("team1")).toBeVisible();
  await expect(cell("team3")).toBeVisible();
  await expect(cell("team2")).toHaveCount(0);
  await expect(legend("team1")).toBeVisible();
  await expect(legend("team2")).toHaveCount(0);
});
