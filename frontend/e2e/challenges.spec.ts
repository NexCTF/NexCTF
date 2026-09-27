import { createAccount, joinTeam, submitFlag } from "./support/api";
import { answer, CAESAR_DECRYPT, openChallenge, question } from "./support/challenges";
import { expect, signedInContext, test } from "./support/fixtures";

// Challenges, questions, hints and flags come from the backend development fixtures.

// Answering needs a team; a fresh one per test keeps every board unsolved.
test.beforeEach(async ({ team: _ }) => {});

test("the board lists active challenges only", async ({ page }) => {
  await page.goto("/challenges");

  await expect(page.getByRole("heading", { name: "Challenges" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "cryptography" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Caesar Cipher/ })).toContainText("0/2 questions");
  await expect(page.getByRole("link", { name: /Web Basics/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Misc Warmup/ })).toHaveCount(0);
});

test("a wrong flag is refused and the right one solves the question", async ({ page }) => {
  await openChallenge(page, "Caesar Cipher");
  const card = question(page, "Decrypt the message");

  await answer(card, "nexctf{not_it}");
  await expect(page.getByText("Wrong answer, try again.")).toBeVisible();

  await answer(card, "nexctf{julius_w0uld_be_proud}");
  await expect(page.getByText("Correct! 🎉")).toBeVisible();
  await expect(card.getByText("✓ Solved")).toBeVisible();
  await expect(page.getByText("1/2 questions solved")).toBeVisible();

  await page.getByRole("link", { name: "Back to challenges" }).click();
  await expect(page.getByRole("link", { name: /Caesar Cipher/ })).toContainText("1/2 questions");
});

test("a sequential challenge unlocks questions in order", async ({ page }) => {
  await openChallenge(page, "SQL Injection 101");
  const next = page.getByRole("button", { name: "Extract the admin password" });
  await expect(next).toHaveCount(0);

  await answer(question(page, "Bypass the login"), "nexctf{sql_injection_basic}");

  await expect(next).toBeVisible();
  await expect(page.getByRole("button", { name: "Read /etc/passwd" })).toHaveCount(0);
});

test("unlocking a paid hint asks for confirmation first", async ({ page }) => {
  await openChallenge(page, "Caesar Cipher");
  const card = question(page, "Decrypt the message");
  const content = "ROT13 is a Caesar cipher with shift 13. Try other shifts.";

  await card.getByRole("button", { name: "10 pts", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Unlock this hint for 10 points?");
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(card.getByText(content)).toHaveCount(0);

  await card.getByRole("button", { name: "10 pts", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Unlock" }).click();
  await expect(card.getByText(content)).toBeVisible();
});

test("completing a challenge opens the feedback form", async ({ page }) => {
  await openChallenge(page, "Caesar Cipher");
  await expect(page.getByRole("heading", { name: "Feedback" })).toHaveCount(0);

  await answer(question(page, "Decrypt the message"), "nexctf{julius_w0uld_be_proud}");
  await expect(question(page, "Decrypt the message").getByText("✓ Solved")).toBeVisible();
  await answer(question(page, "What shift was used?"), "nexctf{13}");
  await expect(page.getByText("2/2 questions solved")).toBeVisible();

  await page.getByRole("button", { name: "Rate 4 out of 5" }).click();
  await page.getByPlaceholder("Anything you liked").fill("Nice warm-up.");
  await page.getByRole("button", { name: "Send feedback" }).click();

  await expect(page.getByText("Thanks for the feedback!")).toBeVisible();
  await expect(page.getByRole("button", { name: "Update feedback" })).toBeVisible();
});

test("a trap flag is refused like any wrong answer", async ({ page }) => {
  await openChallenge(page, "OSINT Starter");
  const card = question(page, "Find the target's email");

  await answer(card, "nexctf{decoy_email}");

  await expect(page.getByText("Wrong answer, try again.")).toBeVisible();
  await expect(card.getByRole("button", { name: "Submit" })).toBeVisible();
  await expect(card.getByText("✓ Solved")).toHaveCount(0);
});

test("a question a teammate just solved is reported as already solved", async ({
  page,
  browser,
  admin,
  team,
}) => {
  await openChallenge(page, "Caesar Cipher");
  const card = question(page, "Decrypt the message");

  const mate = await signedInContext(browser, await createAccount(admin));
  await joinTeam(mate.request, team.invite_code);
  await submitFlag(mate.request, CAESAR_DECRYPT);
  await mate.close();

  await answer(card, CAESAR_DECRYPT.flag);

  await expect(page.getByText("Already solved!")).toBeVisible();
  await expect(card.getByText("✓ Solved")).toBeVisible();
});

test("the write-up shows once the team completes the challenge", async ({ page }) => {
  await openChallenge(page, "Web Basics");
  const writeup = page.getByRole("heading", { name: "Writeup" });
  await expect(writeup).toHaveCount(0);

  await answer(question(page, "Find the hidden flag"), "nexctf{web_basics_flag}");
  await expect(question(page, "Find the hidden flag").getByText("✓ Solved")).toBeVisible();
  await expect(writeup).toHaveCount(0);

  await answer(question(page, "Bypass the HTTP auth"), "nexctf{basic_auth_bypass}");

  await expect(writeup).toBeVisible();
  await expect(page.getByText("curl -u admin:admin https://target/admin")).toBeVisible();
});
