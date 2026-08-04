import { expect, test } from "@playwright/test";

test("professional shell exposes current journey", async ({ page }) => {
  await page.goto("/overview");
  await expect(page.getByText("OutcomeOS")).toBeVisible();
  await expect(page.getByText("SANDBOX / DEMO")).toBeVisible();
  await expect(page.getByText("আপনার sage green linen set আছে? COD হবে?")).toBeVisible();
  await expect(page.getByLabel("Edit AI reply")).toContainText("COD হবে");
});
