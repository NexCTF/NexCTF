import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { fileMarkdown, MarkdownEditor } from "@/components/ui/markdown-editor";
import { getAdminFiles, markFilePublic, uploadAdminFile } from "@/lib/api";
import { paginated, storedFile } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminFiles: vi.fn(),
  uploadAdminFile: vi.fn(),
  markFilePublic: vi.fn(),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}));

const clip = storedFile({
  id: "f1",
  name: "Clip",
  original_filename: "clip.mp4",
  mime_type: "video/mp4",
});

function Harness() {
  const [value, setValue] = useState("");
  return <MarkdownEditor value={value} onChange={setValue} />;
}

function renderEditor() {
  renderWithQuery(<Harness />);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getAdminFiles).mockResolvedValue(paginated([]));
  vi.mocked(uploadAdminFile).mockResolvedValue({ ...clip, duplicates: [] });
});

it("writes image, media and plain-file markdown for a stored file", () => {
  expect(fileMarkdown({ ...clip, mime_type: "image/png" })).toBe("![Clip](/api/v1/file/f1/view)");
  expect(fileMarkdown(clip)).toBe("[Clip](/api/v1/file/f1/view#clip.mp4)");
  expect(fileMarkdown({ ...clip, mime_type: "application/zip" })).toBe(
    "[Clip](/api/v1/file/f1/view)",
  );
});

it("uploads a public file from the picker and inserts it", async () => {
  renderEditor();

  await userEvent.click(screen.getByRole("button", { name: /insert file/i }));
  await userEvent.upload(
    await screen.findByTestId("file-picker-upload"),
    new File(["x"], "clip.mp4", { type: "video/mp4" }),
  );
  await waitFor(() => expect(uploadAdminFile).toHaveBeenCalled());
  await userEvent.click(screen.getByRole("button", { name: "Insert" }));

  const [name, , isPublic] = vi.mocked(uploadAdminFile).mock.calls[0] ?? [];
  expect(name).toBe("clip.mp4");
  expect(isPublic).toBe(true);
  await waitFor(() =>
    expect(screen.getByRole("textbox")).toHaveProperty(
      "value",
      "[Clip](/api/v1/file/f1/view#clip.mp4)",
    ),
  );
});

it("warns before publishing a private file it inserts", async () => {
  const secret = storedFile({ id: "f2", name: "Secret", mime_type: "application/zip" });
  vi.mocked(getAdminFiles).mockResolvedValue(paginated([{ ...secret, is_public: false }]));
  vi.mocked(markFilePublic).mockResolvedValue(secret);
  renderEditor();

  await userEvent.click(screen.getByRole("button", { name: /insert file/i }));
  await userEvent.click(await screen.findByRole("radio", { name: "Secret" }));

  expect(screen.getByText(/Secret will be made public/)).toBeDefined();
  await userEvent.click(screen.getByRole("button", { name: "Insert" }));

  await waitFor(() => expect(markFilePublic).toHaveBeenCalledWith("f2", true));
  await waitFor(() =>
    expect(screen.getByRole("textbox")).toHaveProperty("value", "[Secret](/api/v1/file/f2/view)"),
  );
});

it("uploads a pasted image and inserts it", async () => {
  const shot = storedFile({ id: "f3", name: "shot.png", mime_type: "image/png" });
  vi.mocked(uploadAdminFile).mockResolvedValue({ ...shot, duplicates: [] });
  renderEditor();

  fireEvent.paste(screen.getByRole("textbox"), {
    clipboardData: {
      types: ["text/plain", "Files"],
      files: [new File(["png"], "shot.png", { type: "image/png" })],
    },
  });

  await waitFor(() =>
    expect(screen.getByRole("textbox")).toHaveProperty(
      "value",
      "![shot.png](/api/v1/file/f3/view)",
    ),
  );
  expect(vi.mocked(uploadAdminFile).mock.calls[0]?.[2]).toBe(true);
});

it("leaves a document paste that also carries an image alone", async () => {
  renderEditor();

  fireEvent.paste(screen.getByRole("textbox"), {
    clipboardData: {
      types: ["text/plain", "text/html", "Files"],
      files: [new File(["png"], "cell.png", { type: "image/png" })],
    },
  });

  expect(uploadAdminFile).not.toHaveBeenCalled();
});
