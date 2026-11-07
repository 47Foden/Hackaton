import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5177', viewport: { width: 1024, height: 900 }, screenshot: 'only-on-failure' },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5177',
    url: 'http://127.0.0.1:5177',
    reuseExistingServer: false,
    env: { VITE_API_MODE: '', VITE_MENU_API_MODE: '', VITE_ORDER_API_MODE: '' },
  },
});
