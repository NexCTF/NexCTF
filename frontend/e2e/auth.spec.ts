import { uniqueName, updateAccount } from "./support/api";
import { expect, signInThroughForm, test } from "./support/fixtures";
import { latestEmailTo, linkPath } from "./support/mail";

test("anonymous visitors are sent to the sign-in page", async ({ page }) => {
  await page.goto("/challenges");

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("Sign in to your account")).toBeVisible();
});

test("a player signs in and out", async ({ page, account }) => {
  await signInThroughForm(page, account.username, account.password);

  await expect(page.getByText(`Welcome, ${account.username}`)).toBeVisible();

  await page.getByRole("button", { name: "Sign out", exact: true }).click();

  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/challenges");
  await expect(page).toHaveURL(/\/login$/);
});

test("a wrong password is refused", async ({ page, account }) => {
  await signInThroughForm(page, account.username, "not-the-password");

  await expect(page.getByText("The username or password is incorrect.")).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});

test("a new player registers, verifies their email and signs in", async ({ page }) => {
  const username = uniqueName("e2e_reg");
  const email = `${username}@e2e.nexctf.lan`;
  const password = `pw-${username}`;

  await page.goto("/login");
  await page.getByRole("link", { name: "Sign up" }).click();
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign up" }).click();

  await expect(page.getByText("Check your inbox to verify your email")).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);

  // The account exists but stays locked until the email is confirmed.
  await signInThroughForm(page, username, password);
  await expect(page.getByText("Verify your email")).toBeVisible();

  await page.goto(linkPath(await latestEmailTo(email), "/verify-email"));
  await expect(page.getByText("Email verified")).toBeVisible();

  await signInThroughForm(page, username, password);
  await expect(page.getByText(`Welcome, ${username}`)).toBeVisible();
});

test("a player resets a forgotten password by email", async ({ page, account }) => {
  const newPassword = `new-${account.password}`;

  await page.goto("/login");
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await page.getByLabel("Email").fill(account.email);
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByText("Check your email")).toBeVisible();

  await page.goto(linkPath(await latestEmailTo(account.email), "/reset-password"));
  await page.getByLabel("New password").fill(newPassword);
  await page.getByLabel("Confirm password").fill(newPassword);
  await page.getByRole("button", { name: "Reset password" }).click();
  await expect(page.getByText("Password updated")).toBeVisible();

  await signInThroughForm(page, account.username, account.password);
  await expect(page.getByText("The username or password is incorrect.")).toBeVisible();

  await signInThroughForm(page, account.username, newPassword);
  await expect(page.getByText(`Welcome, ${account.username}`)).toBeVisible();
});

test("a disabled account is told so once the password is right", async ({
  page,
  admin,
  account,
}) => {
  await updateAccount(admin, account, { is_active: false });

  await signInThroughForm(page, account.username, "not-the-password");
  await expect(page.getByText("The username or password is incorrect.")).toBeVisible();

  await signInThroughForm(page, account.username, account.password);
  await expect(page.getByText("Account Disabled")).toBeVisible();
  await expect(page.getByText("Your account has been disabled.")).toBeVisible();
});

test("a player disabled mid-session is sent back to sign in", async ({ page, admin, signedIn }) => {
  await page.goto("/challenges");
  await expect(page.getByRole("heading", { name: "Challenges" })).toBeVisible();

  await updateAccount(admin, signedIn, { is_active: false });
  await page.getByRole("link", { name: "Teams" }).click();

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("Sign in to your account")).toBeVisible();
});

test("a player whose new email is unverified asks for another link", async ({
  page,
  admin,
  account,
}) => {
  const email = `${uniqueName("e2e_moved")}@e2e.nexctf.lan`;
  await updateAccount(admin, account, { email });

  await signInThroughForm(page, account.username, account.password);
  await expect(page.getByText("Verify your email")).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Resend verification email" }).click();
  await expect(page.getByText("a new link is on its way")).toBeVisible();

  await page.goto(linkPath(await latestEmailTo(email), "/verify-email"));
  await expect(page.getByText("Email verified")).toBeVisible();

  await signInThroughForm(page, account.username, account.password);
  await expect(page.getByText(`Welcome, ${account.username}`)).toBeVisible();
});
