import { ADMIN, adminContent, dialog, expect, openDialog, shot } from "../support";

shot(
  "links/links",
  ADMIN,
  async (page) => {
    await page.goto("/admin/links");
    await expect(page.getByRole("cell", { name: "GitHub", exact: true })).toBeVisible();
  },
  adminContent,
);

shot("links/new_link", ADMIN, (page) => openDialog(page, "/admin/links", "New link"), dialog);
