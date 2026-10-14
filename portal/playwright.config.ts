import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  use: { baseURL: 'http://localhost:5174', browserName: 'chromium' },
  webServer: {
    command: 'npx vite --host localhost --port 5174 --strictPort',
    url: 'http://localhost:5174',
    reuseExistingServer: false,
    env: {
      VITE_COGNITO_POOL_ID: 'ap-south-1_TestPool',
      VITE_COGNITO_CLIENT_ID: 'testclient12345678',
      VITE_COGNITO_DOMAIN: 'https://sahayak-test.auth.ap-south-1.amazoncognito.com',
      VITE_PORTAL_ORIGIN: 'http://localhost:5174',
    },
  },
});
