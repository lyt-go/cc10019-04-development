import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 300_000,
  expect: { timeout: 10_000 },
  workers: 3,
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5173',
    browserName: 'chromium',
    headless: true,
    actionTimeout: 10_000,
  },
  reporter: 'line',
})
