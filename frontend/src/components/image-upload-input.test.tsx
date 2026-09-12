import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { uploadAdminFile } from "@/lib/api";
import { ImageUploadInput } from "./image-upload-input";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  uploadAdminFile: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

function renderInput(value: string, onChange: (v: string) => void) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ImageUploadInput value={value} onChange={onChange} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(uploadAdminFile).mockResolvedValue({
    id: "11111111-1111-1111-1111-111111111111",
    name: "logo.png",
    s3_key: "files/11111111-1111-1111-1111-111111111111",
    original_filename: "logo.png",
    mime_type: "image/png",
    file_size: 3,
    is_public: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  });
});

it("uploads a public file and stores its stable URL", async () => {
  const onChange = vi.fn();
  const { container } = renderInput("", onChange);
  const file = new File(["png"], "logo.png", { type: "image/png" });

  // biome-ignore lint/style/noNonNullAssertion: the hidden file input is always rendered
  await userEvent.upload(container.querySelector<HTMLInputElement>("input[type=file]")!, file);

  expect(uploadAdminFile).toHaveBeenCalledWith("logo.png", file, true);
  await waitFor(() =>
    expect(onChange).toHaveBeenCalledWith("/api/v1/file/11111111-1111-1111-1111-111111111111/view"),
  );
});

it("keeps a hand-typed URL", async () => {
  const onChange = vi.fn();
  renderInput("", onChange);

  await userEvent.type(screen.getByRole("textbox"), "h");

  expect(onChange).toHaveBeenCalledWith("h");
});

it("clears the value", async () => {
  const onChange = vi.fn();
  renderInput("https://cdn/logo.png", onChange);

  await userEvent.click(screen.getByRole("button", { name: "Clear" }));

  expect(onChange).toHaveBeenCalledWith("");
});
