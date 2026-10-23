import path from "node:path";
import { test as base, expect, type Locator, type Page } from "@playwright/test";
import { type Account, ADMIN_LOGIN, signIn } from "../e2e/support/api";

type Credentials = Pick<Account, "username" | "password">;

/** Accounts seeded by the backend development fixtures. */
export const ADMIN: Credentials = ADMIN_LOGIN;
export const PLAYER: Credentials = { username: "user1", password: "user1" };

/** IDs seeded by the backend development fixtures. */
export const ADMIN_ID = "f9a973c4-aecb-4b20-8529-ff8c7ec103bd";
export const SQL_INJECTION_ID = "a1000000-0000-4000-8000-000000000002";
export const MISC_WARMUP_ID = "a1000000-0000-4000-8000-000000000006";
export const SECURITY_QUIZ_ID = "a1000000-0000-4000-8000-000000000007";
export const TEAM1_ID = "435127a0-f2fb-4d2b-87bd-91ab77328e71";
export const USER1_ID = "1cd3b6dd-cd32-4984-aa25-fc2de4dd5544";

/** Crops for `shot()`: the content of an admin page without its sidebar, an open dialog. */
export const adminContent = (page: Page): Locator => page.locator("aside + div > :first-child");
export const dialog = (page: Page): Locator => page.getByRole("dialog");
/** And the whole page, for one longer than the viewport. */
export const wholePage = (page: Page): Locator => page.locator("body");

/** Open `url` and the dialog behind its `button`. */
export async function openDialog(page: Page, url: string, button: string): Promise<void> {
  await page.goto(url);
  await page.getByRole("button", { name: button }).click();
  await expect(dialog(page)).toBeVisible();
}

/** Pages captured for both the README and the documentation. */
export async function openDashboard(page: Page): Promise<void> {
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
}

export async function openPlugins(page: Page): Promise<void> {
  await page.goto("/admin/plugins");
  await expect(page.getByRole("heading", { name: "Plugins", exact: true })).toBeVisible();
}

export async function openChallenges(page: Page): Promise<void> {
  await page.goto("/challenges");
  await expect(page.getByRole("link", { name: "Web Basics" })).toBeVisible();
}

export async function openSqlInjection(page: Page): Promise<void> {
  await page.goto(`/challenges/${SQL_INJECTION_ID}`);
  await expect(page.getByRole("heading", { level: 1, name: "SQL Injection 101" })).toBeVisible();
  await expect(page.getByText("Bypass the login")).toBeVisible();
}

export async function openScoreboard(page: Page): Promise<void> {
  await page.goto("/scoreboard");
  await expect(page.getByRole("cell", { name: "team2" })).toBeVisible();
  await expect(page.locator(".recharts-curve").first()).toBeVisible();
}

/** Wait for skeletons, spinners and web fonts to be gone or ready. */
async function settle(page: Page): Promise<void> {
  await expect(page.locator(".animate-pulse, .animate-spin")).toHaveCount(0);
  await page.evaluate(() => document.fonts.ready);
}

/**
 * Capture `<name>.png` in the project's output, signed in as `account`, once
 * `prepare` has opened the page and waited for its content: the element `crop`
 * picks, or the whole viewport. The session is signed out afterwards.
 */
export function shot(
  name: string,
  account: Credentials,
  prepare: (page: Page) => Promise<void>,
  crop?: (page: Page) => Locator,
): void {
  base(name, async ({ page, colorScheme }, testInfo) => {
    const theme = colorScheme === "light" ? "light" : "dark";
    await page.addInitScript((t) => localStorage.setItem("nexctf-theme", t), theme);
    await signIn(page.request, account);
    try {
      await prepare(page);
      await settle(page);
      await (crop?.(page) ?? page).screenshot({
        path: path.join(testInfo.project.metadata.output, `${name}.png`),
        animations: "disabled",
        caret: "hide",
      });
    } finally {
      await page.request.post("/api/v1/auth/logout");
    }
  });
}

export { expect };
