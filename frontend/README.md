# Factor Solar: frontend

Vite + React + TypeScript. Interfaz en español; todas las cifras vienen de la API.

- `npm run dev`: desarrollo contra el backend (Vite reenvía `/api` a `http://localhost:8000`).
- `npm run dev:mock`: sin backend; la API se simula en el navegador (`src/api/mock.ts`) y la app lo rotula como demostración.
- `npm run build`: genera `dist/`, que FastAPI sirve en `/`.
- Capturas de QA (Playwright), con el servidor de Vite ya arrancado:
  - `npx vite --mode mock --port 5174 --host 127.0.0.1` y `npm run capturas`
  - `npx vite --port 5175 --host 127.0.0.1` (backend en marcha) y `QA_MODO=real npm run capturas`
  - Salida en `../qa/capturas/` y una instantánea HTML del informe en `../qa/instantaneas/` para el detector de Impeccable.

Contrato de la API: `src/api/tipos.ts` (reconciliado con el backend real).
