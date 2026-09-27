import { expect, test } from "./support/fixtures";

test("the dark theme applies at once and survives a reload", async ({ page }) => {
  await page.goto("/scoreboard");
  const root = page.locator("html");
  await expect(root).not.toHaveClass(/\bdark\b/);

  await page.getByRole("button", { name: "Toggle theme" }).click();
  await page.getByRole("menuitem", { name: "Dark" }).click();
  await expect(root).toHaveClass(/\bdark\b/);

  await page.reload();
  await expect(root).toHaveClass(/\bdark\b/);

  await page.getByRole("button", { name: "Toggle theme" }).click();
  await page.getByRole("menuitem", { name: "Light" }).click();
  await expect(root).not.toHaveClass(/\bdark\b/);
});

test("switching to French translates the interface and sticks", async ({ page }) => {
  await page.goto("/scoreboard");
  await expect(page.getByRole("link", { name: "Scoreboard" })).toBeVisible();

  await page.getByRole("button", { name: "Change language" }).click();
  await page.getByRole("menuitem", { name: "Français" }).click();

  await expect(page.getByRole("link", { name: "Classement" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Équipes" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Scoreboard" })).toHaveCount(0);

  await page.reload();
  await expect(page.getByRole("link", { name: "Classement" })).toBeVisible();
});
