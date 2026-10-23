import type { Locator, Page } from "@playwright/test";
import {
  ADMIN,
  adminContent,
  dialog,
  expect,
  openDialog,
  SECURITY_QUIZ_ID,
  SQL_INJECTION_ID,
  shot,
} from "../support";

/** Open the editor of challenge `id` and unfold question `label`, returning its card. */
async function openQuestion(page: Page, id: string, label: string): Promise<Locator> {
  await page.goto(`/admin/challenges/${id}`);
  const header = page.getByText(label, { exact: true }).locator("xpath=..");
  await header.getByRole("button").last().click();
  return header.locator("xpath=..");
}

/** Open the add-solution dialog of question `label`, on the type picker. */
async function addSolution(page: Page, id: string, label: string): Promise<void> {
  const card = await openQuestion(page, id, label);
  await card.getByRole("button", { name: "Add Solution" }).click();
  await expect(dialog(page)).toBeVisible();
}

/** Pick `type` in the open type picker, its card named by the type then its description. */
async function pickType(page: Page, type: string, kind: "challenge" | "solution"): Promise<void> {
  await dialog(page)
    .getByRole("button", { name: new RegExp(`^${type} `) })
    .click();
  await expect(dialog(page).getByText(`New ${type} ${kind}`)).toBeVisible();
}

shot(
  "challenges/challenges",
  ADMIN,
  async (page) => {
    await page.goto("/admin/challenges");
    await expect(page.getByRole("cell", { name: "Security Quiz" })).toBeVisible();
  },
  adminContent,
);

shot(
  "challenges/challenge_type",
  ADMIN,
  (page) => openDialog(page, "/admin/challenges", "New Challenge"),
  dialog,
);

shot(
  "challenges/new_challenge",
  ADMIN,
  async (page) => {
    await openDialog(page, "/admin/challenges", "New Challenge");
    await pickType(page, "standard", "challenge");
  },
  dialog,
);

shot(
  "challenges/new_question",
  ADMIN,
  (page) => openDialog(page, `/admin/challenges/${SQL_INJECTION_ID}`, "Add Question"),
  dialog,
);

shot(
  "challenges/solution_type",
  ADMIN,
  (page) => addSolution(page, SQL_INJECTION_ID, "Bypass the login"),
  dialog,
);

shot(
  "challenges/new_match_solution",
  ADMIN,
  async (page) => {
    await addSolution(page, SQL_INJECTION_ID, "Bypass the login");
    await pickType(page, "match", "solution");
  },
  dialog,
);

shot(
  "challenges/new_regex_solution",
  ADMIN,
  async (page) => {
    await addSolution(page, SQL_INJECTION_ID, "Bypass the login");
    await pickType(page, "regex", "solution");
  },
  dialog,
);

shot(
  "challenges/new_mcq_solution",
  ADMIN,
  async (page) => {
    await addSolution(page, SECURITY_QUIZ_ID, "Default HTTPS port");
    await pickType(page, "mcq", "solution");
  },
  dialog,
);

shot(
  "challenges/new_hint",
  ADMIN,
  async (page) => {
    const card = await openQuestion(page, SQL_INJECTION_ID, "Bypass the login");
    await card.getByRole("button", { name: "Add Hint" }).click();
    await expect(dialog(page).getByText("Add hint")).toBeVisible();
  },
  dialog,
);

shot(
  "challenges/add_file",
  ADMIN,
  async (page) => {
    const card = await openQuestion(page, SQL_INJECTION_ID, "Bypass the login");
    await card.getByRole("button", { name: "Manage Files" }).click();
    await expect(dialog(page).getByText("README.md").first()).toBeVisible();
  },
  dialog,
);
