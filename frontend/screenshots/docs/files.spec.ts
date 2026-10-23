import { ADMIN, adminContent, dialog, expect, openDialog, shot } from "../support";

shot(
  "files/files",
  ADMIN,
  async (page) => {
    await page.goto("/admin/files");
    await expect(page.getByRole("cell", { name: "README.md" }).first()).toBeVisible();
  },
  adminContent,
);

shot("files/upload_file", ADMIN, (page) => openDialog(page, "/admin/files", "Upload file"), dialog);

shot("files/edit_file", ADMIN, (page) => openDialog(page, "/admin/files", "Edit"), dialog);
