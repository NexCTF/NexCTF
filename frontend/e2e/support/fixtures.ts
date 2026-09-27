import {
  type APIRequestContext,
  type Browser,
  type BrowserContext,
  test as base,
  expect,
  type Page,
} from "@playwright/test";
import { type Account, adminApi, createAccount, createTeam, signIn, type TeamSummary } from "./api";

interface Fixtures {
  /** A fresh, verified account that is not signed in anywhere yet. */
  account: Account;
  /** `account`, signed in on `page` but without a team. */
  signedIn: Account;
  /** `signedIn`, captain of a fresh team, so it starts with no solves. */
  team: TeamSummary;
}

interface WorkerFixtures {
  admin: APIRequestContext;
}

export const test = base.extend<Fixtures, WorkerFixtures>({
  admin: [
    // biome-ignore lint/correctness/noEmptyPattern: Playwright requires the destructuring
    async ({}, use) => {
      const admin = await adminApi();
      await use(admin);
      await admin.dispose();
    },
    { scope: "worker" },
  ],
  account: async ({ admin }, use) => {
    await use(await createAccount(admin));
  },
  signedIn: async ({ account, page }, use) => {
    await signIn(page.request, account);
    await use(account);
  },
  team: async ({ signedIn: _, page }, use) => {
    await use(await createTeam(page.request));
  },
});

export { expect };

/** Fill and submit the sign-in form, opening it first unless `open` is false. */
export async function signInThroughForm(
  page: Page,
  username: string,
  password: string,
  open = true,
) {
  if (open) await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** A second browser signed in as `account`, standing in for another device or player. */
export async function signedInContext(browser: Browser, account: Account): Promise<BrowserContext> {
  const context = await browser.newContext();
  await signIn(context.request, account);
  return context;
}
