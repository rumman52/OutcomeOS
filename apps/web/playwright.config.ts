import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://localhost:4173" },
  webServer: [
    {
      command:
        "APP_ENV=test PERSISTENCE_BACKEND=json_sandbox DEMO_AUTH_ENABLED=true MOCK_INTEGRATIONS_ENABLED=true OUTCOMEOS_DEMO_DB=/tmp/outcomeos-playwright-demo.json uv run --project ../api uvicorn outcomeos_api.main:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/healthz",
      reuseExistingServer: false,
    },
    {
      command:
        "APP_ENV=test DEMO_AUTH_ENABLED=true MOCK_INTEGRATIONS_ENABLED=true NEXT_PUBLIC_API_ORIGIN=http://127.0.0.1:8000 pnpm dev --hostname localhost --port 4173",
      url: "http://localhost:4173/login",
      reuseExistingServer: false,
    },
  ],
});
