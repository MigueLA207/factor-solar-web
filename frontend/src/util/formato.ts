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

/** Separador de miles = espacio fino (estilo SI), para no confundirlo con la coma decimal. */
export const num = (x: number, dec = 0) => fmt(dec, dec).format(x).replace(/\./g, ' ')
export const pct = (x: number, dec = 1) => `${num(x, dec)} %`
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
export function leerCorrelacion(r: number) {
  if (r >= 0.9) return 'se parecen mucho hora a hora'
  if (r >= 0.75) return 'se parecen bastante hora a hora'
  if (r >= 0.5) return 'se parecen a medias hora a hora'
  return 'se parecen poco hora a hora'
}
