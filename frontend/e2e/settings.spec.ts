import type { Page } from "@playwright/test";
import { expect, signInThroughForm, test } from "./support/fixtures";

async function changePassword(page: Page, current: string, next: string, confirm = next) {
  await page.goto("/settings");
  await page.getByLabel("Current password").fill(current);
  await page.getByLabel("New password", { exact: true }).fill(next);
  await page.getByLabel("Confirm new password").fill(confirm);
  await page.getByRole("button", { name: "Change password" }).click();
}

test("a player changes their password", async ({ page, signedIn }) => {
  const newPassword = `new-${signedIn.password}`;

  await changePassword(page, signedIn.password, newPassword);
  await expect(page.getByText("Password changed")).toBeVisible();

  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await signInThroughForm(page, signedIn.username, newPassword);
  await expect(page.getByText(`Welcome, ${signedIn.username}`)).toBeVisible();
});

test("a password change needs matching new passwords", async ({ page, signedIn }) => {
  await changePassword(page, signedIn.password, "first-choice", "second-choice");

  await expect(page.getByText("Passwords do not match")).toBeVisible();
});

test("a password change needs the current password", async ({ page, signedIn }) => {
  await changePassword(page, "not-the-password", `new-${signedIn.password}`);

  await expect(page.getByText("Current password is incorrect")).toBeVisible();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
});

test("a player's public details show on their team page, private ones do not", async ({
  page,
  team,
}) => {
  await page.goto("/settings");
  await page.getByLabel("Discord").fill("player#1234");
  await page.getByLabel("Phone").fill("+33 6 00 00 00 00");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Profile saved")).toBeVisible();

  await page.goto(`/teams/${team.id}`);
  await expect(page.getByText("player#1234")).toBeVisible();
  await expect(page.getByText("+33 6 00 00 00 00")).toHaveCount(0);
});
