import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { getAdminFiles } from "@/lib/api";
import { copyToClipboard } from "@/lib/utils";
import { paginated } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./files";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminFiles: vi.fn(),
}));
vi.mock("@/lib/utils", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/utils")>()),
  copyToClipboard: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

const FILE = {
  id: "f-1",
  name: "logo.png",
  s3_key: "files/f-1",
  original_filename: "logo.png",
  mime_type: "image/png",
  file_size: 120,
  is_public: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.mocked(getAdminFiles).mockResolvedValue(paginated([FILE]));
});

it("copies an absolute public link", async () => {
  renderRoute(Route, { path: "/admin/files" });

  await userEvent.click(await screen.findByRole("button", { name: "Copy public link" }));

  expect(copyToClipboard).toHaveBeenCalledWith(`${window.location.origin}/api/v1/file/f-1/view`);
});

it("hides the link button on a private file", async () => {
  vi.mocked(getAdminFiles).mockResolvedValue(paginated([{ ...FILE, is_public: false }]));
  renderRoute(Route, { path: "/admin/files" });

  await screen.findByRole("button", { name: "Preview" });
  expect(screen.queryByRole("button", { name: "Copy public link" })).toBeNull();
});
