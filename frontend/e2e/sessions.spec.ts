import type { BrowserContext } from "@playwright/test";
import { expect, signedInContext, test } from "./support/fixtures";

async function isSignedIn(device: BrowserContext): Promise<boolean> {
  return (await device.request.get("/api/v1/info/me")).ok();
}

test("a player signs out one of their other devices", async ({ page, browser, signedIn }) => {
  const device = await signedInContext(browser, signedIn);
  await page.goto("/settings");
  const signOutDevice = page.getByRole("button", { name: "Sign out this device" });
  await expect(page.getByText("This device")).toBeVisible();
  await expect(signOutDevice).toHaveCount(1);

  await signOutDevice.click();
  await page.getByRole("dialog").getByRole("button", { name: "Sign out this device" }).click();

  await expect(page.getByText("Session signed out")).toBeVisible();
  await expect(signOutDevice).toHaveCount(0);
  expect(await isSignedIn(device)).toBe(false);
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await device.close();
});

test("signing out everywhere ends every session, this one included", async ({
  page,
  browser,
  signedIn,
}) => {
  const device = await signedInContext(browser, signedIn);
  await page.goto("/settings");

  await page.getByRole("button", { name: "Sign out everywhere" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Sign out everywhere" }).click();

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("Sign in to your account")).toBeVisible();
  expect(await isSignedIn(device)).toBe(false);
  expect((await page.request.get("/api/v1/info/me")).status()).toBe(401);
  await device.close();
});
