import path from "node:path";
import { defineConfig } from "vitest/config";

// ponytail: separate from vite.config.ts so the router codegen plugin stays out of tests.
// No react plugin — esbuild handles JSX from tsconfig's "jsx": "react-jsx".
export default defineConfig({
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    clearMocks: true,
    unstubGlobals: true,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
