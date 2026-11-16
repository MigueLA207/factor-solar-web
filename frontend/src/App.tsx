import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { api } from './api/cliente'
import type { Ejemplo, Etapa, EstadoAnalisis, Lugar, RespuestaSensor } from './api/tipos'
import { Buscador } from './componentes/Buscador'
import { Informe } from './componentes/Informe'
import { Mapa, type Punto } from './componentes/Mapa'
import { PasoSensor, type ModoSensor } from './componentes/PasoSensor'
import { Progreso } from './componentes/Progreso'
import { coord } from './util/formato'
import { prefiereMenosMovimiento } from './util/movimiento'

const ANIOS_RESPALDO = { min: 2015, max: 2025, defecto: 2024 }
const INICIO: Punto = { lat: 6.155, lon: -75.374, nombre: 'Rionegro, Antioquia' }

type Ejecucion =
  | { fase: 'inactivo' }
  | { fase: 'preparando' }
  | { fase: 'corriendo'; id: string; estado: EstadoAnalisis | null }
  | { fase: 'listo'; id: string; estado: EstadoAnalisis }
  | { fase: 'error'; mensaje: string; estado?: EstadoAnalisis | null }

/** Mientras el backend no responde con sus etapas, se muestran las once en espera. */
const ESPERA: Etapa[] = (
  [
    ['E', 'era5', 'Extraer ERA5 (Open-Meteo, models=era5)'],
    ['E', 'nasa', 'Extraer NASA POWER (horario, comunidad RE)'],
    ['E', 'sensor', 'Leer el sensor'],
    ['T', 'calidad_sensor', 'Calidad del sensor'],
    ['T', 'calidad_fuentes', 'Calidad de ERA5 y NASA'],
    ['T', 'hora_utc', 'Llevar todo a hora UTC (NASA y sensor)'],
    ['T', 'integracion', 'Unir las tres fuentes por ts_utc'],
    ['T', 'desfase', 'Chequeo de desfase'],
    ['L', 'factores', 'Factores de corrección'],
    ['L', 'consistencia', 'Consistencia entre fuentes'],
    ['L', 'resumen', 'Día típico y energía mensual'],
  ] as const
).map(([fase, paso, titulo]) => ({ fase, paso, titulo, estado: 'pendiente' as const, detalle: '' }))

