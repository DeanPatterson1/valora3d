import { defineConfig, devices } from "@playwright/test";

const production = process.env.E2E_PRODUCTION === "1";
const port = production ? 3100 : 3000;

export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  webServer: {
    command: production ? "npm run build && npm run start -- --port 3100" : "npm run dev",
    url: `http://localhost:${port}`,
    reuseExistingServer: false,
    timeout: 240_000,
  },
  use: {
    baseURL: `http://localhost:${port}`,
    trace: "retain-on-failure",
    launchOptions: {
      args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
