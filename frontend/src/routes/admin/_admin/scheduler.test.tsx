import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import {
  createAdminSchedulerJob,
  getAdminSchedulerCronNext,
  getAdminSchedulerJobs,
  getAdminSchedulerJobTypes,
} from "@/lib/api";
import { renderRoute } from "@/test/render";
import { Route } from "./scheduler";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminSchedulerJobs: vi.fn(),
  getAdminSchedulerJobTypes: vi.fn(),
  createAdminSchedulerJob: vi.fn(),
  getAdminSchedulerCronNext: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

beforeEach(() => {
  vi.mocked(getAdminSchedulerJobs).mockResolvedValue({
    data: [],
    pagination: { total_count: 0, page: 1, per_page: 25, total_pages: 0 },
    // biome-ignore lint/suspicious/noExplicitAny: only the fields DataTable reads
  } as any);
  vi.mocked(getAdminSchedulerJobTypes).mockResolvedValue([
    { type_name: "send_notification", create_schema: {}, update_schema: {} },
    // biome-ignore lint/suspicious/noExplicitAny: schema shape is irrelevant here
  ] as any);
  vi.mocked(createAdminSchedulerJob).mockResolvedValue({} as never);
  vi.mocked(getAdminSchedulerCronNext).mockResolvedValue({
    timezone: "Europe/Paris",
    next_runs: ["2026-08-23T00:00:00Z"],
  });
});

async function openDialog() {
  renderRoute(Route, { path: "/admin/scheduler" });
  await userEvent.click(await screen.findByRole("button", { name: /new job/i }));
  return screen.findByRole("dialog");
}

it("shows the job-type placeholder before a type is picked", async () => {
  const dialog = await openDialog();
  expect(dialog.textContent).toMatch(/select a job type/i);
});

it("keeps the job-type label bound to the select trigger", async () => {
  await openDialog();
  // Orphaned labels are the usual regression when swapping a native select out.
  expect(screen.getByLabelText(/job type/i)).toBeTruthy();
});

it("submits a cron-only job with no explicit date", async () => {
  const dialog = await openDialog();

  await userEvent.type(screen.getByLabelText(/^name$/i), "nightly");
  await userEvent.click(screen.getByLabelText(/job type/i));
  await userEvent.click(await screen.findByRole("option", { name: "send_notification" }));
  await userEvent.type(screen.getByLabelText(/repeat \(cron/i), "0 0 * * *");

  const save = within(dialog).getByRole("button", { name: /^save$/i }) as HTMLButtonElement;
  await waitFor(() => expect(save.disabled).toBe(false));
  await userEvent.click(save);

  await waitFor(() => expect(createAdminSchedulerJob).toHaveBeenCalled());
  expect(vi.mocked(createAdminSchedulerJob).mock.calls[0][0]).toMatchObject({
    cron_expression: "0 0 * * *",
    scheduled_at: undefined,
  });
});
