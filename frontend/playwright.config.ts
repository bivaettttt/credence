import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "e2e",
  workers: 1,
  use: {
    baseURL: process.env.CREDENCE_URL ?? "http://127.0.0.1:8111",
    viewport: { width: 1440, height: 950 },
    video: process.env.CREDENCE_VIDEO ? "on" : "off",
  },
});
