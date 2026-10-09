import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, expect, it, vi } from "vitest";
import {
  getAdminSchedulerJob,
  getAdminSchedulerJobTasks,
  getAdminSchedulerJobTypes,
  runAdminSchedulerJob,
} from "@/lib/api";
import { paginated, schedulerJob, schedulerTask } from "@/test/fixtures";
import { renderRoute } from "@/test/render";
import { Route } from "./scheduler_.$jobId";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getAdminSchedulerJob: vi.fn(),
  getAdminSchedulerJobTasks: vi.fn(),
  getAdminSchedulerJobTypes: vi.fn(),
  runAdminSchedulerJob: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getAdminSchedulerJob).mockResolvedValue(schedulerJob());
  vi.mocked(getAdminSchedulerJobTypes).mockResolvedValue([]);
  vi.mocked(getAdminSchedulerJobTasks).mockResolvedValue(paginated([]));
});

function render() {
  return renderRoute(Route, {
    path: `/admin/scheduler/${schedulerJob().id}`,
    routePath: "/admin/scheduler/$jobId",
  });
}

it("links each queued run to its job in the task queue", async () => {
  vi.mocked(getAdminSchedulerJobTasks).mockResolvedValue(
    paginated([
      schedulerTask({ status: "failed", queue_job_id: 42 }),
      schedulerTask({ id: "skipped-run", status: "skipped", queue_job_id: null }),
    ]),
  );
  render();

  const link = await screen.findByRole("link", { name: /view in task queue/i });
  expect(link.getAttribute("href")).toBe("/admin/tasks?job=42");
  const skipped = screen.getByText("skipped").closest("tr") as HTMLElement;
  expect(within(skipped).queryByRole("link")).toBeNull();
});

it.each([
  ["pending", "success", /run queued/i],
  ["skipped", "info", /already queued or running/i],
] as const)("tells the admin a %s run-now was %s", async (status, level, message) => {
  vi.mocked(runAdminSchedulerJob).mockResolvedValue(schedulerTask({ status }));
  render();

  await userEvent.click(await screen.findByRole("button", { name: /run now/i }));

  expect(toast[level]).toHaveBeenCalledWith(expect.stringMatching(message));
});
