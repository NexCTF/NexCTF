import type { Page } from "@playwright/test";
import { ADMIN_LOGIN, signIn } from "./support/api";
import { expect, test } from "./support/fixtures";

const PLAYER_PAGES = ["/", "/challenges", "/scoreboard", "/team", "/settings"];
const ADMIN_PAGES = [
  "/admin",
  "/admin/challenges",
  "/admin/users",
  "/admin/teams",
  "/admin/submissions",
  "/admin/scoreboard",
  "/admin/scheduler",
  "/admin/pages",
  "/admin/settings",
];

test.use({ viewport: { width: 390, height: 844 } });

/** Load `path` and assert the document is no wider than the viewport. */
async function expectFitsViewport(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await expect(page.locator("h1").first()).toBeVisible();
  await expect(page.locator(".animate-pulse")).toHaveCount(0);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, `${path} scrolls sideways`).toBeLessThanOrEqual(0);
}

test("player pages fit a phone screen", async ({ page, team: _ }) => {
  for (const path of PLAYER_PAGES) await expectFitsViewport(page, path);
});

for (const path of ADMIN_PAGES) {
  test(`${path} fits a phone screen`, async ({ page }) => {
    await signIn(page.request, ADMIN_LOGIN);
    await expectFitsViewport(page, path);
  });
}

test("the player menu navigates and closes", async ({ page, signedIn: _ }) => {
  await page.goto("/challenges");
  await page.getByRole("button", { name: "Menu" }).click();
  const menu = page.getByRole("dialog", { name: "Menu" });
  await menu.getByRole("link", { name: "Scoreboard" }).click();

  await expect(page).toHaveURL(/\/scoreboard$/);
  await expect(menu).toBeHidden();
});

test("the admin drawer navigates and closes", async ({ page }) => {
  await signIn(page.request, ADMIN_LOGIN);
  await page.goto("/admin");
  await page.getByRole("button", { name: "Menu" }).click();
  const drawer = page.getByRole("dialog", { name: "Menu" });
  await drawer.getByRole("link", { name: "Users" }).click();

  await expect(page).toHaveURL(/\/admin\/users$/);
  await expect(drawer).toBeHidden();
});
