import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const ROOT = path.resolve(import.meta.dirname, "..");
const CI = !!process.env.CI;

/**
 * End-to-end suite: drives the real frontend (Vite dev server) against the real
 * backend seeded with the development fixtures. Infra must be up
 * (`task dev:infra:up`); both servers are started unless already running.
 */
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/support/global-setup.ts",
  fullyParallel: true,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  workers: CI ? 2 : undefined,
  reporter: CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    locale: "en-US",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Lets a pre-installed Chromium stand in for `playwright install`.
        launchOptions: { executablePath: process.env.E2E_CHROMIUM_PATH || undefined },
      },
    },
  ],
  webServer: [
    {
      command: "task dev:backend",
      cwd: ROOT,
      // Run through `task dev:e2e`, the docker hostnames of .env.dev would win over the task's.
      env: { POSTGRES_SERVER: "127.0.0.1", REDIS_HOST: "127.0.0.1", S3_HOST: "127.0.0.1" },
      url: "http://localhost:8000/api/v1/info",
      reuseExistingServer: !CI,
      timeout: 180_000,
      stdout: "pipe",
    },
    {
      // CI tests the production bundle; `vite preview` reuses the dev proxy to the API.
      command: CI ? "bun run build && bunx vite preview --port 5173 --strictPort" : "bun run dev",
      url: "http://localhost:5173",
      reuseExistingServer: !CI,
      timeout: 120_000,
    },
  ],
});
