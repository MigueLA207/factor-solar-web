// Formato de cifras en español de Colombia. Solo da forma: nunca cambia el valor que manda la API.
const cache = new Map<string, Intl.NumberFormat>()

function fmt(min: number, max: number) {
  const k = `${min}-${max}`
  let f = cache.get(k)
  if (!f) {
    f = new Intl.NumberFormat('es-CO', { minimumFractionDigits: min, maximumFractionDigits: max })
    cache.set(k, f)
  }
  return f
}

export const SIN_DATO = '—'
/** true si hay un número usable (null, undefined y NaN son «sin dato»). */
export const hay = (x: number | null | undefined): x is number => typeof x === 'number' && Number.isFinite(x)

/**
 * Separador de miles = espacio fino (estilo SI), para no confundirlo con la coma decimal.
 * Un valor ausente se muestra como «—»: nunca se convierte en 0.
 */
export const num = (x: number | null | undefined, dec = 0) => (hay(x) ? fmt(dec, dec).format(x).replace(/\./g, '\u202f') : SIN_DATO)
export const pct = (x: number | null | undefined, dec = 1) => (hay(x) ? `${num(x, dec)} %` : SIN_DATO)
/** "+" para positivos; vacío para negativos (ya traen su signo) y para sin dato. */
export const signo = (x: number | null | undefined) => (hay(x) && x > 0 ? '+' : '')

/**
 * Cuánto se pasa o se queda corta una fuente frente al sensor, según el signo de
 * sesgo_relativo_pct = (fuente − sensor) / sensor × 100. Sin dato: sin interpretación.
 */
export function leerSesgo(sesgo: number | null | undefined) {
  if (!hay(sesgo)) return null
  if (sesgo > 0) return { sobre: true, verbo: 'se pasa', verboSin: 'sobrestima', magnitud: sesgo }
  if (sesgo < 0) return { sobre: false, verbo: 'se queda corto', verboSin: 'subestima', magnitud: Math.abs(sesgo) }
  return { sobre: false, verbo: 'coincide con el sensor', verboSin: 'coincide con el sensor', magnitud: 0 }
}
export const coord = (x: number, eje: 'lat' | 'lon') => {
  const h = eje === 'lat' ? (x >= 0 ? 'N' : 'S') : x >= 0 ? 'E' : 'O'
  return `${fmt(3, 3).format(Math.abs(x))}° ${h}`
}

export const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
export const MESES_LARGOS = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

/** Palabras llanas para una correlación de Pearson. */
export function leerCorrelacion(r: number | null | undefined) {
  if (!hay(r)) return ''
  if (r >= 0.9) return 'se parecen mucho hora a hora'
  if (r >= 0.75) return 'se parecen bastante hora a hora'
  if (r >= 0.5) return 'se parecen a medias hora a hora'
  return 'se parecen poco hora a hora'
}
