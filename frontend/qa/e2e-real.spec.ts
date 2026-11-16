import { expect, test, type Page } from '@playwright/test'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { gunzipSync } from 'node:zlib'

// Pruebas de punta a punta contra el backend REAL (QA_MODO=real, backend en http://localhost:8000).
//   1. El sensor CRUDO de la AE4 (Rionegro 2024) subido como CSV debe dar el mismo factor que el
//      pipeline de la AE4: ERA5 0,9103, NASA 0,9809, diferencia ERA5–NASA +7,76 %.
//   2. Estados de error: servidor apagado, pedido rechazado por la API y etapa con error.
// Capturas en ../qa/capturas/.

const AQUI = path.dirname(fileURLToPath(import.meta.url))
const SALIDA = path.resolve(AQUI, '../../qa/capturas')
const CSV_AE4 = path.resolve(AQUI, '../../datos/prueba/sensor_rionegro_2024_CRUDO.csv.gz')

/** Instantánea HTML para el detector de Impeccable (no se versiona: qa/instantaneas/ está en .gitignore). */
async function instantanea(page: Page, nombre: string) {
  const dir = path.resolve(SALIDA, '../instantaneas')
  await mkdir(dir, { recursive: true })
  await writeFile(`${dir}/${nombre}.html`, await page.content(), 'utf8')
}

test.skip(process.env.QA_MODO !== 'real', 'Solo contra el backend real (QA_MODO=real).')

async function fijarPunto(page: Page, lat: string, lon: string) {
  const campoLat = page.getByLabel('Latitud')
  const campoLon = page.getByLabel('Longitud')
  await campoLat.fill(lat)
  await campoLat.press('Enter')
  await campoLon.fill(lon)
  await campoLon.press('Enter')
}

test('el sensor de la AE4 da el factor de la AE4 (0,9103)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await fijarPunto(page, '6,147148', '-75,377316')
  await page.getByRole('radio', { name: '2024' }).check()

  await page.getByLabel('Subir el CSV de mi sensor').check()
  const csv = gunzipSync(await readFile(CSV_AE4))
  await page.locator('input[type="file"]').setInputFiles({ name: 'sensor_rionegro_2024_CRUDO.csv', mimeType: 'text/csv', buffer: csv })
  await expect(page.locator('.subida')).toBeVisible({ timeout: 120_000 })
  await expect(page.locator('.subida')).toContainText('2024')

  await page.getByLabel(/régimen bimodal/).check()
  await page.getByRole('button', { name: 'Calcular el factor' }).click()
  const informe = page.locator('.informe')
  await expect(informe).toBeVisible({ timeout: 180_000 })
  await page.waitForTimeout(1500) // el número del factor se asienta

  // Cifras de la AE4 (ae4/pipeline/salidas/factores.csv y consistencia ERA5–NASA).
  await expect(page.locator('.hallazgo__numero')).toHaveAttribute('aria-label', 'Factor 0,9103')
  await expect(page.locator('.hallazgo__numero')).toHaveText('0,9103')
  await expect(informe).toContainText('el factor sería 0,9809')
  await expect(informe).toContainText('+7,76 %')
  await expect(informe).toContainText('Correlación 0,947')

  // Fig. 1: un punto por mes con dato, unidos por una línea; sin tallos verticales.
  const fig1 = page.locator('#fig-factor-t').locator('xpath=..')
  expect(await fig1.locator('circle.punto-mes').count()).toBe(12)
  expect(await fig1.locator('.tallo').count()).toBe(0)

  // Datos subidos: se rotulan como del usuario, nunca como medición real ni como SIMULADO.
  await expect(page.locator('.simulado--usuario')).toContainText('Datos del usuario')
  await expect(page.locator('.informe__meta')).toContainText('datos subidos por el usuario')
  await expect(informe).not.toContainText('MEDIDO')
  await expect(informe).not.toContainText('sensor real,')

  // Ninguna cifra con punto decimal en el texto visible del informe (la UI usa coma decimal).
  const texto = await informe.innerText()
  const conPunto = texto.match(/\b\d+\.\d+\b/g) ?? []
  expect(conPunto, `cifras con punto decimal: ${conPunto.join(', ')}`).toEqual([])

  await page.screenshot({ path: `${SALIDA}/real-07-csv-ae4-1440.png`, fullPage: true })
  await instantanea(page, 'real-csv-ae4')
  await page.locator('.hallazgo').screenshot({ path: `${SALIDA}/real-07-csv-ae4-hallazgo-1440.png` })
})

