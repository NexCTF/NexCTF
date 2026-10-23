import type { Page } from "@playwright/test";
import { ADMIN, adminContent, dialog, expect, openDialog, shot } from "../support";

/** Open the editor of the seeded Rules page. */
async function openRules(page: Page): Promise<void> {
  await page.goto("/admin/pages");
  await page.getByRole("button", { name: "Edit" }).click();
  await expect(page.getByLabel("Title")).toHaveValue("Rules");
}

shot(
  "pages/pages",
  ADMIN,
  async (page) => {
    await page.goto("/admin/pages");
    await expect(page.getByRole("cell", { name: "Rules", exact: true })).toBeVisible();
  },
  adminContent,
);

shot("pages/new_page", ADMIN, (page) => openDialog(page, "/admin/pages", "New page"), dialog);

shot("pages/edit_page", ADMIN, openRules, adminContent);

shot(
  "pages/insert_file",
  ADMIN,
  async (page) => {
    await openRules(page);
    await page.getByRole("button", { name: "Insert file" }).click();
    await expect(dialog(page).getByText("README.md").first()).toBeVisible();
  },
  dialog,
);
