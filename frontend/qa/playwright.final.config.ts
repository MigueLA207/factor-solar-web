import { defineConfig } from '@playwright/test'

// Revisión final: sin servidor propio; apunta al backend que sirve frontend/dist (REV_URL).
export default defineConfig({
  testDir: '.',
  testMatch: 'revision-final.spec.ts',
  timeout: 240_000,
  workers: 1,
  reporter: 'list',
  use: { locale: 'es-CO' },
})
