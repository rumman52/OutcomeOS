import { expect, test } from '@playwright/test'

test('core sandbox workflow', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Order reference').fill('journey-1')
  await page.getByRole('button', { name: 'Create sandbox order' }).click()
  await expect(page.getByRole('status')).toContainText('journey-1 created · pending')
})
