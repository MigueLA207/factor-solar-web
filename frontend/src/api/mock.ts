// API SIMULADA para desarrollar y tomar capturas sin backend (npm run dev:mock).
// Imita la FORMA de las respuestas del backend real; las cifras son inventadas en el navegador.
// La interfaz lo rotula como "modo demostración" y nunca debe presentarse como resultado real.
import type { Api } from './cliente'
import type {
  Ejemplo,
  Etapa,
  EstadoAnalisis,
  FilaFactor,
  Lugar,
  PeticionAnalisis,
  PeticionSimular,
  ReglaCalidad,
  RespuestaSensor,
  Resultado,
  Salud,
} from './tipos'

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

const LUGARES: Lugar[] = [
  { nombre: 'Rionegro', region: 'Antioquia', pais: 'Colombia', lat: 6.155, lon: -75.374 },
  { nombre: 'Medellín', region: 'Antioquia', pais: 'Colombia', lat: 6.244, lon: -75.581 },
  { nombre: 'Bogotá', region: 'Bogotá D.C.', pais: 'Colombia', lat: 4.711, lon: -74.072 },
  { nombre: 'Barranquilla', region: 'Atlántico', pais: 'Colombia', lat: 10.964, lon: -74.796 },
  { nombre: 'Riohacha', region: 'La Guajira', pais: 'Colombia', lat: 11.544, lon: -72.907 },
  { nombre: 'Cali', region: 'Valle del Cauca', pais: 'Colombia', lat: 3.452, lon: -76.532 },
  { nombre: 'Quibdó', region: 'Chocó', pais: 'Colombia', lat: 5.694, lon: -76.661 },
]

const ej = (slug: string, nombre: string, lugar: string, lat: number, lon: number, descripcion: string, clima: string): Ejemplo => ({
  sensor_id: `demo-ejemplo-${slug}`,
  slug,
  nombre,
  lugar,
  lat,
  lon,
  anio: 2024,
  descripcion,
  clima,
  simulado: true,
  factor_verdadero_anual: null,
  frecuencia: 'minuto',
  filas: 0,
})

const EJEMPLOS: Ejemplo[] = [
  ej('rionegro', 'Rionegro (Antioquia, CO)', 'Rionegro, Antioquia, Colombia', 6.147, -75.377, 'Altiplano del Oriente antioqueño.', 'andino de montaña'),
  ej('riohacha', 'Riohacha (La Guajira, CO)', 'Riohacha, La Guajira, Colombia', 11.544, -72.907, 'Costa seca y muy soleada.', 'árido costero'),
  ej('quibdo', 'Quibdó (Chocó, CO)', 'Quibdó, Chocó, Colombia', 5.694, -76.661, 'Uno de los sitios más nublados del país.', 'selva húmeda'),
]

const PASOS: [Etapa['fase'], string, string, string][] = [
  ['E', 'era5', 'Extraer ERA5 (Open-Meteo, models=era5)', 'demo: horas inventadas'],
  ['E', 'nasa', 'Extraer NASA POWER (horario, comunidad RE)', 'demo: horas inventadas'],
  ['E', 'sensor', 'Leer el sensor', 'demo: registros inventados — SIMULADO'],
  ['T', 'calidad_sensor', 'Calidad del sensor', 'demo'],
  ['T', 'calidad_fuentes', 'Calidad de ERA5 y NASA', 'demo'],
  ['T', 'hora_utc', 'Llevar todo a hora UTC (NASA y sensor)', 'demo'],
  ['T', 'integracion', 'Unir las tres fuentes por ts_utc', 'demo'],
  ['T', 'desfase', 'Chequeo de desfase (correlación −8 a +8 h)', 'demo'],
  ['L', 'factores', 'Factores de corrección', 'demo'],
  ['L', 'consistencia', 'Consistencia entre fuentes', 'demo'],
  ['L', 'resumen', 'Día típico y energía mensual', 'demo'],
]

