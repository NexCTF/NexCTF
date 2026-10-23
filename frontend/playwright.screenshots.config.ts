import path from "node:path";
import { defineConfig, type PlaywrightTestConfig } from "@playwright/test";
import base from "./playwright.config";

type WebServer = Exclude<NonNullable<PlaywrightTestConfig["webServer"]>, unknown[]>;

const [backend, frontend] = base.webServer as WebServer[];

/** Its own database and cache index, which `task dev:screenshots` recreates. */
const env = { ...backend.env, POSTGRES_DB: "nexctf_screenshots", REDIS_DB: "1" };

/** Each set of captures: its specs in `screenshots/<set>/`, and where its images go. */
const SETS = {
  readme: path.resolve(import.meta.dirname, "../img"),
  docs: process.env.SCREENSHOTS_DOCS_DIR ?? path.resolve(import.meta.dirname, "docshots"),
};

/**
 * README and documentation screenshots: one capture per `shot()`, written to its
 * set's output (the documentation converts its own to WebP). Only the development
 * fixtures appear, plus what `screenshots/seed.ts` adds for the docs.
 */
export default defineConfig({
  ...base,
  globalSetup: [base.globalSetup ?? [], "./screenshots/seed.ts"].flat(),
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  webServer: [
    { ...backend, env, reuseExistingServer: false },
    // Runs the scheduler jobs the seed queues; the seed waits for them to finish.
    { command: "task dev:worker", cwd: backend.cwd, env },
    frontend,
  ],
  projects: Object.entries(SETS).map(([set, output]) => ({
    name: set,
    testDir: `./screenshots/${set}`,
    metadata: { output },
    use: {
      ...base.projects?.[0]?.use,
      viewport: { width: 1370, height: 1207 },
      colorScheme: "dark",
      // Dates and the event timezone render the same wherever the capture runs.
      timezoneId: "UTC",
      reducedMotion: "reduce",
      trace: "off",
      screenshot: "off",
    },
  })),
});