// Solo las llamadas a la API (en desarrollo Vite también sirve /src/api/*.ts, que no deben tocarse).
const esApi = (url: URL) => url.pathname.startsWith('/api/')
const esCrearAnalisis = (url: URL) => url.pathname === '/api/analisis'

const ANCHOS = [
  { nombre: '1440', width: 1440, height: 900 },
  { nombre: '390', width: 390, height: 844 },
]

for (const v of ANCHOS) {
  test(`estados de error a ${v.nombre}px`, async ({ page }) => {
    await page.setViewportSize({ width: v.width, height: v.height })

    // (a) Servidor apagado: ninguna llamada a /api responde.
    await page.route(esApi, (r) => r.abort('connectionrefused'))
    await page.goto('/')
    const franja = page.locator('.sin-servidor')
    await expect(franja).toContainText('La app no encuentra su servidor')
    await page.screenshot({ path: `${SALIDA}/real-08-sin-servidor-${v.nombre}.png` })
    await page.getByRole('button', { name: 'Calcular el factor' }).click()
    const detenido = page.locator('.detenido')
    await expect(detenido).toContainText('No hay conexión con el servidor')
    await page.locator('.progreso').screenshot({ path: `${SALIDA}/real-08-sin-servidor-detenido-${v.nombre}.png` })
    // Al volver el servidor, "Reintentar la conexión" quita la franja.
    await page.unroute(esApi)
    await page.getByRole('button', { name: 'Reintentar la conexión' }).click()
    await expect(franja).toBeHidden({ timeout: 15_000 })

    // (b) La API rechaza el pedido con {"detail": {"mensaje": ...}}.
    await page.getByLabel('Usar un ejemplo listo').check()
    await page.getByRole('button', { name: /Rionegro/ }).click()
    await page.route(esCrearAnalisis, (r) =>
      r.request().method() === 'POST'
        ? r.fulfill({
            status: 400,
            contentType: 'application/json',
            body: JSON.stringify({ detail: { mensaje: 'El sensor tiene datos de 2024 y se pidió el año 2025.' } }),
          })
        : r.continue(),
    )
    await page.getByRole('button', { name: 'Calcular el factor' }).click()
    await expect(detenido).toContainText('El servidor no aceptó el pedido')
    await expect(detenido).toContainText('se pidió el año 2025')
    await page.locator('.progreso').screenshot({ path: `${SALIDA}/real-09-pedido-rechazado-${v.nombre}.png` })
    await page.unroute(esCrearAnalisis)

    // (c) Una etapa termina con error (NASA POWER caído), como lo informa el backend.
    let fallar = true
    await page.route((u) => u.pathname.startsWith('/api/analisis/'), async (r) => {
      if (!fallar || r.request().method() !== 'GET') return r.continue()
      const real = await (await r.fetch()).json()
      const etapas = real.etapas.map((e: { paso: string }) =>
        e.paso === 'era5'
          ? { ...e, estado: 'listo', detalle: '8 784 horas (caché); celda ERA5 6,10; -75,40' }
          : e.paso === 'nasa'
            ? { ...e, estado: 'error', detalle: 'NASA POWER no respondió después de 3 intentos (HTTP 503).' }
            : { ...e, estado: 'pendiente', detalle: '' },
      )
      await r.fulfill({
        json: { ...real, estado: 'error', resultado: null, etapas, error: 'NASA POWER no respondió después de 3 intentos (HTTP 503).' },
      })
    })
    await page.getByRole('button', { name: 'Reintentar', exact: true }).click()
    await expect(detenido).toContainText('El análisis se detuvo en «Extraer NASA POWER')
    await page.locator('.progreso').screenshot({ path: `${SALIDA}/real-10-etapa-con-error-${v.nombre}.png` })
    if (v.nombre === '1440') await instantanea(page, 'real-etapa-con-error')

    // Reintentar con la fuente de vuelta termina el informe sin volver a llenar nada.
    fallar = false
    await page.getByRole('button', { name: 'Reintentar', exact: true }).click()
    await expect(page.locator('.informe')).toBeVisible({ timeout: 120_000 })
    await expect(detenido).toBeHidden()
  })
}
