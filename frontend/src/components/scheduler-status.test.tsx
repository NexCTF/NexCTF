import { expect, it } from "vitest";
import type { SchedulerJob } from "@/lib/api";
import { jobStatus } from "./scheduler-status";

function job(overrides: Partial<SchedulerJob>): SchedulerJob {
  return {
    id: "1",
    name: "job",
    job_type: "send_notification",
    is_active: true,
    scheduled_at: "2026-08-22T00:00:00Z",
    cron_expression: null,
    params: {},
    last_run: null,
    created_at: "2026-08-22T00:00:00Z",
    created_by_id: "u1",
    ...overrides,
  };
}

it("marks an armed job as scheduled whether or not it has already run", () => {
  expect(jobStatus(job({}))).toBe("scheduled");
  expect(jobStatus(job({ cron_expression: "0 0 * * *", last_run: "2026-08-21T00:00:00Z" }))).toBe(
    "scheduled",
  );
});

it("marks a spent one-shot job as completed", () => {
  expect(jobStatus(job({ is_active: false, last_run: "2026-08-21T00:00:00Z" }))).toBe("completed");
});

it("marks a switched-off recurring job as disabled, not completed", () => {
  expect(
    jobStatus(
      job({ is_active: false, cron_expression: "0 0 * * *", last_run: "2026-08-21T00:00:00Z" }),
    ),
  ).toBe("disabled");
});

it("marks a never-run inactive job as disabled", () => {
  expect(jobStatus(job({ is_active: false }))).toBe("disabled");
});
