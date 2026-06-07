import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: "./src/index.ts",
      formats: ["iife"],
      name: "__nexctf_tmp",
      fileName: () => "bundle.js",
    },
    rollupOptions: {
      external: ["react", "react-dom", "react/jsx-runtime"],
      output: {
        globals: {
          react: "__nexctf__.React",
          "react-dom": "__nexctf__.ReactDOM",
          "react/jsx-runtime": "__nexctf__.jsxRuntime",
        },
        exports: "default",
        // Register the plugin with the host after the IIFE executes.
        footer: `typeof window.__nexctf_register__==="function"&&window.__nexctf_register__(__nexctf_tmp);`,
      },
    },
  },
});
