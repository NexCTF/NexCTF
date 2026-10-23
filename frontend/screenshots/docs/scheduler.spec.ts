import type { Page } from "@playwright/test";
import { ADMIN, adminContent, dialog, expect, openDialog, shot } from "../support";

/** Open the new job dialog, with `type` picked when given. */
async function newJob(page: Page, type?: string): Promise<void> {
  await openDialog(page, "/admin/scheduler", "New job");
  if (!type) return;
  await dialog(page).getByRole("combobox", { name: "Job type" }).click();
  await page.getByRole("option", { name: type }).click();
  await expect(dialog(page).getByText("Parameters")).toBeVisible();
}

shot(
  "scheduler/scheduler",
  ADMIN,
  async (page) => {
    await page.goto("/admin/scheduler");
    await expect(page.getByRole("cell", { name: "Close Misc Warmup" })).toBeVisible();
  },
  adminContent,
);

shot("scheduler/new_scheduler", ADMIN, (page) => newJob(page), dialog);

shot(
  "scheduler/new_scheduler_toggle_challenge",
  ADMIN,
  (page) => newJob(page, "toggle_challenge"),
  dialog,
);

shot(
  "scheduler/new_scheduler_send_notification",
  ADMIN,
  (page) => newJob(page, "send_notification"),
  dialog,
);

shot(
  "scheduler/scheduler_details",
  ADMIN,
  async (page) => {
    await page.goto("/admin/scheduler");
    await page.getByRole("cell", { name: "Close Misc Warmup" }).click();
    await expect(page.getByRole("cell", { name: "success" })).toBeVisible();
  },
  adminContent,
);