export default function App() {
  const idAnio = useId()
  const [punto, setPunto] = useState<Punto>(INICIO)
  const [vuelo, setVuelo] = useState(0)
  const [anios, setAnios] = useState(ANIOS_RESPALDO)
  const [anio, setAnio] = useState(ANIOS_RESPALDO.defecto)
  const [bimodal, setBimodal] = useState(false)
  const [modo, setModo] = useState<ModoSensor>('simular')
  const [ejemplos, setEjemplos] = useState<Ejemplo[]>([])
  const [ejemplo, setEjemplo] = useState<Ejemplo | null>(null)
  const [subido, setSubido] = useState<RespuestaSensor | null>(null)
  const [ejec, setEjec] = useState<Ejecucion>({ fase: 'inactivo' })
  const refProgreso = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.ejemplos().then(setEjemplos).catch(() => setEjemplos([]))
    api
      .salud()
      .then((s) => {
        setAnios({ min: s.anio_min, max: s.anio_max, defecto: s.anio_por_defecto })
        setAnio(s.anio_por_defecto)
      })
      .catch(() => {})
  }, [])

  const volarA = useCallback((p: Punto) => {
    setPunto(p)
    setVuelo((v) => v + 1)
  }, [])

  const elegirLugar = (l: Lugar) => volarA({ lat: l.lat, lon: l.lon, nombre: [l.nombre, l.region].filter(Boolean).join(', ') })

  const elegirEjemplo = (e: Ejemplo) => {
    setEjemplo(e)
    setAnio(e.anio)
    volarA({ lat: e.lat, lon: e.lon, nombre: e.nombre })
  }

  // Sondeo del estado del análisis mientras corre.
  const idCorriendo = ejec.fase === 'corriendo' ? ejec.id : null
  useEffect(() => {
    if (!idCorriendo) return
    let vivo = true
    let t: ReturnType<typeof setTimeout> | undefined
    const tick = async () => {
      try {
        const estado = await api.estadoAnalisis(idCorriendo)
        if (!vivo) return
        if (estado.estado === 'listo' && estado.resultado) setEjec({ fase: 'listo', id: idCorriendo, estado })
        else if (estado.estado === 'error') setEjec({ fase: 'error', mensaje: estado.error ?? 'error desconocido', estado })
        else {
          setEjec({ fase: 'corriendo', id: idCorriendo, estado })
          t = setTimeout(tick, 500)
        }
      } catch (e) {
        if (vivo) setEjec({ fase: 'error', mensaje: e instanceof Error ? e.message : 'sin conexión con la API' })
      }
    }
    tick()
    return () => {
      vivo = false
      clearTimeout(t)
    }
  }, [idCorriendo])

  const ocupado = ejec.fase === 'preparando' || ejec.fase === 'corriendo'
  const faltaArchivo = modo === 'subir' && !subido?.sensor_id
  const faltaEjemplo = modo === 'ejemplo' && !ejemplo
  const anioFijo = (modo === 'ejemplo' && !!ejemplo) || (modo === 'subir' && !!subido)

  const calcular = async () => {
    setEjec({ fase: 'preparando' })
    requestAnimationFrame(() =>
      refProgreso.current?.scrollIntoView({ behavior: prefiereMenosMovimiento() ? 'auto' : 'smooth', block: 'start' }),
    )
    try {
      // El análisis usa el año del sensor (el backend responde 400 si no coincide).
      let sensorId: string
      let sitio = { lat: punto.lat, lon: punto.lon, anio, nombre: punto.nombre ?? null }
      if (modo === 'subir' && subido) {
        sensorId = subido.sensor_id
        sitio = { ...sitio, anio: subido.resumen.anio }
      } else if (modo === 'ejemplo' && ejemplo) {
        sensorId = ejemplo.sensor_id
        sitio = { lat: ejemplo.lat, lon: ejemplo.lon, anio: ejemplo.anio, nombre: ejemplo.nombre }
      } else {
        sensorId = (await api.simularSensor({ lat: punto.lat, lon: punto.lon, anio, nombre: punto.nombre ?? undefined })).sensor_id
      }
      const { analisis_id } = await api.crearAnalisis({
        ...sitio,
        sensor_id: sensorId,
        regimen: bimodal ? 'bimodal_andino' : null,
      })
      setEjec({ fase: 'corriendo', id: analisis_id, estado: null })
    } catch (e) {
      setEjec({ fase: 'error', mensaje: e instanceof Error ? e.message : 'no se pudo iniciar' })
    }
  }

  const etapas =
    ejec.fase === 'corriendo' || ejec.fase === 'listo' || ejec.fase === 'error' ? ejec.estado?.etapas ?? [] : []

  return (
    <>
      <a className="saltar" href="#principal">
        Saltar al contenido
      </a>
      {api.esDemo && (
        <p className="franja-demo" role="note">
          Modo demostración: la API está simulada en el navegador. Ninguna cifra de esta sesión es un resultado real.
        </p>
      )}
      <header className="cabecera">
        <div className="cabecera__marca">
          <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
            <circle cx="16" cy="16" r="6" fill="var(--sol)" />
            <path d="M3 16h7M22 16h7M16 3v7M16 22v7" stroke="currentColor" strokeWidth="2" />
          </svg>
          <p className="cabecera__nombre">Factor Solar</p>
        </div>
        <p className="cabecera__lema">ERA5 · NASA POWER · sensor en sitio</p>
      </header>

      <main id="principal">
        <section className="planilla" aria-labelledby="titulo-planilla">
          <div className="planilla__intro">
            <h1 id="titulo-planilla" className="planilla__titulo">
              ¿Cuánto se equivoca ERA5 donde va tu sensor?
            </h1>
            <p className="planilla__entrada">
              Elige el punto y el año, aporta los datos del sensor y el pipeline calcula el factor que convierte la radiación de ERA5 en energía real.
            </p>
          </div>

          <div className="planilla__rejilla">
            <div className="tramo tramo--sitio">
              <h2 className="tramo__titulo">
                <span className="tramo__n cifra">1</span> Sitio
              </h2>
              <Buscador alElegir={elegirLugar} />
              <Coordenadas punto={punto} bloqueado={ocupado} alCambiar={volarA} />
            </div>

            <div className="mapa">
              <Mapa punto={punto} vuelo={vuelo} alElegir={(p) => !ocupado && setPunto(p)} />
              <p className="mapa__lectura cifra" aria-live="polite">
                <span className="mapa__nombre">{punto.nombre ?? 'Punto elegido en el mapa'}</span>
                <span>
                  {coord(punto.lat, 'lat')} · {coord(punto.lon, 'lon')}
                </span>
              </p>
            </div>

            <div className="tramo tramo--anio">
              <h2 className="tramo__titulo" id={`${idAnio}-t`}>
                <span className="tramo__n cifra">2</span> Año
              </h2>
              <div className="segmentos" role="radiogroup" aria-labelledby={`${idAnio}-t`}>
                {Array.from({ length: anios.max - anios.min + 1 }, (_, i) => anios.max - i).map((a) => (
                  <label key={a} className="segmentos__op">
                    <input type="radio" name={`${idAnio}-anio`} value={a} checked={anio === a} onChange={() => setAnio(a)} disabled={ocupado || anioFijo} />
                    <span className="cifra">{a}</span>
                  </label>
                ))}
              </div>
              <p className="campo__nota">
                {anioFijo ? 'El año lo fija el sensor elegido.' : 'Se usa el año completo, hora por hora.'}
              </p>
            </div>

            <div className="tramo tramo--sensor">
              <h2 className="tramo__titulo">
                <span className="tramo__n cifra">3</span> Sensor
              </h2>
              <PasoSensor
                modo={modo}
                alCambiarModo={setModo}
                ejemplos={ejemplos}
                ejemplo={ejemplo}
                alElegirEjemplo={elegirEjemplo}
                subido={subido}
                alSubir={(r) => {
                  setSubido(r)
                  if (r) setAnio(r.resumen.anio)
                }}
                bloqueado={ocupado}
                contexto={{ anio, lat: punto.lat, lon: punto.lon }}
              />
            </div>

            <div className="tramo tramo--accion">
              <label className="interruptor">
                <input type="checkbox" checked={bimodal} onChange={(e) => setBimodal(e.target.checked)} disabled={ocupado} />
                <span>
                  Calcular también por fases del régimen bimodal
                  <span className="interruptor__nota">Andes colombianos: dos temporadas secas y dos de lluvias.</span>
                </span>
              </label>
              <button type="button" className="boton boton--primario" onClick={calcular} disabled={ocupado || faltaArchivo || faltaEjemplo}>
                {ocupado ? 'Calculando…' : 'Calcular el factor'}
              </button>
              <p className="campo__nota">
                {faltaArchivo && 'Primero sube el CSV del sensor.'}
                {faltaEjemplo && 'Primero elige un ejemplo.'}
                {!faltaArchivo && !faltaEjemplo && 'Consulta ERA5 y NASA POWER en vivo; la primera vez tarda unos segundos.'}
              </p>
            </div>
          </div>
        </section>

        <div ref={refProgreso} className="ancla">
          {ejec.fase !== 'inactivo' && (
            <Progreso etapas={etapas.length ? etapas : ESPERA} error={ejec.fase === 'error' ? ejec.mensaje : null} />
          )}
        </div>

        {ejec.fase === 'listo' && ejec.estado.resultado && (
          <Informe r={ejec.estado.resultado} urlDescarga={api.urlDescarga(ejec.id)} esDemo={api.esDemo} />
        )}
      </main>

      <footer className="pie">
        <p>
          Fuentes: ERA5 (Copernicus / ECMWF) vía Open-Meteo con <code>models=era5</code>; NASA POWER, comunidad RE. Mapa © colaboradores de OpenStreetMap.
        </p>
        <p>Proyecto académico de Adquisición e Integración de Datos, ITM. Un factor calculado con un sensor simulado no es una medición.</p>
      </footer>
    </>
  )
}

