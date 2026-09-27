import { expect, type Locator, type Page } from "@playwright/test";

/** A question from the backend development fixtures, with its accepted flag. */
export interface SeededQuestion {
  challengeId: string;
  questionId: string;
  flag: string;
}

/** "Caesar Cipher" / "Decrypt the message". */
export const CAESAR_DECRYPT: SeededQuestion = {
  challengeId: "a1000000-0000-4000-8000-000000000004",
  questionId: "b1000000-0000-4000-8000-000000000005",
  flag: "nexctf{julius_w0uld_be_proud}",
};

/** "Web Basics" / "Find the hidden flag", worth 100 points. */
export const WEB_BASICS_HIDDEN: SeededQuestion = {
  challengeId: "a1000000-0000-4000-8000-000000000001",
  questionId: "b1000000-0000-4000-8000-000000000001",
  flag: "nexctf{web_basics_flag}",
};

/** A question's card: the parent of the header button carrying its label. */
export function question(page: Page, label: string): Locator {
  return page.getByRole("button", { name: label }).locator("xpath=..");
}

export async function openChallenge(page: Page, title: string): Promise<void> {
  await page.goto("/challenges");
  await page.getByRole("link", { name: title }).click();
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
}

/** Type an answer into a card's field (input or text area) and submit it. */
export async function answer(card: Locator, flag: string): Promise<void> {
  await card.getByPlaceholder("Enter your answer").fill(flag);
  await card.getByRole("button", { name: "Submit" }).click();
}
