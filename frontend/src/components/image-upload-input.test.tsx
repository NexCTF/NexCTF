import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { getAdminFiles, uploadAdminFile } from "@/lib/api";
import { paginated, storedFile } from "@/test/fixtures";
import { ImageUploadInput } from "./image-upload-input";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminFiles: vi.fn(),
  uploadAdminFile: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

const ID = "11111111-1111-1111-1111-111111111111";

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
  vi.mocked(getAdminFiles).mockResolvedValue(paginated([]));
  vi.mocked(uploadAdminFile).mockResolvedValue({ ...storedFile({ id: ID }), duplicates: [] });
});

it("uploads a public image and stores its stable URL", async () => {
  const onChange = vi.fn();
  renderInput("", onChange);
  const file = new File(["png"], "logo.png", { type: "image/png" });

  await userEvent.click(screen.getByRole("button", { name: "Choose" }));
  await userEvent.upload(await screen.findByTestId("file-picker-upload"), file);
  await waitFor(() => expect(uploadAdminFile).toHaveBeenCalledWith("logo.png", file, true));
  await userEvent.click(screen.getByRole("button", { name: "Use image" }));

  await waitFor(() => expect(onChange).toHaveBeenCalledWith(`/api/v1/file/${ID}/view`));
});

it("lists only images", async () => {
  renderInput("", vi.fn());

  await userEvent.click(screen.getByRole("button", { name: "Choose" }));

  await waitFor(() =>
    expect(vi.mocked(getAdminFiles).mock.calls[0]?.[0]).toContain("mime_prefix=image%2F"),
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
