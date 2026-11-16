import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { EstadoAnalisis, Resultado } from '../src/api/tipos'
import { resultadoDemo } from '../src/api/mock'

// Honestidad del informe (revisión W4): el informe se arma con una respuesta de /api/analisis fabricada
// (la forma de la API, cifras de prueba) para forzar los casos que el cálculo real rara vez produce:
// factor mayor que 1, nulos, sensor simulado, año parcial, reloj del CSV corrido.
// El backend real solo aporta /api/salud y /api/ejemplos (QA_MODO=real, backend en :8000).
const SALIDA = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../qa/capturas')

test.skip(process.env.QA_MODO !== 'real', 'Solo contra el backend real (QA_MODO=real).')

const ID = 'an-0123456789'

function base(): Resultado {
  const r = resultadoDemo({ lat: 6.147, lon: -75.377, anio: 2024, sensor_id: 'x' }, ID)
  r.sitio.nombre = 'Sitio de prueba'
  return r
}

/** Informe con el análisis interceptado: no toca el cálculo real. */
async function verInforme(page: Page, r: Resultado, ancho = 1440) {
  await page.setViewportSize({ width: ancho, height: 900 })
  await page.route((u) => u.pathname === '/api/analisis', (ruta) =>
    ruta.request().method() === 'POST' ? ruta.fulfill({ json: { analisis_id: ID } }) : ruta.continue(),
  )
  await page.route((u) => u.pathname === `/api/analisis/${ID}`, (ruta) => {
    const estado: EstadoAnalisis = {
      analisis_id: ID,
      estado: 'listo',
      etapas: [],
      resultado: r,
      error: null,
    }
    return ruta.fulfill({ json: estado })
  })
  await page.goto('/')
  await page.getByLabel('Usar un ejemplo listo').check()
  await page.getByRole('button', { name: /Rionegro/ }).click()
  await page.getByRole('button', { name: 'Calcular el factor' }).click()
  const informe = page.locator('.informe')
  await expect(informe).toBeVisible({ timeout: 60_000 })
  await page.waitForTimeout(1200) // el número del factor se asienta
  return informe
}

test('factor mayor que 1: el texto dice que ERA5 subestima y la regla dibuja lo que le falta', async ({ page }) => {
  const r = base()
  r.simulado = false
  r.etiqueta_sensor = 'DATOS DEL USUARIO (CSV subido)'
  const f = r.factores.era5.anual
  f.factor = 1.0821
  f.sesgo_relativo_pct = -7.58 // ERA5 se queda corto
  f.suma_fuente_kwh_m2 = 1000
  f.suma_sensor_kwh_m2 = 1082.1
  f.factor_verdadero = null
  r.factores.verdadero_anual = null
  r.factores.era5.mensual = r.factores.era5.mensual.map((m, i) => ({ ...m, factor: i % 2 ? 1.05 : 0.98, factor_verdadero: null }))
  const informe = await verInforme(page, r)

  await expect(page.locator('.hallazgo__numero')).toHaveText('1,0821')
  await expect(page.locator('.hallazgo__frase')).toContainText('ERA5 subestima')
  await expect(page.locator('.hallazgo__frase')).toContainText('7,6 %')
  await expect(page.locator('.hallazgo__frase')).not.toContainText('sobrestima')
  await expect(page.locator('.hallazgo__regla .nota')).toContainText('le falta a ERA5')
  await expect(page.locator('.hallazgo__formula')).toContainText('energía del sensor')
  await expect(page.locator('.hallazgo__formula')).not.toContainText('real')
  await expect(informe).toContainText('por encima de 1,00, ERA5 se queda corto')
  // La regla dibuja el tramo rayado a continuación de la barra de ERA5, hasta la del sensor.
  const geo = await page.$eval('.regla svg', (svg) => {
    const rect = (c: string) => svg.querySelector(`rect.${c}`)!
    const era5 = rect('regla__barra') as SVGRectElement
    const falta = rect('regla__exceso') as SVGRectElement
    return { finEra5: Number(era5.getAttribute('x')) + Number(era5.getAttribute('width')), x: Number(falta.getAttribute('x')), w: Number(falta.getAttribute('width')) }
  })
  expect(geo.w).toBeGreaterThan(10)
  expect(Math.abs(geo.x - geo.finEra5)).toBeLessThan(2)
  expect(await page.locator('.hallazgo__regla svg').getAttribute('aria-label')).toContain('se queda corto')
  await page.screenshot({ path: `${SALIDA}/honestidad-factor-mayor-que-1-1440.png`, fullPage: true })
})

