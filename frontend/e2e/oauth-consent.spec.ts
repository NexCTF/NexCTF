import type { Page } from "@playwright/test";
import { expect, signInThroughForm, test } from "./support/fixtures";

// OAuth clients from the backend development fixtures.
const DISPLAY = {
  clientId: "nexctf_scoreboard_display",
  redirectUri: "https://display.example.com/callback",
};
const STAFF = { clientId: "nexctf_staff_tools", redirectUri: "https://staff.example.com/callback" };

function consentPath(client: typeof DISPLAY, state = "e2e-state"): string {
  const params = new URLSearchParams({
    client_id: client.clientId,
    redirect_uri: client.redirectUri,
    scope: "openid profile",
    state,
  });
  return `/oauth/consent?${params}`;
}

/** Whether `url` is the app's callback, compared exactly rather than by pattern. */
function isCallback(url: URL, client: typeof DISPLAY): boolean {
  return `${url.origin}${url.pathname}` === client.redirectUri;
}

/** Stand in for the app: answer its callback so the browser has somewhere to land. */
async function serveCallback(page: Page, client: typeof DISPLAY): Promise<void> {
  await page.route(`${client.redirectUri}**`, (route) =>
    route.fulfill({ contentType: "text/html", body: "<p>app callback</p>" }),
  );
}

test("a signed-out player signs in and comes back to the consent page", async ({
  page,
  account,
}) => {
  await page.goto(consentPath(DISPLAY));
  await expect(page).toHaveURL(/\/login\?next=/);

  await signInThroughForm(page, account.username, account.password, false);

  await expect(page).toHaveURL(/\/oauth\/consent\?/);
  await expect(page.getByText("Authorization Request")).toBeVisible();
  await expect(page.getByText(`Signed in as ${account.username}`)).toBeVisible();
});

test("allowing an app sends it back an authorization code", async ({ page, signedIn: _ }) => {
  await serveCallback(page, DISPLAY);
  await page.goto(consentPath(DISPLAY));
  await expect(page.getByText("Scoreboard Display is requesting access")).toBeVisible();
  await expect(page.getByText("Read your username")).toBeVisible();

  await page.getByRole("button", { name: "Allow" }).click();

  await expect(page).toHaveURL((url) => isCallback(url, DISPLAY));
  const params = new URL(page.url()).searchParams;
  expect(params.get("code")).toBeTruthy();
  expect(params.get("state")).toBe("e2e-state");
});

test("denying an app sends it back an access_denied error", async ({ page, signedIn: _ }) => {
  await serveCallback(page, DISPLAY);
  await page.goto(consentPath(DISPLAY));

  await page.getByRole("button", { name: "Deny" }).click();

  await expect(page).toHaveURL((url) => isCallback(url, DISPLAY));
  const params = new URL(page.url()).searchParams;
  expect(params.get("error")).toBe("access_denied");
  expect(params.get("code")).toBeNull();
});

test("an app restricted to admins turns players away", async ({ page, signedIn: _ }) => {
  await page.goto(consentPath(STAFF));

  await expect(page.getByText("Access denied")).toBeVisible();
  await expect(page.getByRole("button", { name: "Allow" })).toHaveCount(0);
});

test("a consent link to an address the app never registered is refused", async ({
  page,
  signedIn: _,
}) => {
  await page.goto(consentPath({ ...DISPLAY, redirectUri: "https://evil.example.com/phish" }));

  await expect(page.getByText("Invalid authorization request")).toBeVisible();
  await expect(page.getByRole("button", { name: "Deny" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Allow" })).toHaveCount(0);
});
