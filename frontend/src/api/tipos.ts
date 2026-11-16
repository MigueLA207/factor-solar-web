// Tipos del contrato de la API v1, reconciliados con el backend real (backend/app.py,
// backend/almacen.py, backend/nucleo/pipeline.py, commit b21cbac).
// El frontend NUNCA calcula cifras de resultado: todo número que se muestra viene de aquí.
// Unidades en el nombre del campo: _kwh_m2 = kWh/m², _pct = porcentaje (0–100), _h = horas.

/** Errores: {"detail": {"mensaje": "...", ...}} (422 de validación incluye la misma forma). */
export interface ErrorDetalle {
  detail: { mensaje: string; validacion?: ValidacionCsv } | string
}

/** GET /api/salud */
export interface Salud {
  estado: string
  version: string
  anio_min: number
  anio_max: number
  anio_por_defecto: number
  parametros_simulacion: Record<string, unknown>
}

/** GET /api/buscar?q= → { lugares } (Open-Meteo Geocoding) */
export interface Lugar {
  nombre: string
  region?: string | null
  pais?: string | null
  codigo_pais?: string | null
  descripcion?: string | null
  lat: number
  lon: number
  elevacion_m?: number | null
  zona_horaria?: string | null
}
export interface RespuestaBuscar {
  lugares: Lugar[]
}

/** GET /api/ejemplos → { ejemplos }. El sensor ya existe: se usa sensor_id directo. */
export interface Ejemplo {
  sensor_id: string
  slug: string
  nombre: string
  lugar: string
  lat: number
  lon: number
  anio: number
  descripcion: string
  clima: string
  simulado: boolean
  factor_verdadero_anual: number | null
  frecuencia: 'minuto' | 'hora'
  filas: number
}
export interface RespuestaEjemplos {
  ejemplos: Ejemplo[]
}

/** Resumen del sensor (almacen.resumen_sensor). */
export interface ResumenSensor {
  sensor_id: string
  nombre: string
  simulado: boolean
  frecuencia: 'minuto' | 'hora'
  anio: number
  lat: number | null
  lon: number | null
  filas: number
  /** "YYYY-MM-DD HH:MM" UTC */
  desde: string
  hasta: string
  tiene_temperatura: boolean
  factor_verdadero_anual?: number
  supuestos?: string[]
  semilla?: number
}

/** Reporte de validación del CSV subido (sensor_csv.validar_csv). */
export interface ValidacionCsv {
  valido: boolean
  filas_leidas?: number
  separador?: string
  frecuencia?: 'minuto' | 'hora'
  anio?: number
  filas_utiles?: number
  desde?: string
  hasta?: string
  tiene_temperatura?: boolean
  errores?: string[]
  advertencias?: string[]
  /** nombre antiguo; el backend manda "advertencias" */
  avisos?: string[]
  [k: string]: unknown
}

/** POST /api/sensor/simular */
export interface PeticionSimular {
  lat: number
  lon: number
  anio: number
  semilla?: number
  parametros?: Record<string, number>
  nombre?: string
}
/** POST /api/sensor/simular  y  POST /api/sensor/subir */
export interface RespuestaSensor {
  sensor_id: string
  resumen: ResumenSensor
  validacion?: ValidacionCsv
}

/** POST /api/analisis. El año debe ser el del sensor (si no, 400). */
export interface PeticionAnalisis {
  lat: number
  lon: number
  anio: number
  sensor_id: string
  regimen?: 'bimodal_andino' | null
  nombre?: string | null
}
export interface RespuestaCrearAnalisis {
  analisis_id: string
}

/** E = Extraer, T = Transformar, L = Cargar (Load). */
export type Fase = 'E' | 'T' | 'L'
export type EstadoEtapa = 'pendiente' | 'en_curso' | 'listo' | 'error'

export interface Etapa {
  fase: Fase
  /** Identificador del paso, p. ej. "era5", "calidad_sensor" */
  paso: string
  titulo: string
  estado: EstadoEtapa
  detalle: string
}

/** GET /api/analisis/{id}. Sondear cada ~500 ms. */
export interface EstadoAnalisis {
  analisis_id: string
  estado: 'en_curso' | 'listo' | 'error'
  etapas: Etapa[]
  resultado?: Resultado | null
  error?: string | null
}

export interface Celda {
  lat: number
  lon: number
  elevacion_m: number | null
}

export interface FuenteDatos {
  nombre: string
  origen: string
  filas: number
  columnas: number
  llave: string
  aporte: string
}

export interface ReglaCalidad {
  fuente: 'sensor' | 'ERA5' | 'NASA' | string
  variable: string
  dimension: string
  regla: string
  filas_antes: number
  problemas_antes: number
  pct_antes: number
  accion: string
  problemas_despues: number
  pct_despues: number
  filas_despues: number
  /** Solo con sensor simulado: cuántos defectos se inyectaron a propósito */
  inyectados?: number | null
}

export interface PasoLinaje {
  paso: number
  fuentes_unidas: string
  llave: string
  tipo_union: string
  filas_entrada_A: number
  filas_entrada_B: number
  filas_resultado: number
  pct_coincidencia: number
  columnas_resultado: number
  filas_si_inner: number
  filas_perdidas_inner: number
  llaves_sin_cruce: number
  detalle_sin_cruce: string
}

