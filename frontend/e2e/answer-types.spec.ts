import { answer, openChallenge, question } from "./support/challenges";
import { expect, test } from "./support/fixtures";

// "Security Quiz" from the backend development fixtures: one question per answer format.

test.beforeEach(async ({ page, team: _ }) => {
  await openChallenge(page, "Security Quiz");
});

test("a single-choice question takes the one right option", async ({ page }) => {
  const card = question(page, "Default HTTPS port");
  await expect(card.getByRole("radio")).toHaveCount(4);
  const submit = card.getByRole("button", { name: "Submit" });
  await expect(submit).toBeDisabled();

  await card.getByRole("radio", { name: "80", exact: true }).check();
  await submit.click();
  await expect(page.getByText("Wrong answer, try again.")).toBeVisible();

  await card.getByRole("radio", { name: "443" }).check();
  await expect(card.getByRole("radio", { name: "80", exact: true })).not.toBeChecked();
  await submit.click();
  await expect(card.getByText("✓ Solved")).toBeVisible();
});

test("a multi-select question needs every right option and no other", async ({ page }) => {
  const card = question(page, "Pick the hash functions");
  const submit = card.getByRole("button", { name: "Submit" });

  await card.getByRole("checkbox", { name: "MD5" }).check();
  await submit.click();
  await expect(page.getByText("Wrong answer, try again.")).toBeVisible();

  await card.getByRole("checkbox", { name: "SHA-256" }).check();
  await card.getByRole("checkbox", { name: "AES" }).check();
  await submit.click();
  await expect(page.getByText("Wrong answer, try again.")).toHaveCount(2);

  await card.getByRole("checkbox", { name: "AES" }).uncheck();
  await submit.click();
  await expect(card.getByText("✓ Solved")).toBeVisible();
});

test("a free-text answer is written in a text area", async ({ page }) => {
  const card = question(page, "What does XSS stand for?");
  await expect(card.getByRole("textbox")).toHaveJSProperty("tagName", "TEXTAREA");

  await answer(card, "Cross-Site Scripting");

  await expect(card.getByText("✓ Solved")).toBeVisible();
});

test("a code answer keeps Tab for indentation", async ({ page }) => {
  const card = question(page, "Print the flag in Python");
  const editor = card.getByPlaceholder("Enter your answer");

  await editor.fill("if True:\n");
  await editor.press("End");
  await editor.press("Tab");
  await expect(editor).toBeFocused();
  await expect(editor).toHaveValue("if True:\n  ");

  await answer(card, 'print("nexctf{hello}")');
  await expect(card.getByText("✓ Solved")).toBeVisible();
  await expect(page.getByText("1/4 questions solved")).toBeVisible();
});
