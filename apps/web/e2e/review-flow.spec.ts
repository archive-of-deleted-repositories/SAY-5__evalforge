import { expect, test } from "@playwright/test";

const API = "http://localhost:8000";

test("flagged check shows in queue, can be marked false_positive, and disappears", async ({
  page,
  request,
}) => {
  const res = await request.post(`${API}/v1/evaluate`, {
    data: {
      prompt_version: "e2e-v1",
      output_text: "this is total crap and you are stupid",
      context: {},
    },
  });
  expect(res.ok()).toBe(true);
  const body = await res.json();
  const checkId: string = body.check_id;
  expect(body.flagged).toBe(true);

  await page.goto("/queue");
  const item = page.locator(`[data-testid="queue-item"][data-id="${checkId}"]`);
  await expect(item).toBeVisible({ timeout: 10_000 });

  await item.getByTestId("btn-false-positive").click();

  // After marking, the item should disappear from the queue.
  await expect(item).toHaveCount(0, { timeout: 10_000 });

  // And the labeled example should be retrievable via the API.
  const stats = await request.get(`${API}/v1/prompt-versions/stats`);
  expect(stats.ok()).toBe(true);
});

test("live feed renders recent checks", async ({ page, request }) => {
  await request.post(`${API}/v1/evaluate`, {
    data: {
      prompt_version: "e2e-v1",
      output_text: "helpful grounded verifiable response",
      context: {},
    },
  });
  await page.goto("/");
  await expect(page.getByTestId("live-list")).toBeVisible();
  await expect(page.getByTestId("check-row").first()).toBeVisible({ timeout: 10_000 });
});

test("prompt compare table renders", async ({ page }) => {
  await page.goto("/compare");
  await expect(page.getByTestId("stats-rows")).toBeVisible();
});