export interface PuntoDesfase {
  desfase_h: number
  correlacion: number | null
}

export interface Desfase {
  pares: Record<string, PuntoDesfase[]>
  mejor_desfase_h: Record<string, number>
  desfase_nasa_aplicado_h: number
  horas_nasa_fuera_del_anio: number
  /**
   * Corrimiento de NASA: la regla de franjas de 15° (por_longitud_h) y las correlaciones con ERA5 de los
   * 3 candidatos (regla ±1 h) ANTES de elegir. El elegido se ajustó contra ERA5: no es una verificación independiente.
   */
  verificacion_desfase_nasa?: {
    por_longitud_h: number
    elegido_h: number
    coincide_con_regla: boolean
    correlacion_por_candidato: Record<string, number | null>
  }
  regla_nasa: string
  ok: boolean
  /** Siempre false: ERA5–NASA solo descarta errores de hora mayores de 1 h. */
  era5_nasa_independiente?: boolean
  /** true solo con datos subidos: un sensor simulado se fabrica con ERA5 y da 0 h por construcción. */
  sensor_era5_independiente?: boolean
  longitud_regla_nasa?: number
}

export interface MesCobertura {
  mes: number
  etiqueta: string
  n_horas: number
  n_horas_posibles: number
  pct: number
  con_datos: boolean
}

/** Meses del año que el sensor cubre de verdad (≥ 50 % de sus horas diurnas con ERA5). */
export interface Cobertura {
  meses: MesCobertura[]
  meses_con_datos: string[]
  meses_sin_datos: string[]
  anio_completo: boolean
  criterio: string
}

/** Señales de que un CSV subido puede no ser confiable (en sensores simulados siempre en false). */
export interface Confiabilidad {
  factor_no_confiable: boolean
  motivo_no_confiable: string | null
  unidades_sospechosas: boolean
  motivo_unidades: string | null
}

export interface FilaFactor {
  /** "anual", "ene".."dic" o "seca_1".. */
  periodo: string
  n_horas: number
  /** Los números pueden ser null (periodo sin datos): se muestran como «—», nunca como 0. */
  suma_sensor_kwh_m2: number | null
  suma_fuente_kwh_m2: number | null
  factor: number | null
  /** (fuente − sensor) / sensor × 100. Positivo: la fuente se pasa; negativo: se queda corta. */
  sesgo_relativo_pct: number | null
  factor_verdadero: number | null
  error_abs: number | null
  mes?: number
  etiqueta?: string
}

export interface FactoresFuente {
  rol: string
  nombre: string
  anual: FilaFactor
  mensual: FilaFactor[]
  fases_bimodal?: FilaFactor[]
}

export interface Comparacion {
  serie_a: string
  serie_b: string
  n_horas: number
  diferencia_media: number | null
  mae: number | null
  correlacion: number | null
  suma_a_kwh_m2: number | null
  suma_b_kwh_m2: number | null
  /** (a − b) / b × 100 */
  diferencia_total_pct: number | null
  filtro: string
  conclusion?: string
}

export interface PuntoDiaTipico {
  /** Etiqueta de FIN de intervalo en hora solar aproximada, 0..23 (0 = de 23:00 a 24:00) */
  hora_local: number
  /** Centro del intervalo (H − 0,5), de 0,5 a 23,5: ahí se dibuja el punto */
  hora_centro: number
  sensor: number | null
  era5: number | null
  nasa: number | null
}

export interface EnergiaMensual {
  mes: number
  etiqueta: string
  n_horas: number
  era5_sin_corregir_kwh_m2: number | null
  era5_por_factor_kwh_m2: number | null
  sensor_kwh_m2: number | null
  /** NASA se suma solo donde NASA tiene dato y lleva sus propias horas (nasa_n_horas). */
  nasa_kwh_m2: number | null
  nasa_n_horas: number
}

export interface Resultado {
  analisis_id: string
  sitio: {
    lat: number
    lon: number
    nombre: string | null
    celda_era5: Celda
    celda_nasa: Celda
    offset_hora_solar_local_h: number
  }
  anio: number
  simulado: boolean
  /** "SIMULADO" cuando simulado = true: se muestra tal cual. */
  etiqueta_sensor: string | null
  supuestos: string[]
  frecuencia_sensor: 'minuto' | 'hora'
  fuentes: FuenteDatos[]
  calidad: ReglaCalidad[]
  linaje: PasoLinaje[]
  desfase: Desfase
  factores: {
    era5: FactoresFuente
    nasa: FactoresFuente
    verdadero_anual: number | null
  }
  consistencia: {
    era5_vs_nasa: Comparacion
    sensor_vs_era5: Comparacion
    sensor_vs_nasa: Comparacion
    [k: string]: Comparacion
  }
  dia_tipico: PuntoDiaTipico[]
  energia_mensual: EnergiaMensual[]
  sesgo_era5_pct: number | null
  sesgo_nasa_pct: number | null
  cobertura?: Cobertura
  confiabilidad?: Confiabilidad
  calentamiento_modulo_c?: number | null
  advertencias: string[]
  fuentes_api?: Record<string, unknown>
  /** Solo si se pidió regimen = "bimodal_andino" */
  fases_bimodal?: { era5: FilaFactor[]; nasa: FilaFactor[] } | null
}
