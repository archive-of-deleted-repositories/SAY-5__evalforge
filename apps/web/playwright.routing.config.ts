import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "routing.spec.ts",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:4193" },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4193 --strictPort",
    url: "http://127.0.0.1:4193",
    reuseExistingServer: false,
  },
});
