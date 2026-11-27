import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { getAdminFiles } from "@/lib/api";
import { paginated, storedFile } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";
import { AttachedFiles } from "./attached-files";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminFiles: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }));

const A = storedFile({ id: "a", name: "a.zip" });
const B = storedFile({
  id: "b",
  name: "b.zip",
  usages: [{ kind: "question", target_id: "q", label: "Other / Q1", challenge_id: "c2" }],
});

function renderAttached(onSave: (ids: string[]) => Promise<unknown>) {
  renderWithQuery(<AttachedFiles title="Files" files={[A]} onSave={onSave} />);
}

beforeEach(() => {
  vi.mocked(getAdminFiles).mockResolvedValue(paginated([A, B]));
});

it("starts from the attached files and saves the new selection", async () => {
  const onSave = vi.fn().mockResolvedValue(undefined);
  renderAttached(onSave);

  await userEvent.click(screen.getByRole("button", { name: "Manage files" }));
  expect(await screen.findByRole("checkbox", { name: "a.zip" })).toHaveProperty("checked", true);
  await userEvent.click(screen.getByRole("checkbox", { name: "b.zip" }));
  await userEvent.click(screen.getByRole("button", { name: "Attach 2 file(s)" }));

  await waitFor(() => expect(onSave).toHaveBeenCalledWith(["a", "b"]));
});

it("shows where a listed file is already used", async () => {
  renderAttached(vi.fn());

  await userEvent.click(screen.getByRole("button", { name: "Manage files" }));

  expect((await screen.findByTitle("Question file: Other / Q1")).textContent).toBe("1");
});

it("detaches one file", async () => {
  const onSave = vi.fn().mockResolvedValue(undefined);
  renderAttached(onSave);

  await userEvent.click(screen.getByRole("button", { name: "Detach a.zip" }));

  await waitFor(() => expect(onSave).toHaveBeenCalledWith([]));
});
