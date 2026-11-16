import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// En desarrollo, /api va al backend FastAPI local.
// En producción, FastAPI sirve frontend/dist y la API en el mismo origen.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
