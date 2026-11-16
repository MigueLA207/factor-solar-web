import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SALIDA = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../qa/capturas')
const MODO = process.env.QA_MODO === 'real' ? 'real' : 'mock'
const ANCHOS = [
  { nombre: '1440', width: 1440, height: 900 },
  { nombre: '390', width: 390, height: 844 },
]

async function esperarMapa(page: Page) {
  await page.waitForSelector('.leaflet-tile-loaded', { timeout: 20_000 }).catch(() => {})
  await page.waitForTimeout(700)
}

const archivo = (n: string, ancho: string) => `${SALIDA}/${MODO}-${n}-${ancho}.png`

for (const v of ANCHOS) {
  test(`flujo completo (${MODO}) a ${v.nombre}px`, async ({ page }) => {
    await page.setViewportSize({ width: v.width, height: v.height })
    await page.goto('/')
    await esperarMapa(page)
    await page.screenshot({ path: archivo('01-inicio', v.nombre), fullPage: true })

    // Paso del sensor: ejemplos listos (en modo real, Rionegro ya está en caché)
    await page.getByLabel('Usar un ejemplo listo').check()
    await page.getByRole('button', { name: /Rionegro/ }).click()
    await page.waitForTimeout(1600) // vuelo del mapa
    await esperarMapa(page)
    await page.screenshot({ path: archivo('02-sensor', v.nombre), fullPage: true })

    // Ejecutar con régimen bimodal
    await page.getByLabel(/régimen bimodal/).check()
    await page.getByRole('button', { name: 'Calcular el factor' }).click()
    await expect(page.locator('.paso[data-estado="listo"]').first()).toBeVisible({ timeout: 60_000 })
    await page.screenshot({ path: archivo('03-progreso', v.nombre) })

    await expect(page.locator('.informe')).toBeVisible({ timeout: 120_000 })
    await page.waitForTimeout(1800) // dibujo de líneas y asentado del número
    await page.screenshot({ path: archivo('04-resultados', v.nombre), fullPage: true })
    // Instantánea HTML del informe para el detector de Impeccable (el detector no puede llegar solo a este estado).
    if (v.nombre === '1440') {
      const { writeFile, mkdir } = await import('node:fs/promises')
      const dir = path.resolve(SALIDA, '../instantaneas')
      await mkdir(dir, { recursive: true })
      await writeFile(`${dir}/${MODO}-resultados.html`, await page.content(), 'utf8')
    }

    // Detalles a tamaño real para revisar tipografía y gráficas.
    const detalles: [string, string][] = [
      ['simulado', '.simulado'],
      ['hallazgo', '.hallazgo'],
      ['validacion', '.validacion'],
      ['figuras', '.figuras'],
      ['anexos', '.anexos'],
    ]
    for (const [nombre, sel] of detalles) {
      const el = page.locator(sel)
      if (await el.count()) await el.first().screenshot({ path: archivo(`05-${nombre}`, v.nombre) })
    }
    // Lectura al pasar el puntero sobre el día típico
    const dia = page.locator('#fig-dia-t').locator('xpath=..').locator('svg[role="img"]').first()
    const caja = await dia.boundingBox()
    if (caja) {
      await page.mouse.move(caja.x + caja.width * 0.5, caja.y + caja.height * 0.5)
      await page.waitForTimeout(200)
      await page.locator('#fig-dia-t').locator('xpath=..').screenshot({ path: archivo('06-lectura', v.nombre) })
    }
  })
}