test('sensor simulado: sello dentro del hallazgo, fórmula y frase honestas, pruebas circulares sin valor', async ({ page }) => {
  const r = base()
  r.simulado = true
  const informe = await verInforme(page, r)

  const hallazgo = page.locator('.hallazgo__factor')
  await expect(hallazgo.locator('.hallazgo__sello')).toHaveText('SIMULADO')
  await expect(page.locator('.hallazgo__formula')).toContainText('energía del sensor simulado')
  await expect(page.locator('.hallazgo__formula')).not.toContainText('energía real')
  await expect(page.locator('.hallazgo__frase')).toContainText('En esta simulación ERA5 se pasa')
  await expect(page.locator('.hallazgo__frase')).toContainText('(porque la simulación lo supone)')
  // Tautologías: sensor–ERA5 no informativo, validación = coherencia interna, sin "factor con NASA".
  await expect(page.locator('#fig-desfase-t').locator('xpath=..')).toContainText('no informativo')
  await expect(page.locator('.noinfo')).toContainText('No informativo')
  await expect(page.locator('#fig-desfase-t').locator('xpath=..').locator('.grafica')).toHaveCount(0)
  await expect(page.locator('.validacion')).toContainText('coherencia interna del cálculo')
  await expect(page.locator('.validacion')).toContainText('No mide el error real de ERA5')
  await expect(informe).not.toContainText('el factor sería')
  await expect(informe).toContainText('no se muestra «el factor con NASA»')
  // Evidencia de la hora de NASA: tabla con las correlaciones previas y aviso de no independencia.
  await expect(page.locator('.evidencia')).toContainText('+5 h')
  await expect(page.locator('.evidencia')).toContainText('no es un chequeo independiente')
  await expect(page.locator('.evidencia tr[data-elegido="true"]')).toContainText('+6 h')
  await page.screenshot({ path: `${SALIDA}/honestidad-simulado-1440.png`, fullPage: true })
})

test('datos subidos: fórmula sin "real" y NASA con su factor', async ({ page }) => {
  const r = base()
  r.simulado = false
  r.etiqueta_sensor = 'DATOS DEL USUARIO (CSV subido)'
  r.supuestos = []
  const informe = await verInforme(page, r)
  await expect(page.locator('.hallazgo__sello')).toHaveCount(0)
  await expect(page.locator('.hallazgo__formula')).toContainText('energía del sensor')
  await expect(page.locator('.hallazgo__formula')).not.toContainText('simulado')
  await expect(page.locator('.hallazgo__formula')).not.toContainText('real')
  await expect(informe).toContainText('el factor sería')
  await expect(informe).toContainText('solo descarta errores de más de 1 h')
})

test('nulos: «—» y ninguna interpretación, nunca 0', async ({ page }) => {
  const r = base()
  r.simulado = false
  r.etiqueta_sensor = 'DATOS DEL USUARIO (CSV subido)'
  const cc = r.consistencia.era5_vs_nasa
  cc.correlacion = null
  cc.diferencia_total_pct = null
  cc.suma_a_kwh_m2 = null
  cc.suma_b_kwh_m2 = null
  cc.conclusion = undefined
  r.factores.nasa.anual.factor = null
  r.factores.nasa.anual.sesgo_relativo_pct = null
  r.desfase.mejor_desfase_h = {}
  r.factores.era5.mensual[2] = { ...r.factores.era5.mensual[2], factor: null, sesgo_relativo_pct: null, suma_sensor_kwh_m2: null, suma_fuente_kwh_m2: null, factor_verdadero: null }
  r.energia_mensual[2] = { ...r.energia_mensual[2], nasa_kwh_m2: null, nasa_n_horas: 0 }
  r.dia_tipico[10] = { ...r.dia_tipico[10], sensor: null, era5: null, nasa: null }
  const informe = await verInforme(page, r)

  const cruzado = page.locator('#t-cruzado').locator('xpath=..')
  await expect(cruzado.locator('dl div').first().locator('dd.cifra')).toHaveText('—')
  await expect(cruzado.locator('dl div').nth(1).locator('dd.cifra')).toHaveText('—')
  await expect(cruzado).not.toContainText('se parecen')
  await expect(cruzado).not.toContainText('el factor sería')
  await expect(page.locator('#fig-desfase-t').locator('xpath=..')).toContainText('No se pudo calcular el máximo')
  await expect(page.locator('#fig-desfase-t').locator('xpath=..')).not.toContainText('no se ve desfase')
  // Tabla de factor mensual: marzo sin dato → «—», y el punto no se dibuja.
  const filaMarzo = page.locator('#fig-factor-t').locator('xpath=..').locator('details tbody tr').nth(2)
  await expect(filaMarzo.locator('td').first()).toHaveText('—')
  expect(await page.locator('#fig-factor-t').locator('xpath=..').locator('.tallo circle').count()).toBe(11)
  const filaEnergia = page.locator('#fig-energia-t').locator('xpath=..').locator('details tbody tr').nth(2)
  await expect(filaEnergia.locator('td').nth(3)).toHaveText('—')
  const texto = await informe.innerText()
  expect(texto).not.toContain('NaN')
  expect(texto).not.toContain('undefined')
})

