import { createAccount, uniqueName } from "./support/api";
import { expect, signedInContext, test } from "./support/fixtures";

test("a player without a team creates one", async ({ page, signedIn: _ }) => {
  const name = uniqueName("team");

  await page.goto("/team");
  await expect(page.getByText("You need a team to submit answers.")).toBeVisible();
  await page.getByLabel("Team name").fill(name);
  await page.getByRole("button", { name: "Create team" }).click();

  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  await expect(page.getByText("Invite Code")).toBeVisible();
  await expect(page.getByText("1 / 4")).toBeVisible();
});

test("a teammate joins with the invite code", async ({ page, browser, admin, team }) => {
  const mate = await createAccount(admin);
  const context = await signedInContext(browser, mate);
  const matePage = await context.newPage();

  await matePage.goto("/team");
  await matePage.getByLabel("Invite code").fill(team.invite_code.toLowerCase());
  await matePage.getByRole("button", { name: "Join" }).click();

  await expect(matePage.getByRole("heading", { level: 1, name: team.name })).toBeVisible();
  await expect(matePage.getByText("2 / 4")).toBeVisible();
  await context.close();

  await page.goto("/team");
  await expect(page.getByText(mate.username)).toBeVisible();
});

test("a wrong invite code is refused", async ({ page, signedIn: _ }) => {
  await page.goto("/team");
  await page.getByLabel("Invite code").fill("NOPE0000");
  await page.getByRole("button", { name: "Join" }).click();

  await expect(page.getByText("No team found with this invite code.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Create team" })).toBeVisible();
});

test("regenerating the invite code retires the old one", async ({ page, team }) => {
  await page.goto("/team");
  await expect(page.getByText(team.invite_code)).toBeVisible();

  await page.getByRole("button", { name: "Regenerate" }).click();

  await expect(page.getByText(team.invite_code)).toHaveCount(0);
});

test("a player leaves their team after confirming", async ({ page, team }) => {
  await page.goto("/team");
  await page.getByRole("button", { name: "Leave team" }).click();
  await expect(page.getByRole("dialog")).toContainText(`Leave team "${team.name}"?`);
  await page.getByRole("dialog").getByRole("button", { name: "Leave team" }).click();

  await expect(page.getByRole("button", { name: "Create team" })).toBeVisible();
});

test("a member edits the team profile", async ({ page, team }) => {
  const name = uniqueName("renamed");
  await page.goto("/team");
  const profile = page.locator("form").filter({ has: page.getByLabel("Country") });

  await profile.getByLabel("Team name").fill(name);
  await profile.getByLabel("Country").fill("fr");
  await profile.getByLabel("School").fill("Nex University");
  await profile.getByLabel("Contact email").fill("captain@e2e.nexctf.lan");
  await profile.getByRole("button", { name: "Save" }).click();

  await expect(page.getByText("Team profile saved")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();

  await page.goto(`/teams/${team.id}`);
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  await expect(page.getByText("Nex University")).toBeVisible();
  await expect(page.getByText("captain@e2e.nexctf.lan")).toHaveCount(0);
});
