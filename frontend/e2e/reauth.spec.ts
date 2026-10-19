import { uniqueName } from "./support/api";
import { expect, test } from "./support/fixtures";
import { ageSession } from "./support/session";

test("a player signed in long ago confirms their password to mint a token", async ({
  page,
  signedIn,
}) => {
  await ageSession(page.context(), 15 * 60);
  const name = uniqueName("token");
  await page.goto("/settings");

  await page.getByRole("button", { name: "New Token" }).click();
  const tokenDialog = page.getByRole("dialog").filter({ hasText: "New API token" });
  await tokenDialog.getByLabel("Name").fill(name);
  await tokenDialog.getByRole("button", { name: "All read", exact: true }).click();
  await tokenDialog.getByRole("button", { name: "Save" }).click();

  const reauth = page.getByRole("dialog", { name: "Confirm it's you" });
  await reauth.getByLabel("Password").fill("not-the-password");
  await reauth.getByRole("button", { name: "Confirm" }).click();
  await expect(reauth).toContainText("The username or password is incorrect.");

  await reauth.getByLabel("Password").fill(signedIn.password);
  await reauth.getByRole("button", { name: "Confirm" }).click();

  await expect(reauth).toBeHidden();
  await expect(page.getByRole("heading", { name: "Token created" })).toBeVisible();
  await expect(page).toHaveURL(/\/settings$/);
});

test("a player who cancels the confirmation keeps their session", async ({ page, signedIn: _ }) => {
  await ageSession(page.context(), 15 * 60);
  await page.goto("/settings");

  await page.getByRole("button", { name: "Enable 2FA" }).click();
  const reauth = page.getByRole("dialog", { name: "Confirm it's you" });
  await reauth.getByRole("button", { name: "Cancel" }).click();

  await expect(reauth).toBeHidden();
  await expect(page).toHaveURL(/\/settings$/);
});
