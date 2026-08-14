import { expect, test } from "@playwright/test";

test("professional shell exposes current journey", async ({ context, page }) => {
  await page.goto("/login");
  expect(new URL(page.url()).origin).toBe("http://localhost:4173");
  await page.getByRole("button", { name: "Sign in to seeded demo workspace" }).click();
  await expect(page).toHaveURL("/overview");
  expect(new URL(page.url()).origin).toBe("http://localhost:4173");
  await expect
    .poll(async () =>
      (await context.cookies()).some(
        (cookie) => cookie.name === "outcomeos_session" && cookie.domain === "localhost",
      ),
    )
    .toBe(true);
  await expect(page.getByText("OutcomeOS")).toBeVisible();
  await expect(page.getByText("SANDBOX / DEMO")).toBeVisible();
  await expect(page.getByText("আপনার sage green linen set আছে? COD হবে?")).toBeVisible();
  await expect(page.getByLabel("Edit AI reply")).toContainText("COD হবে");
});
