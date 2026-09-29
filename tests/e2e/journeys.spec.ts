import { test, expect } from '@playwright/test';
import addressesFixture from '../fixtures/addresses.json';

test.describe('5G Home Internet Availability & Arbitrage Engine — E2E User Journeys', () => {
  test.beforeEach(async ({ page }) => {
    // Intercept default suggestions and geocoding to prevent external network calls
    await page.route('**/api/geocode/suggest*', async (route) => {
      const url = new URL(route.request().url());
      const query = (url.searchParams.get('q') || '').toLowerCase();

      if (query.includes('350 5th') || query.includes('urban') || query.includes('10118')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(addressesFixture.urban.suggestions),
        });
      } else if (query.includes('oak') || query.includes('suburban') || query.includes('60540')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(addressesFixture.suburban.suggestions),
        });
      } else if (query.includes('route 1') || query.includes('rural') || query.includes('83113')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(addressesFixture.rural.suggestions),
        });
      }

      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });
  });

  test('Journey 1: Urban Multi-Provider — Full multi-brand comparison, filtering & sorting', async ({ page }) => {
    // Intercept availability API for urban address
    await page.route('**/api/availability*', async (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(addressesFixture.urban.availability),
      });
    });

    await page.goto('/');

    // 1. Intake & Autocomplete
    const searchInput = page.getByRole('textbox', { name: /address|search/i })
      .or(page.locator('input[type="text"]'));
    await expect(searchInput).toBeVisible();
    await searchInput.fill('350 5th Ave, New York, NY 10118');

    // Submit search
    const submitBtn = page.getByRole('button', { name: /check|search|find/i });
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
    } else {
      await searchInput.press('Enter');
    }

    // 2. Results Verification: 6 distinct brand cards rendered
    const providerCards = page.locator('[data-testid="provider-card"]')
      .or(page.locator('.provider-card'));
    await expect(providerCards.first()).toBeVisible({ timeout: 10000 });

    // Verify all 6 brands exist in the DOM
    await expect(page.getByText('T-Mobile 5G Home Internet', { exact: false })).toBeVisible();
    await expect(page.getByText('Metro by T-Mobile', { exact: false })).toBeVisible();
    await expect(page.getByText('Verizon 5G Home', { exact: false })).toBeVisible();
    await expect(page.getByText('Straight Talk Home Internet', { exact: false })).toBeVisible();
    await expect(page.getByText('Total Wireless Home Internet', { exact: false })).toBeVisible();
    await expect(page.getByText('AT&T Internet Air', { exact: false })).toBeVisible();

    // 3. Network Filter Test: Filter by "T-Mobile"
    const tmobileFilter = page.getByRole('button', { name: /T-Mobile/i })
      .or(page.locator('[data-filter="T-Mobile"]'));
    if (await tmobileFilter.isVisible()) {
      await tmobileFilter.click();
      // Only T-Mobile and Metro should be visible
      await expect(page.getByText('T-Mobile 5G Home Internet', { exact: false })).toBeVisible();
      await expect(page.getByText('Metro by T-Mobile', { exact: false })).toBeVisible();
      await expect(page.getByText('Verizon 5G Home', { exact: false })).not.toBeVisible();
      await expect(page.getByText('AT&T Internet Air', { exact: false })).not.toBeVisible();

      // Reset filter to All
      const allFilter = page.getByRole('button', { name: /All/i })
        .or(page.locator('[data-filter="All"]'));
      if (await allFilter.isVisible()) {
        await allFilter.click();
      }
    }

    // 4. Outbound Signup Link Test
    const signupLinks = page.locator('a[href*="http"]')
      .filter({ hasText: /Get Plan|Order Now|Sign Up|Check Out/i });
    if (await signupLinks.count() > 0) {
      const firstLink = signupLinks.first();
      await expect(firstLink).toHaveAttribute('target', '_blank');
      await expect(firstLink).toHaveAttribute('rel', /noopener/i);
    }
  });

  test('Journey 2: Suburban Single-Carrier — Single MNO footprint disambiguation', async ({ page }) => {
    // Intercept availability API for suburban address
    await page.route('**/api/availability*', async (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(addressesFixture.suburban.availability),
      });
    });

    await page.goto('/');

    const searchInput = page.getByRole('textbox', { name: /address|search/i })
      .or(page.locator('input[type="text"]'));
    await searchInput.fill('456 Oak Rd, Naperville, IL 60540');

    const submitBtn = page.getByRole('button', { name: /check|search|find/i });
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
    } else {
      await searchInput.press('Enter');
    }

    // Exactly T-Mobile and Metro should be displayed
    await expect(page.getByText('T-Mobile 5G Home Internet', { exact: false })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Metro by T-Mobile', { exact: false })).toBeVisible();

    // Competing carriers should NOT be displayed
    await expect(page.getByText('Verizon 5G Home', { exact: false })).not.toBeVisible();
    await expect(page.getByText('AT&T Internet Air', { exact: false })).not.toBeVisible();
  });

  test('Journey 3: Rural Satellite-Only — Unserved location Starlink fallback & badge', async ({ page }) => {
    // Intercept availability API for rural address
    await page.route('**/api/availability*', async (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(addressesFixture.rural.availability),
      });
    });

    await page.goto('/');

    const searchInput = page.getByRole('textbox', { name: /address|search/i })
      .or(page.locator('input[type="text"]'));
    await searchInput.fill('Route 1 Box 42, Big Piney, WY 83113');

    const submitBtn = page.getByRole('button', { name: /check|search|find/i });
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
    } else {
      await searchInput.press('Enter');
    }

    // 1. Fallback Notice Banner should appear
    const fallbackBanner = page.getByText(/No terrestrial 5G Home Internet available/i)
      .or(page.locator('[data-testid="satellite-fallback-banner"]'));
    await expect(fallbackBanner).toBeVisible({ timeout: 10000 });

    // 2. Starlink card should be displayed
    await expect(page.getByText('Starlink', { exact: false })).toBeVisible();

    // 3. Equipment fee disclosure ($599) should be explicit
    await expect(page.getByText(/599/i)).toBeVisible();
  });

  test('Journey 4: Invalid Address Error Handling & PO Box Rejection', async ({ page }) => {
    // Route 404/400 for nonexistent address
    await page.route('**/api/availability*99999*', async (route) => {
      return route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify(addressesFixture.invalid.nonexistent.availability),
      });
    });

    await page.goto('/');

    const searchInput = page.getByRole('textbox', { name: /address|search/i })
      .or(page.locator('input[type="text"]'));
    const submitBtn = page.getByRole('button', { name: /check|search|find/i });

    // Scenario A: Blank submission validation
    await searchInput.fill('   ');
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
    } else {
      await searchInput.press('Enter');
    }

    // Should indicate address is required
    const errorMsg = page.getByText(/enter a valid|required|cannot be blank/i)
      .or(page.locator('[data-testid="search-error"]'));
    await expect(errorMsg).toBeVisible();

    // Scenario B: PO Box Rejection
    await searchInput.fill('PO Box 1234, Dallas, TX 75201');
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
    } else {
      await searchInput.press('Enter');
    }

    const poBoxWarning = page.getByText(/PO Box|physical residential street address/i);
    await expect(poBoxWarning).toBeVisible();

    // Scenario C: Nonexistent Address
    await searchInput.fill('99999 Nonexistent Blvd, Nowhere, ZZ 00000');
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
    } else {
      await searchInput.press('Enter');
    }

    const notFoundMsg = page.getByText(/couldn't locate this address|not found/i);
    await expect(notFoundMsg).toBeVisible();
  });
});
