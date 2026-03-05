import { test, expect } from '@playwright/test';

test.describe('Alti.Analytics Sentient UI - End-to-End Tests', () => {

    test('Dashboard loads the Universal Actuation UI Hook', async ({ page }) => {
        // Navigate to the Next.js app
        await page.goto('/');

        // Assert the main header is visible
        await expect(page.locator('h1', { hasText: 'Alti.Analytics Engine' })).toBeVisible();

        // Assert the Autonomous Actuation Alert Banner is present (mocked logic)
        const alertBanner = page.locator('div', { hasText: 'Autonomous Actuation Executed' });
        await expect(alertBanner).toBeVisible();
        await expect(page.locator('button', { hasText: 'Review Action' })).toBeVisible();
    });

    test('Generative UI Stream responds to Anomaly Simulation', async ({ page }) => {
        await page.goto('/');

        // Find the generative input context box
        const inputLocator = page.locator('input[placeholder="Simulate an anomaly..."]');
        await expect(inputLocator).toBeVisible();

        // Simulate inputting a logistics anomaly
        await inputLocator.fill('Simulate a sudden spike in East Coast shipping latency.');

        // Press Enter to submit
        await page.keyboard.press('Enter');

        // Due to the asynchronous streaming nature of `ai/rsc`, we wait for the mocked
        // response context to appear within the user interface

        // Assert the user's input appeared in the chat window
        await expect(page.locator('div', { hasText: 'Simulate a sudden spike in East Coast shipping latency.' }).first()).toBeVisible();

        // In a full E2E setup with the real Swarm API mocked/running, we would assert 
        // the presence of the exact generative Server Component rendered by the Swarm
        // e.g., await expect(page.locator('[data-testid="framer-supply-chain-map"]')).toBeVisible();
    });

});
