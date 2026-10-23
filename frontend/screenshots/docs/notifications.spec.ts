import { ADMIN, adminContent, dialog, expect, openDialog, shot } from "../support";

shot(
  "notifications/notifications",
  ADMIN,
  async (page) => {
    await page.goto("/admin/notifications");
    await expect(page.getByRole("cell", { name: "New challenge available" })).toBeVisible();
  },
  adminContent,
);

shot(
  "notifications/new_notification",
  ADMIN,
  (page) => openDialog(page, "/admin/notifications", "New notification"),
  dialog,
);