/** Coma decimal, como en el resto de la app; se aceptan coma o punto al escribir. */
const aTexto = (x: number) => String(x).replace('.', ',')

function Coordenadas({ punto, bloqueado, alCambiar }: { punto: Punto; bloqueado: boolean; alCambiar: (p: Punto) => void }) {
  const id = useId()
  const [lat, setLat] = useState(aTexto(punto.lat))
  const [lon, setLon] = useState(aTexto(punto.lon))
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    setLat(aTexto(punto.lat))
    setLon(aTexto(punto.lon))
  }, [punto.lat, punto.lon])

  const aplicar = () => {
    const a = Number(lat.replace(',', '.'))
    const o = Number(lon.replace(',', '.'))
    if (!Number.isFinite(a) || a < -90 || a > 90) return setError('La latitud va de -90 a 90.')
    if (!Number.isFinite(o) || o < -180 || o > 180) return setError('La longitud va de -180 a 180.')
    setError(null)
    if (a !== punto.lat || o !== punto.lon) alCambiar({ lat: a, lon: o, nombre: null })
  }
  const enter = (e: KeyboardEvent) => {
    if (e.key === 'Enter') aplicar()
  }

  return (
    <div className="coordenadas">
      <div className="coordenadas__campos">
        <div className="campo">
          <label className="campo__rotulo" htmlFor={`${id}-lat`}>
            Latitud
          </label>
          <input id={`${id}-lat`} className="campo__entrada cifra" inputMode="decimal" value={lat} disabled={bloqueado} onChange={(e) => setLat(e.target.value)} onBlur={aplicar} onKeyDown={enter} />
        </div>
        <div className="campo">
          <label className="campo__rotulo" htmlFor={`${id}-lon`}>
            Longitud
          </label>
          <input id={`${id}-lon`} className="campo__entrada cifra" inputMode="decimal" value={lon} disabled={bloqueado} onChange={(e) => setLon(e.target.value)} onBlur={aplicar} onKeyDown={enter} />
        </div>
      </div>
      <p className="campo__nota" role={error ? 'alert' : undefined}>
        {error ?? 'O haz clic en el mapa. Grados decimales; el oeste es negativo.'}
      </p>
    </div>
  )
}