/** PRNG determinista (mulberry32): el mismo punto da la misma demostración. */
function generador(semilla: number) {
  let a = semilla >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
const r = (x: number, d: number) => Math.round(x * 10 ** d) / 10 ** d

function fila(periodo: string, s: number, f: number, n: number, verdadero: number | null, extra: Partial<FilaFactor> = {}): FilaFactor {
  const factor = r(s / f, 4)
  return {
    periodo,
    n_horas: n,
    suma_sensor_kwh_m2: r(s, 2),
    suma_fuente_kwh_m2: r(f, 2),
    factor,
    sesgo_relativo_pct: r(((f - s) / s) * 100, 2),
    factor_verdadero: verdadero,
    error_abs: verdadero == null ? null : r(Math.abs(factor - verdadero), 4),
    ...extra,
  }
}

function resultadoDemo(p: PeticionAnalisis, id: string): Resultado {
  const azar = generador(Math.abs(Math.round(p.lat * 1000) * 7919 + Math.round(p.lon * 1000) * 104729 + p.anio))
  const nubes = 0.35 + azar() * 0.4
  const anual = 2050 - nubes * 700
  const e5 = MESES.map((_, i) => (anual / 12) * (1 + Math.cos((i / 12) * 4 * Math.PI) * 0.09 + (azar() - 0.5) * 0.06))
  const fm = MESES.map((_, i) => 0.97 - nubes * 0.16 + Math.cos((i / 12) * 4 * Math.PI) * 0.025 + (azar() - 0.5) * 0.02)
  const se = e5.map((v, i) => v * fm[i])
  const na = e5.map((v) => v * (0.92 + azar() * 0.06))
  const suma = (a: number[]) => a.reduce((x, y) => x + y, 0)
  const nh = MESES.map(() => 390 + Math.round(azar() * 30))
  const verdaderoAnual = r(suma(se) / suma(e5) + (azar() - 0.5) * 0.004, 4)
  const fases = [
    ['seca_1', 'Seca 1 (dic–feb)', [11, 0, 1]],
    ['lluvias_1', 'Lluvias 1 (mar–may)', [2, 3, 4]],
    ['seca_2', 'Seca 2 (jun–ago)', [5, 6, 7]],
    ['lluvias_2', 'Lluvias 2 (sep–nov)', [8, 9, 10]],
  ] as const
  const porFase = (serie: number[], verdadero: boolean) =>
    fases.map(([periodo, etiqueta, ms]) =>
      fila(periodo, suma(ms.map((m) => se[m])), suma(ms.map((m) => serie[m])), suma(ms.map((m) => nh[m])), verdadero ? r(suma(ms.map((m) => se[m])) / suma(ms.map((m) => e5[m])), 4) : null, { etiqueta }),
    )
  const pico = 760 + (1 - nubes) * 180
  const forma = (h: number) => {
    const x = (h - 12) / 6.1
    return Math.abs(x) >= 1 ? 0 : Math.pow(Math.cos((x * Math.PI) / 2), 1.5)
  }
  const corr = (k: number, base: number) => r(base * Math.cos((k / 8) * (Math.PI / 2)) ** 1.6 * 1.3 - 0.3, 4)
  const sensorVsEra5 = Array.from({ length: 17 }, (_, i) => ({ desfase_h: i - 8, correlacion: corr(i - 8, 0.997) }))
  const era5VsNasa = Array.from({ length: 17 }, (_, i) => ({ desfase_h: i - 8, correlacion: corr(i - 8, 0.95) }))
  const regla = (fuente: string, variable: string, dimension: string, texto: string, antes: number, accion: string, despues: number): ReglaCalidad => ({
    fuente, variable, dimension, regla: texto, filas_antes: 527040, problemas_antes: antes, pct_antes: r((antes / 527040) * 100, 3), accion, problemas_despues: despues, pct_despues: r((despues / 527040) * 100, 3), filas_despues: 527040, inyectados: antes || null,
  })
  const sumE5 = suma(e5)
  const sumS = suma(se)
  const sumN = suma(na)

  return {
    analisis_id: id,
    sitio: {
      lat: p.lat,
      lon: p.lon,
      nombre: p.nombre ?? null,
      celda_era5: { lat: r(Math.round(p.lat * 4) / 4, 2), lon: r(Math.round(p.lon * 4) / 4, 2), elevacion_m: null },
      celda_nasa: { lat: r(p.lat, 3), lon: r(p.lon, 3), elevacion_m: null },
      offset_hora_solar_local_h: Math.round(p.lon / 15),
    },
    anio: p.anio,
    simulado: true,
    etiqueta_sensor: 'SIMULADO',
    supuestos: [
      'Demostración: estas cifras se inventan en el navegador para probar la interfaz.',
      'Con el backend, aquí aparecen los supuestos reales de la simulación del sensor.',
    ],
    frecuencia_sensor: 'minuto',
    fuentes: [
      { nombre: 'Sensor en sitio (SIMULADO)', origen: 'demo', filas: 527040, columnas: 3, llave: 'ts_utc (minuto agregado a hora)', aporte: 'numerador del factor' },
      { nombre: 'Open-Meteo ERA5', origen: 'demo', filas: 8784, columnas: 3, llave: 'ts_utc (ya viene en UTC)', aporte: 'denominador del factor' },
      { nombre: 'NASA POWER', origen: 'demo', filas: 8832, columnas: 3, llave: 'ts_utc (hora solar local +6 h)', aporte: 'chequeo cruzado' },
    ],
    calidad: [
      regla('sensor', 'ts_utc', 'unicidad', 'Registros repetidos (mismo minuto)', 120, 'se conserva el último envío', 0),
      regla('sensor', 'ts_utc', 'oportunidad', 'Registros faltantes', 566, 'huecos cortos se interpolan; cortes largos quedan vacíos', 445),
      regla('sensor', 'irr_sitio', 'validez', 'Valores imposibles (más de 1500 W/m²)', 25, 'se vacían y luego se interpolan', 0),
      regla('sensor', 'irr_sitio', 'validez', 'Negativos pequeños de noche', 5000, 'se llevan a 0', 0),
      regla('ERA5', 'irr_era5', 'completitud', 'Irradiancia vacía', 0, 'se deja vacía (sin imputar)', 0),
      regla('NASA', 'irr_nasa', 'completitud', 'Irradiancia sin dato (código -999)', 0, 'el -999 se cambia por vacío', 0),
    ],
    linaje: [
      { paso: 1, fuentes_unidas: 'sensor + ERA5', llave: 'ts_utc', tipo_union: 'left (validate 1:1)', filas_entrada_A: 8784, filas_entrada_B: 8784, filas_resultado: 8784, pct_coincidencia: 100, columnas_resultado: 6, filas_si_inner: 8784, filas_perdidas_inner: 0, llaves_sin_cruce: 0, detalle_sin_cruce: 'todas las horas cruzaron' },
      { paso: 2, fuentes_unidas: 'sensor+ERA5 + NASA', llave: 'ts_utc', tipo_union: 'left (validate 1:1)', filas_entrada_A: 8784, filas_entrada_B: 8784, filas_resultado: 8784, pct_coincidencia: 100, columnas_resultado: 8, filas_si_inner: 8784, filas_perdidas_inner: 0, llaves_sin_cruce: 0, detalle_sin_cruce: 'todas las horas cruzaron' },
    ],
    desfase: {
      pares: { 'sensor vs ERA5': sensorVsEra5, 'ERA5 vs NASA': era5VsNasa },
      mejor_desfase_h: { 'sensor vs ERA5': 0, 'ERA5 vs NASA': 0 },
      desfase_nasa_aplicado_h: 6,
      horas_nasa_fuera_del_anio: 48,
      regla_nasa: 'Demostración: con el backend aquí se explica cómo se pasa NASA de hora solar local a UTC.',
      ok: true,
    },
    factores: {
      era5: {
        rol: 'factor de cotización',
        nombre: 'factor de cotización',
        anual: fila('anual', sumS, sumE5, suma(nh), verdaderoAnual),
        mensual: MESES.map((m, i) => fila(m, se[i], e5[i], nh[i], r(fm[i] + (azar() - 0.5) * 0.004, 4), { mes: i + 1 })),
        fases_bimodal: porFase(e5, true),
      },
      nasa: {
        rol: 'chequeo cruzado',
        nombre: 'chequeo cruzado',
        anual: fila('anual', sumS, sumN, suma(nh), null),
        mensual: MESES.map((m, i) => fila(m, se[i], na[i], nh[i], null, { mes: i + 1 })),
      },
      verdadero_anual: verdaderoAnual,
    },
    consistencia: {
      era5_vs_nasa: {
        serie_a: 'irr_era5', serie_b: 'irr_nasa', n_horas: suma(nh), diferencia_media: 0, mae: 0, correlacion: 0.95,
        suma_a_kwh_m2: r(sumE5, 2), suma_b_kwh_m2: r(sumN, 2), diferencia_total_pct: r(((sumE5 - sumN) / sumN) * 100, 2), filtro: 'demo',
        conclusion: 'Demostración: con el backend aquí aparece la conclusión del chequeo cruzado en palabras.',
      },
      sensor_vs_era5: { serie_a: 'irr_sitio', serie_b: 'irr_era5', n_horas: suma(nh), diferencia_media: 0, mae: 0, correlacion: 0.997, suma_a_kwh_m2: r(sumS, 2), suma_b_kwh_m2: r(sumE5, 2), diferencia_total_pct: r(((sumS - sumE5) / sumE5) * 100, 2), filtro: 'demo' },
      sensor_vs_nasa: { serie_a: 'irr_sitio', serie_b: 'irr_nasa', n_horas: suma(nh), diferencia_media: 0, mae: 0, correlacion: 0.94, suma_a_kwh_m2: r(sumS, 2), suma_b_kwh_m2: r(sumN, 2), diferencia_total_pct: r(((sumS - sumN) / sumN) * 100, 2), filtro: 'demo' },
    },
    dia_tipico: Array.from({ length: 24 }, (_, h) => ({
      hora_local: h,
      era5: r(pico * forma(h), 1),
      sensor: r(pico * forma(h) * (sumS / sumE5), 1),
      nasa: r(pico * forma(h) * (sumN / sumE5), 1),
    })),
    energia_mensual: MESES.map((m, i) => ({
      mes: i + 1,
      etiqueta: m,
      n_horas: nh[i],
      era5_sin_corregir_kwh_m2: r(e5[i], 2),
      era5_por_factor_kwh_m2: r(e5[i] * (sumS / sumE5), 2),
      sensor_kwh_m2: r(se[i], 2),
      nasa_kwh_m2: r(na[i], 2),
    })),
    sesgo_era5_pct: r(((sumE5 - sumS) / sumS) * 100, 2),
    sesgo_nasa_pct: r(((sumN - sumS) / sumS) * 100, 2),
    advertencias: [],
    fases_bimodal: p.regimen ? { era5: porFase(e5, true), nasa: porFase(na, false) } : null,
  }
}

const analisis = new Map<string, { inicio: number; peticion: PeticionAnalisis }>()
const espera = (ms: number) => new Promise((res) => setTimeout(res, ms))
const MS_POR_PASO = 420

const resumen = (id: string, p: { lat: number; lon: number; anio: number }) => ({
  sensor_id: id,
  nombre: 'Sensor de demostración',
  simulado: true,
  frecuencia: 'minuto' as const,
  anio: p.anio,
  lat: p.lat,
  lon: p.lon,
  filas: 527040,
  desde: `${p.anio}-01-01 00:00`,
  hasta: `${p.anio}-12-31 23:59`,
  tiene_temperatura: true,
})

export const apiMock: Api = {
  esDemo: true,
  async salud(): Promise<Salud> {
    return { estado: 'ok', version: 'demo', anio_min: 2015, anio_max: 2025, anio_por_defecto: 2024, parametros_simulacion: {} }
  },
  async buscar(q) {
    await espera(150)
    const t = q.trim().toLowerCase()
    return LUGARES.filter((l) => l.nombre.toLowerCase().includes(t) || (l.region ?? '').toLowerCase().includes(t))
  },
  async ejemplos() {
    await espera(100)
    return EJEMPLOS
  },
  async simularSensor(p: PeticionSimular): Promise<RespuestaSensor> {
    await espera(400)
    const id = `demo-sim-${Math.round(p.lat * 1000)}-${Math.round(p.lon * 1000)}-${p.anio}`
    return { sensor_id: id, resumen: resumen(id, p) }
  },
  async subirSensor(archivo, extra): Promise<RespuestaSensor> {
    await espera(400)
    const id = `demo-csv-${archivo.size}`
    return {
      sensor_id: id,
      resumen: { ...resumen(id, { lat: extra.lat ?? 0, lon: extra.lon ?? 0, anio: extra.anio ?? 2024 }), simulado: false },
      validacion: { valido: true, avisos: ['Modo demostración: el archivo no se leyó de verdad.'] },
    }
  },
  async crearAnalisis(p) {
    await espera(150)
    const id = `demo-${Date.now()}`
    analisis.set(id, { inicio: Date.now(), peticion: p })
    return { analisis_id: id }
  },
  async estadoAnalisis(id): Promise<EstadoAnalisis> {
    await espera(50)
    const a = analisis.get(id)
    if (!a) return { analisis_id: id, estado: 'error', etapas: [], error: 'Análisis no encontrado.' }
    const hechos = Math.min(PASOS.length, Math.floor((Date.now() - a.inicio) / MS_POR_PASO))
    const etapas: Etapa[] = PASOS.map(([fase, paso, titulo, detalle], i) => ({
      fase,
      paso,
      titulo,
      estado: i < hechos ? 'listo' : i === hechos ? 'en_curso' : 'pendiente',
      detalle: i < hechos ? detalle : '',
    }))
    if (hechos < PASOS.length) return { analisis_id: id, estado: 'en_curso', etapas }
    return { analisis_id: id, estado: 'listo', etapas, resultado: resultadoDemo(a.peticion, id) }
  },
  urlDescarga() {
    return null
  },
}
