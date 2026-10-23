import { readFile } from "node:fs/promises";
import path from "node:path";
import { type APIRequestContext, expect } from "@playwright/test";
import { adminApi } from "../e2e/support/api";
import { ADMIN_ID, MISC_WARMUP_ID } from "./support";

const README = path.resolve(import.meta.dirname, "../../README.md");

type Payload = Parameters<APIRequestContext["post"]>[1];

/** POST `payload` to the admin API and return the created object. */
async function create(admin: APIRequestContext, url: string, payload: Payload) {
  const res = await admin.post(url, payload);
  if (!res.ok()) {
    throw new Error(
      `seeding ${url} failed (${res.status()}): ${await res.text()}\n` +
        "Run `task dev:screenshots`, which starts from a fresh fixture database.",
    );
  }
  return (await res.json()).data;
}

/** A job that has run once, so its page shows an execution history. */
async function seedJobWithHistory(admin: APIRequestContext): Promise<void> {
  const job = await create(admin, "admin/scheduler/jobs", {
    data: {
      name: "Close Misc Warmup",
      job_type: "toggle_challenge",
      cron_expression: "0 18 * * *",
      is_active: false,
      // Misc Warmup is already closed, so the run leaves the other screenshots untouched.
      params: { challenge_id: MISC_WARMUP_ID, make_active: false },
    },
  });
  // A second run right after would be skipped, deduplicated against this one.
  await create(admin, `admin/scheduler/jobs/${job.id}/run`, {});
  await expect
    .poll(
      async () => {
        const res = await admin.get(`admin/scheduler/jobs/${job.id}/tasks`);
        return (await res.json()).data[0]?.status;
      },
      { message: "the worker never ran the job", timeout: 30_000 },
    )
    .toBe("success");
}

/** What the development fixtures lack for the documentation screenshots. */
export default async function seed(): Promise<void> {
  const admin = await adminApi();
  try {
    await create(admin, "admin/file", {
      multipart: {
        name: "README.md",
        upload: { name: "README.md", mimeType: "text/markdown", buffer: await readFile(README) },
      },
    });
    await create(admin, "admin/link", {
      data: { name: "GitHub", url: "https://github.com/NexCTF", visibility: "public" },
    });
    await create(admin, "admin/page", {
      data: { title: "Rules", slug: "rules", is_published: true, nav_placement: "nav" },
    });
    await create(admin, "admin/notification", {
      data: {
        title: "New challenge available",
        content: "Security Quiz is now open.",
        is_broadcast: true,
        created_by_id: ADMIN_ID,
      },
    });
    await create(admin, "admin/scheduler/jobs", {
      data: {
        name: "Open Misc Warmup",
        job_type: "toggle_challenge",
        // Far ahead, so the worker leaves it scheduled.
        scheduled_at: "2030-06-01T16:00:00Z",
        params: { challenge_id: MISC_WARMUP_ID, make_active: true },
      },
    });
    await seedJobWithHistory(admin);
  } finally {
    await admin.dispose();
  }
}
