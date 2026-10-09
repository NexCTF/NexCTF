import { expect, it } from "vitest";
import { schedulerJob } from "@/test/fixtures";
import { jobStatus } from "./scheduler-status";

it("marks an armed job as scheduled whether or not it has already run", () => {
  expect(jobStatus(schedulerJob({}))).toBe("scheduled");
  expect(
    jobStatus(schedulerJob({ cron_expression: "0 0 * * *", last_run: "2026-08-21T00:00:00Z" })),
  ).toBe("scheduled");
});

it("marks a spent one-shot job as completed", () => {
  expect(jobStatus(schedulerJob({ is_active: false, last_run: "2026-08-21T00:00:00Z" }))).toBe(
    "completed",
  );
});

it("marks a switched-off recurring job as disabled, not completed", () => {
  expect(
    jobStatus(
      schedulerJob({
        is_active: false,
        cron_expression: "0 0 * * *",
        last_run: "2026-08-21T00:00:00Z",
      }),
    ),
  ).toBe("disabled");
});

it("marks a never-run inactive job as disabled", () => {
  expect(jobStatus(schedulerJob({ is_active: false }))).toBe("disabled");
});
