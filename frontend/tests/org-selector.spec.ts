import test, { expect } from "@playwright/test";

test("org selector should show all options when cleared", async ({ page }) => {
  await page.goto("/settings");

  // Wait for the org selector to be visible and have a value
  const orgSelector = page.getByTestId("org-selector");
  await expect(orgSelector).toBeVisible();
  await expect(orgSelector).not.toHaveValue("");

  // Click to open the dropdown
  await orgSelector.click();

  // Should show multiple options in the dropdown
  const listbox = page.getByRole("listbox");
  await expect(listbox).toBeVisible();
  const optionsBefore = listbox.getByRole("option");
  const countBefore = await optionsBefore.count();
  expect(countBefore).toBeGreaterThan(1);

  // Close dropdown first
  await page.keyboard.press("Escape");
  await expect(listbox).not.toBeVisible();

  // Hover to reveal clear button and click it
  await orgSelector.hover();
  const clearButton = page.locator('button[data-visible="true"]');
  await clearButton.click();

  // Click on the input to open the dropdown
  await orgSelector.click();

  // After clearing, all options should still be visible (not filtered)
  await expect(listbox).toBeVisible();
  const optionsAfter = listbox.getByRole("option");
  const countAfter = await optionsAfter.count();
  expect(countAfter).toBe(countBefore);
});
