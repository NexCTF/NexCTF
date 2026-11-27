import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import {
  deleteAdminFile,
  getAdminChallenges,
  getAdminFile,
  getAdminFiles,
  getAdminFilesSummary,
} from "@/lib/api";
import { copyToClipboard } from "@/lib/utils";
import { paginated, storedFile } from "@/test/fixtures";
import { clickAndConfirm, renderRoute } from "@/test/render";
import { Route } from "./files";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminFiles: vi.fn(),
  getAdminFile: vi.fn(),
  getAdminFilesSummary: vi.fn(),
  getAdminChallenges: vi.fn(),
  deleteAdminFile: vi.fn(),
}));
vi.mock("@/lib/utils", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/utils")>()),
  copyToClipboard: vi.fn(),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

const LINKED = storedFile({
  usages: [
    { kind: "challenge", target_id: "c1", label: "Baby RSA", challenge_id: "c1" },
    { kind: "page_text", target_id: "p1", label: "Rules", challenge_id: null },
  ],
});

beforeEach(() => {
  vi.mocked(getAdminFiles).mockResolvedValue(paginated([storedFile()]));
  vi.mocked(getAdminFilesSummary).mockResolvedValue({
    count: 3,
    total_size: 2048,
    unused_count: 1,
  });
  vi.mocked(deleteAdminFile).mockResolvedValue(undefined);
  vi.mocked(getAdminChallenges).mockResolvedValue(paginated([]));
});

it("copies an absolute public link", async () => {
  renderRoute(Route, { path: "/admin/files" });

  await userEvent.click(await screen.findByRole("button", { name: "Copy public link" }));

  expect(copyToClipboard).toHaveBeenCalledWith(`${window.location.origin}/api/v1/file/f-1/view`);
});

it("hides the link button on a private file", async () => {
  vi.mocked(getAdminFiles).mockResolvedValue(paginated([storedFile({ is_public: false })]));
  renderRoute(Route, { path: "/admin/files" });

  await screen.findByRole("button", { name: "Preview" });
  expect(screen.queryByRole("button", { name: "Copy public link" })).toBeNull();
});

it("shows the summary and where a file is used", async () => {
  vi.mocked(getAdminFiles).mockResolvedValue(paginated([LINKED]));
  renderRoute(Route, { path: "/admin/files" });

  expect(await screen.findByText("3 files · 2.0 KB · 1 unused")).toBeDefined();
  await userEvent.click(await screen.findByRole("button", { name: "Used (2)" }));

  expect(await screen.findByText("Baby RSA")).toBeDefined();
  expect(screen.getByText("Rules")).toBeDefined();
});

it("deletes an unused file without forcing", async () => {
  renderRoute(Route, { path: "/admin/files" });

  await clickAndConfirm(await screen.findByRole("button", { name: "Delete" }), "Delete");

  await waitFor(() => expect(deleteAdminFile).toHaveBeenCalledWith("f-1", false));
});

it("forces the delete of a used file after naming its usages", async () => {
  vi.mocked(getAdminFiles).mockResolvedValue(paginated([LINKED]));
  renderRoute(Route, { path: "/admin/files" });

  await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
  expect(await screen.findByText(/Challenge file: Baby RSA/)).toBeDefined();
  await userEvent.click(screen.getByRole("button", { name: "Unlink and delete" }));

  await waitFor(() => expect(deleteAdminFile).toHaveBeenCalledWith("f-1", true));
});

it("previews a PDF from a local copy typed as a PDF", async () => {
  const pdf = storedFile({ mime_type: "application/pdf", original_filename: "notes.pdf" });
  vi.mocked(getAdminFiles).mockResolvedValue(paginated([pdf]));
  vi.mocked(getAdminFile).mockResolvedValue({
    ...pdf,
    view_url: "https://s3.example/notes.pdf",
    download_url: "https://s3.example/notes.pdf?dl",
  });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(new Uint8Array([0x25, 0x50]), { status: 200 })),
  );
  const created: Blob[] = [];
  URL.createObjectURL = vi.fn((blob: Blob) => {
    created.push(blob);
    return "blob:preview";
  });
  URL.revokeObjectURL = vi.fn();
  renderRoute(Route, { path: "/admin/files" });

  await userEvent.click(await screen.findByRole("button", { name: "Preview" }));

  await waitFor(() =>
    expect(document.querySelector("iframe")?.getAttribute("src")).toBe("blob:preview"),
  );
  expect(fetch).toHaveBeenCalledWith("https://s3.example/notes.pdf");
  expect(created[0].type).toBe("application/pdf");
  vi.unstubAllGlobals();
});
