import { defineConfig, devices } from '@playwright/test'

/**
 * E2E frontend ↔ backend real: levanta la API FastAPI sobre SQLite
 * temporal y el dev server de Vite apuntando a ella. La evaluación usa
 * `escenario_mock` para no depender de credenciales de Experian.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5199',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command:
        '.\\.venv\\Scripts\\python.exe -m backend.database.seed_demo && .\\.venv\\Scripts\\python.exe -m uvicorn backend.main:app --port 8010',
      cwd: '..',
      url: 'http://localhost:8010/api/health',
      timeout: 60_000,
      env: {
        DATABASE_URL: 'sqlite:///./e2e_playwright.db',
        DB_CREAR_TABLAS: 'true',
        ENVIRONMENT: 'demo',
        CORS_ORIGINS: 'http://localhost:5199,http://localhost:5173',
      },
    },
    {
      command: 'npm run dev -- --port 5199 --strictPort',
      url: 'http://localhost:5199',
      timeout: 60_000,
      env: {
        VITE_API_URL: 'http://localhost:8010',
      },
    },
  ],
})
