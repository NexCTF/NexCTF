import type { Page } from "@playwright/test";
import { signIn } from "./support/api";
import { expect, signInThroughForm, test } from "./support/fixtures";
import { enableTotp, totpCode, typeOtp } from "./support/totp";

function totpSection(page: Page) {
  return page.getByRole("heading", { name: "Two-Factor Authentication" }).locator("xpath=../../..");
}

test("a player turns on 2FA from the settings", async ({ page, signedIn: _ }) => {
  await page.goto("/settings");
  await expect(totpSection(page)).toContainText("2FA is disabled");

  await page.getByRole("button", { name: "Enable 2FA" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Or enter the key manually:");
  const secret = await dialog.locator("code").innerText();
  await dialog.getByRole("button", { name: "Next" }).click();
  await typeOtp(dialog, totpCode(secret));
  await dialog.getByRole("button", { name: "Enable" }).click();

  await expect(page.getByText("Two-factor authentication enabled")).toBeVisible();
  await expect(totpSection(page)).toContainText("2FA is enabled");
});

test("a wrong setup code is refused without signing the player out", async ({
  page,
  signedIn: _,
}) => {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Enable 2FA" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Next" }).click();
  await typeOtp(dialog, "000000");
  await dialog.getByRole("button", { name: "Enable" }).click();

  await expect(dialog).toContainText("Invalid code, please try again.");
  await expect(page).toHaveURL(/\/settings$/);
});

test("a player with 2FA signs in with a code", async ({ page, account }) => {
  await signIn(page.request, account);
  const secret = await enableTotp(page.request);
  await page.request.post("/api/v1/auth/logout");

  await signInThroughForm(page, account.username, account.password);
  await expect(page.getByText("Enter the 6-digit code from your authenticator app.")).toBeVisible();

  // The field submits the form by itself once the sixth digit is in.
  await typeOtp(page.locator("form"), "000000");
  await expect(page.getByText("The one-time password is incorrect or has expired.")).toBeVisible();

  await typeOtp(page.locator("form"), totpCode(secret));
  await expect(page.getByText(`Welcome, ${account.username}`)).toBeVisible();
});

test("a player turns 2FA off with a current code", async ({ page, signedIn: _ }) => {
  const secret = await enableTotp(page.request);
  await page.goto("/settings");
  await expect(totpSection(page)).toContainText("2FA is enabled");

  await page.getByRole("button", { name: "Disable 2FA" }).click();
  const dialog = page.getByRole("dialog");
  await typeOtp(dialog, totpCode(secret));
  await dialog.getByRole("button", { name: "Disable", exact: true }).click();

  await expect(page.getByText("Two-factor authentication disabled")).toBeVisible();
  await expect(totpSection(page)).toContainText("2FA is disabled");
});
