import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  use: { launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {}, baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5177', viewport: { width: 1024, height: 900 }, screenshot: 'only-on-failure' },
  webServer: process.env.PLAYWRIGHT_EXTERNAL_SERVER === '1' ? undefined : {
    command: 'npm run dev -- --host 127.0.0.1 --port 5177',
    url: 'http://127.0.0.1:5177',
    reuseExistingServer: false,
    env: { VITE_API_MODE: '', VITE_MENU_API_MODE: '', VITE_ORDER_API_MODE: '' },
  },
});
