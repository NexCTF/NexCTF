import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, it, vi } from "vitest";
import { fileMarkdown, MarkdownEditor } from "@/components/ui/markdown-editor";
import { getAdminFiles, uploadAdminFile } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminFiles: vi.fn(),
  uploadAdminFile: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const stored = {
  id: "f1",
  name: "Clip",
  original_filename: "clip.mp4",
  mime_type: "video/mp4",
  is_public: true,
};

it("writes image, media and plain-file markdown for a stored file", () => {
  expect(fileMarkdown({ ...stored, mime_type: "image/png" } as never)).toBe(
    "![Clip](/api/v1/file/f1/view)",
  );
  expect(fileMarkdown(stored as never)).toBe("[Clip](/api/v1/file/f1/view#clip.mp4)");
  expect(fileMarkdown({ ...stored, mime_type: "application/zip" } as never)).toBe(
    "[Clip](/api/v1/file/f1/view)",
  );
});

it("renames, uploads and inserts a file without leaving the editor", async () => {
  vi.mocked(getAdminFiles).mockResolvedValue({ data: [] } as never);
  vi.mocked(uploadAdminFile).mockResolvedValue(stored as never);

  function Harness() {
    const [value, setValue] = useState("");
    return <MarkdownEditor value={value} onChange={setValue} />;
  }
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Harness />
    </QueryClientProvider>,
  );

  await userEvent.click(screen.getByRole("button", { name: /insert file/i }));
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await userEvent.upload(input, new File(["x"], "clip.mp4", { type: "video/mp4" }));

  const nameField = await screen.findByLabelText("Name");
  expect(nameField).toHaveProperty("value", "clip.mp4");
  await userEvent.clear(nameField);
  await userEvent.type(nameField, "Clip");
  await userEvent.click(screen.getByRole("button", { name: /^upload$/i }));

  await waitFor(() => expect(uploadAdminFile).toHaveBeenCalled());
  const [name, , isPublic] = vi.mocked(uploadAdminFile).mock.calls[0] ?? [];
  expect(name).toBe("Clip");
  expect(isPublic).toBe(true);
  await waitFor(() =>
    expect(screen.getByRole("textbox")).toHaveProperty(
      "value",
      "[Clip](/api/v1/file/f1/view#clip.mp4)",
    ),
  );
});
