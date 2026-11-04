import { defineConfig, devices } from "@playwright/test";
const existingServer = process.env.OAK_TEST_URL ?? process.env.OAK_BASE_URL;
const fixtureOrigin = "http://127.0.0.1:8502";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  timeout: 45000,
  reporter: "list",
  use: {
    baseURL: existingServer ?? fixtureOrigin,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: existingServer
    ? undefined
    : {
        command:
          "../.venv/bin/python ../scripts/serve_observer_fixture.py --port 8502",
        url: `${fixtureOrigin}/api/v1/workspace`,
        reuseExistingServer: false,
        timeout: 30000,
        gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
      },
});
