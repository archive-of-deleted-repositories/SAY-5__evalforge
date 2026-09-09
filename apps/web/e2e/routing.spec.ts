import { expect, test } from "@playwright/test";

test("direct routes, navigation, and browser history select the correct page", async ({ page }) => {
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin === "http://localhost:8000") {
      await route.fulfill({ json: [] });
    } else if (["http://127.0.0.1:4193", "http://localhost:5173"].includes(url.origin)) {
      await route.continue();
    } else {
      await route.abort();
    }
  });
  await page.routeWebSocket("**/v1/live", socket => socket.close());
  const failures: string[] = [];
  page.on("pageerror", error => failures.push(error.message));
  await page.goto("/queue");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Review Queue" })).toHaveAttribute("aria-current", "page");
  await page.getByRole("link", { name: "Prompt Compare" }).click();
  await expect(page).toHaveURL(/\/compare$/);
  await expect(page.getByRole("heading", { name: "Prompt Compare" })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  await page.getByRole("link", { name: "Live Feed" }).click();
  await expect(page.getByRole("heading", { name: "Live Feed" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Review Queue" })).not.toHaveAttribute("aria-current", "page");
  await page.goto("/compare");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Prompt Compare" })).toBeVisible();
  expect(failures).toEqual([]);
});
