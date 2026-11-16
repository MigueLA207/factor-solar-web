import { expect, test } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Capturas de la revisión final contra el backend real servido en REV_URL (por defecto http://127.0.0.1:8820).
const SALIDA = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../qa/revision-final')
test.skip(process.env.QA_REV !== '1', 'Solo con QA_REV=1.')

for (const [nombre, ancho] of [['1440', 1440], ['390', 390]] as const) {
  for (const ej of ['Rionegro', 'Bogotá']) {
    test(`${ej} ${nombre}`, async ({ page }) => {
      await page.setViewportSize({ width: ancho, height: 900 })
      await page.goto(process.env.REV_URL ?? 'http://127.0.0.1:8820/')
      await page.getByLabel('Usar un ejemplo listo').check()
      await page.getByRole('button', { name: new RegExp(ej) }).click()
      await page.getByLabel(/régimen bimodal/).check()
      await page.getByRole('button', { name: 'Calcular el factor' }).click()
      await expect(page.locator('.informe')).toBeVisible({ timeout: 150_000 })
      await page.waitForTimeout(2000)
      await page.screenshot({ path: `${SALIDA}/${ej.slice(0, 3).toLowerCase()}-${nombre}.png`, fullPage: true })
      for (const f of ['fig-factor', 'fig-energia', 'fig-dia', 'fig-desfase']) {
        await page.locator('figure.figura').nth(['fig-factor', 'fig-energia', 'fig-dia', 'fig-desfase'].indexOf(f)).screenshot({ path: `${SALIDA}/${ej.slice(0, 3).toLowerCase()}-${nombre}-${f}.png` })
      }
    })
  }
}
