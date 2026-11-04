import { chromium } from "@playwright/test";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const origin = process.env.OAK_TEST_URL ?? "http://127.0.0.1:8501";
const task = encodeURIComponent("mcp:064d950af7a04b3e823a103a6ce8c6b2");
const paths = {
  setup: "/setup",
  construction: `/construction?task=${task}`,
  inference: `/inference?task=${task}&run=998d8311b79a414993d0337a3908bbff`,
};
for (const [width, name] of [
  [1440, "desktop"],
  [820, "tablet"],
  [390, "mobile"],
]) {
  await page.setViewportSize({ width, height: 1000 });
  for (const [screen, path] of Object.entries(paths)) {
    await page.goto(origin + path);
    await page.waitForLoadState("networkidle");
    if (screen !== "setup")
      await page.locator('[data-testid="graph-canvas"]').waitFor();
    await page.screenshot({
      path: `/tmp/oak-${screen}-${name}.png`,
      fullPage: true,
    });
  }
}
await page.emulateMedia({ colorScheme: "dark" });
await page.setViewportSize({ width: 1440, height: 1000 });
await page.goto(origin + paths.inference);
await page.locator('[data-testid="graph-canvas"]').waitFor();
await page.screenshot({ path: "/tmp/oak-inference-dark.png", fullPage: true });
if (process.env.OAK_CAPTURE_TASK && process.env.OAK_CAPTURE_RUN) {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto(
    `${origin}/inference?task=${encodeURIComponent(process.env.OAK_CAPTURE_TASK)}&run=${encodeURIComponent(process.env.OAK_CAPTURE_RUN)}`,
  );
  await page.locator('[data-testid="agent-answer"]').waitFor();
  await page.locator('[data-testid="graph-canvas"]').waitFor();
  await page.screenshot({
    path: "/tmp/oak-inference-live.png",
    fullPage: true,
  });
}
await browser.close();
console.log(
  "Saved real API previews to /tmp/oak-{setup,construction,inference}-{desktop,tablet,mobile}.png and /tmp/oak-inference-dark.png",
);
