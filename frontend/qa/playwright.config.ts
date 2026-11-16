import { defineConfig } from '@playwright/test'

// Capturas de QA visual. Salida: ../qa/capturas/
//   QA_MODO=mock (por defecto): API simulada en el navegador, no necesita backend.
//   QA_MODO=real: Vite reenvía /api al backend en http://localhost:8000 (arrancarlo antes).
const real = process.env.QA_MODO === 'real'
const puerto = real ? 5175 : 5174

export default defineConfig({
  testDir: '.',
  timeout: 180_000,
  workers: 1,
  reporter: 'list',
  use: { baseURL: `http://127.0.0.1:${puerto}`, locale: 'es-CO' },
  webServer: {
    command: `npx vite ${real ? '' : '--mode mock '}--port ${puerto} --strictPort --host 127.0.0.1`,
    url: `http://127.0.0.1:${puerto}`,
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