test('año parcial, reloj del CSV corrido y unidades dudosas se marcan junto al número', async ({ page }) => {
  const r = base()
  r.simulado = false
  r.etiqueta_sensor = 'DATOS DEL USUARIO (CSV subido)'
  r.cobertura = {
    meses: [],
    meses_con_datos: ['ene', 'feb', 'mar', 'abr', 'may', 'jun'],
    meses_sin_datos: ['jul', 'ago', 'sep', 'oct', 'nov', 'dic'],
    anio_completo: false,
    criterio: 'x',
  }
  r.confiabilidad = {
    factor_no_confiable: true,
    motivo_no_confiable: 'posible desfase de hora en el CSV: la correlación sensor–ERA5 es máxima con +2 h, no con 0 h',
    unidades_sospechosas: true,
    motivo_unidades: 'el factor anual (0,0009) está fuera de 0,5–1,5',
  }
  r.desfase.mejor_desfase_h = { 'sensor vs ERA5': 2, 'ERA5 vs NASA': 0 }
  r.advertencias = ['Año parcial: el factor anual solo usa los meses con datos.', 'Factor no confiable: algo.', 'Otro aviso cualquiera.']
  const informe = await verInforme(page, r)
  const hallazgo = page.locator('.hallazgo__factor')
  await expect(hallazgo.locator('.hallazgo__titulo')).toContainText('(parcial)')
  await expect(hallazgo).toContainText('Parcial: solo tiene datos suficientes en ene, feb, mar, abr, may, jun')
  await expect(hallazgo).toContainText('No es un factor de año completo')
  await expect(hallazgo).toContainText('No confiable: posible desfase de hora en el CSV')
  await expect(hallazgo).toContainText('Revise las unidades del CSV')
  await expect(hallazgo.locator('.hallazgo__frase')).toContainText('los meses con datos')
  await expect(informe).toContainText('Factor de los meses con datos')
  // Los avisos que el hallazgo ya muestra no se repiten en la lista; los demás sí.
  await expect(page.locator('.advertencias li')).toHaveCount(1)
  await expect(page.locator('.advertencias li')).toContainText('Otro aviso cualquiera')
  await expect(page.locator('#fig-desfase-t').locator('xpath=..')).toContainText('posible desfase de hora en el CSV')
})

test('a 390 px los anexos pesados arrancan plegados y a 1440 px abiertos', async ({ page }) => {
  const r = base()
  await verInforme(page, r, 390)
  for (const id of ['t-calidad', 't-fuentes']) {
    await expect(page.locator(`details.anexo:has(#${id})`)).not.toHaveAttribute('open', /.*/)
  }
  await page.locator('details.anexo:has(#t-calidad) summary').click()
  await expect(page.locator('details.anexo:has(#t-calidad)')).toHaveAttribute('open', /.*/)
  await page.screenshot({ path: `${SALIDA}/honestidad-anexos-390.png`, fullPage: true })

  const ancho = await page.context().newPage()
  await verInforme(ancho, r, 1440)
  for (const id of ['t-calidad', 't-fuentes']) {
    await expect(ancho.locator(`details.anexo:has(#${id})`)).toHaveAttribute('open', /.*/)
  }
})

test('contraste: el detalle de cada paso del registro llega a 4,5:1 y no se desvanece', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.getByLabel('Usar un ejemplo listo').check()
  await page.getByRole('button', { name: /Rionegro/ }).click()
  await page.getByRole('button', { name: 'Calcular el factor' }).click()
  const detalle = page.locator('.paso__detalle').first()
  await expect(detalle).toBeVisible({ timeout: 60_000 })
  const medida = await detalle.evaluate((el) => {
    const canal = (v: number) => {
      const c = v / 255
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
    }
    const luz = (rgb: string) => {
      const [r, g, b] = (rgb.match(/[\d.]+/g) ?? []).map(Number)
      return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)
    }
    let fondo = el as HTMLElement | null
    let color = ''
    while (fondo) {
      color = getComputedStyle(fondo).backgroundColor
      if (color && color !== 'rgba(0, 0, 0, 0)' && color !== 'transparent') break
      fondo = fondo.parentElement
    }
    const a = luz(getComputedStyle(el).color)
    const b = luz(color || 'rgb(244, 244, 240)')
    return { ratio: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05), animacionOpacidad: getComputedStyle(el).animationName.includes('aparecer') }
  })
  expect(medida.ratio).toBeGreaterThanOrEqual(4.5)
  expect(medida.animacionOpacidad).toBe(false)
})
