import { readFileSync } from "node:fs";
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const DEV_NONCE = "nexctf-dev";
const SECURITY_HEADERS = path.resolve(import.meta.dirname, "../docker/security-headers.caddy");

/** The production CSP from the Caddy snippet, plus what only the dev server needs. */
function devContentSecurityPolicy(): string {
  const snippet = readFileSync(SECURITY_HEADERS, "utf8");
  const policy = /Content-Security-Policy "([^"]+)"/.exec(snippet)?.[1];
  if (!policy) throw new Error("docker/security-headers.caddy sets no Content-Security-Policy");
  const directives = new Map(
    policy.split(";").map((directive) => {
      const [name, ...sources] = directive.trim().split(/\s+/);
      return [name, sources];
    }),
  );
  const extend = (name: string, source: string) => {
    const sources = directives.get(name);
    if (!sources) throw new Error(`the CSP has no ${name} directive to extend`);
    sources.push(source);
  };
  extend("script-src", `'nonce-${DEV_NONCE}'`);
  if (process.env.S3_PUBLIC_URL) extend("img-src", new URL(process.env.S3_PUBLIC_URL).origin);
  return Array.from(directives, ([name, sources]) => [name, ...sources].join(" ")).join("; ");
}

/** Restarts the dev server when the Caddy snippet changes, so its CSP stays current. */
function watchSecurityHeaders(): Plugin {
  return {
    name: "nexctf:watch-security-headers",
    configureServer(server) {
      server.watcher.add(SECURITY_HEADERS);
      server.watcher.on("change", (file) => {
        if (file === SECURITY_HEADERS) void server.restart();
      });
    },
  };
}

export default defineConfig(({ command }) => ({
  plugins: [
    TanStackRouterVite({ routeFileIgnorePattern: "\\.test\\.tsx?$" }),
    react(),
    tailwindcss(),
    watchSecurityHeaders(),
  ],
  // Stamps the React refresh preamble, the dev server's only inline script.
  html: command === "serve" ? { cspNonce: DEV_NONCE } : {},
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "src"),
    },
  },
  server: {
    // Report-Only, so a violation shows in the console without breaking the page.
    headers:
      command === "serve"
        ? { "Content-Security-Policy-Report-Only": devContentSecurityPolicy() }
        : {},
    proxy: {
      // SSE endpoint — disable timeout so the long-lived connection isn't killed
      "/api/v1/stream": {
        target: "http://localhost:8000",
        changeOrigin: true,
        // xfwd sends the real client IP; pairs with TRUSTED_PROXY_COUNT=1
        xfwd: true,
        timeout: 0,
        proxyTimeout: 0,
      },
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        xfwd: true,
      },
    },
  },
}));
