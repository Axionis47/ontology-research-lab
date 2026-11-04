import { test, expect } from "@playwright/test";

// These tests use a running OaK API and its genuine saved artifacts. No request
// interception, mock service, or generated benchmark evidence is used.
const weatherTask = "mcp:064d950af7a04b3e823a103a6ce8c6b2";
const helsinkiRun = "998d8311b79a414993d0337a3908bbff";
test("Helsinki playback preserves graphs and separates answer from assessment", async ({
  page,
  request,
}) => {
  const runResponse = await request.get(`/api/v1/runs/${helsinkiRun}`);
  test.skip(
    runResponse.status() === 404,
    "The retained public Helsinki run is unavailable in this workspace.",
  );
  expect(runResponse.ok()).toBeTruthy();
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET") mutations.push(request.url());
  });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(
    `/inference?task=${encodeURIComponent(weatherTask)}&run=${helsinkiRun}`,
  );
  await expect(page.getByTestId("agent-answer")).toHaveText("2");
  await expect(
    page.getByText("Independent assessment", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".assessment")).toContainText("Passed");
  await expect(page.getByTestId("graph-canvas")).toHaveAttribute(
    "data-node-count",
    "4",
  );
  await expect(page.getByTestId("graph-canvas")).toHaveAttribute(
    "data-edge-count",
    "3",
  );
  await expect(page.getByTestId("graph-canvas")).toHaveAttribute(
    "data-highlight-count",
    "2",
  );
  await page.getByLabel("Highlight graph records").fill("DailyForecast");
  await expect(page.getByTestId("graph-canvas")).toHaveAttribute(
    "data-node-count",
    "4",
  );
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  await expect(page.getByLabel("Replay step")).toHaveValue("0");
  await expect(page.getByLabel("Highlight graph records")).toHaveValue("");
  await expect(page.getByTestId("graph-canvas")).toHaveAttribute(
    "data-node-count",
    "0",
  );
  await page.getByRole("button", { name: "Replay", exact: true }).click();
  await expect(page.getByLabel("Replay step")).not.toHaveValue("0");
  await page.getByRole("button", { name: "Replay", exact: true }).click();
  await page.reload();
  await expect(page.getByTestId("agent-answer")).toHaveText("2");
  await page.locator(".event-selected .evidence-links button").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page
      .getByRole("dialog")
      .locator("p")
      .filter({ hasText: /^Stored artifact / }),
  ).toBeVisible();
  if (!process.env.OAK_TEST_URL && !process.env.OAK_BASE_URL)
    await expect(
      page.getByRole("heading", { name: "Export provenance" }),
    ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(mutations).toEqual([]);
  expect(errors).toEqual([]);
});
test("weather history shows failed schema evidence and actual parent revision", async ({
  page,
  request,
}) => {
  const response = await request.get(
    `/api/v1/tasks/${encodeURIComponent(weatherTask)}/history`,
  );
  test.skip(
    response.status() === 404,
    "Local weather construction history is unavailable.",
  );
  await page.goto(`/construction?task=${encodeURIComponent(weatherTask)}`);
  await expect(page.getByText("Changes from recorded parent")).toBeVisible();
  await expect(page.getByRole("button", { name: /Parent / })).toBeVisible();
  await page
    .locator(".attempt")
    .filter({ hasText: "No kernel produced" })
    .first()
    .click();
  await expect(page.locator(".attempt-active")).toContainText("Failed");
  await expect(page.getByTestId("graph-canvas")).toHaveAttribute(
    "data-node-count",
    "3",
  );
  await expect(page.locator(".attempt-active .case-tags")).toContainText(
    "construction-07",
  );
});

test("Coffee retained graph contains 5,746 records and no invented relationships", async ({
  page,
  request,
}) => {
  const task = "corpus:6cd20839ae78451caa3fb68d77a060b7",
    run = "4406240ec1f14f8aa83578fee983696c";
  const response = await request.get(`/api/v1/runs/${run}`);
  test.skip(
    response.status() === 404,
    "Rich Coffee artifacts are local-only and unavailable here.",
  );
  expect(response.ok()).toBeTruthy();
  await page.goto(`/inference?task=${encodeURIComponent(task)}&run=${run}`);
  await expect(page.getByTestId("graph-canvas")).toHaveAttribute(
    "data-node-count",
    "80",
  );
  await expect(page.getByTestId("graph-canvas")).toHaveAttribute(
    "data-edge-count",
    "0",
  );
  await expect(page.locator(".graph-footer")).toContainText("5,746");
  await expect(page.getByTestId("agent-answer")).toBeVisible();
});

test("USGS missing capability stays unresolved without invented task assessment", async ({
  page,
  request,
}) => {
  const task = "corpus:92a95ecf291d41d9887cdaa1be74fe67",
    run = "5ab56bddb2ac4a6aa3ce1c543a7fbad3";
  const response = await request.get(`/api/v1/runs/${run}`);
  test.skip(
    response.status() === 404,
    "Rich USGS artifacts are local-only and unavailable here.",
  );
  expect(response.ok()).toBeTruthy();
  await page.goto(`/inference?task=${encodeURIComponent(task)}&run=${run}`);
  await expect(page.locator(".run-summary")).toContainText("Completed");
  await expect(page.locator(".run-summary")).toContainText("Unresolved");
  await expect(page.locator(".assessment")).toContainText("Not checked");
  await page.goto(`/construction?task=${encodeURIComponent(task)}`);
  await expect(page.locator(".attempt")).toHaveCount(4);
  await expect(page.getByText("Changes from recorded parent")).toBeVisible();
});
test("setup and observer layouts remain usable at mobile, tablet and desktop widths", async ({
  page,
}) => {
  for (const width of [390, 820, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const path of [
      "/setup",
      `/construction?task=${encodeURIComponent(weatherTask)}`,
      `/inference?task=${encodeURIComponent(weatherTask)}&run=${helsinkiRun}`,
    ]) {
      await page.goto(path);
      await expect(
        page.getByRole("navigation", { name: "Main navigation" }),
      ).toBeVisible();
      await expect(page.locator("h1")).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBeTruthy();
    }
  }
  await page.goto("/setup");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
});
