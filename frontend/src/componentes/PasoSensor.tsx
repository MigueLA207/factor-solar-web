import { useId, useState } from 'react'
import { api } from '../api/cliente'
import type { Ejemplo, RespuestaSensor } from '../api/tipos'
import { num } from '../util/formato'

export type ModoSensor = 'simular' | 'subir' | 'ejemplo'

interface Props {
  modo: ModoSensor
  alCambiarModo: (m: ModoSensor) => void
  ejemplos: Ejemplo[]
  ejemplo: Ejemplo | null
  alElegirEjemplo: (e: Ejemplo) => void
  subido: RespuestaSensor | null
  alSubir: (r: RespuestaSensor | null) => void
  bloqueado: boolean
  /** Se mandan con el CSV para que el backend sepa dónde está el sensor */
  contexto: { anio: number; lat: number; lon: number }
}

const OPCIONES: { valor: ModoSensor; titulo: string; nota: string }[] = [
  { valor: 'simular', titulo: 'Simular un sensor para este punto', nota: 'Se fabrica a partir del clima de este punto. Útil para probar el método; el resultado sale marcado como SIMULADO.' },
  { valor: 'subir', titulo: 'Subir el CSV de mi sensor', nota: 'Columnas ts_utc, irr_sitio y, si la tienes, t_modulo. Por minuto o por hora, en UTC.' },
  { valor: 'ejemplo', titulo: 'Usar un ejemplo listo', nota: 'Sensores simulados de climas distintos, ya preparados. El punto y el año pasan a ser los del ejemplo.' },
]

export function PasoSensor(p: Props) {
  const id = useId()
  const [subiendo, setSubiendo] = useState(false)
  const [errorSubida, setErrorSubida] = useState<string | null>(null)

  const subir = async (archivo: File | undefined) => {
    p.alSubir(null)
    setErrorSubida(null)
    if (!archivo) return
    setSubiendo(true)
    try {
      // El año lo decide el archivo (el backend toma el año con más registros); el punto va como referencia.
      p.alSubir(await api.subirSensor(archivo, { lat: p.contexto.lat, lon: p.contexto.lon }))
    } catch (e) {
      setErrorSubida(e instanceof Error ? e.message : 'No se pudo leer el archivo.')
    } finally {
      setSubiendo(false)
    }
  }

  return (
    <fieldset className="sensor" disabled={p.bloqueado}>
      <legend className="visualmente-oculto">Datos del sensor</legend>
      {OPCIONES.map((o) => (
        <div key={o.valor} className="sensor__opcion" data-activa={p.modo === o.valor}>
          <input
            type="radio"
            id={`${id}-${o.valor}`}
            name={`${id}-modo`}
            value={o.valor}
            checked={p.modo === o.valor}
            onChange={() => p.alCambiarModo(o.valor)}
            className="sensor__radio"
          />
          <label htmlFor={`${id}-${o.valor}`} className="sensor__titulo">
            {o.titulo}
          </label>
          <p className="sensor__nota">{o.nota}</p>

          {o.valor === 'subir' && p.modo === 'subir' && (
            <div className="sensor__detalle">
              <label className="boton boton--secundario boton--archivo">
                <input type="file" accept=".csv,text/csv" onChange={(e) => subir(e.target.files?.[0])} />
                {subiendo ? 'Leyendo…' : 'Elegir archivo CSV'}
              </label>
              {errorSubida && (
                <p className="aviso aviso--error" role="alert">
                  {errorSubida} Revisa que el archivo tenga la columna ts_utc en UTC e irr_sitio en W/m².
                </p>
              )}
              {p.subido && <ResumenSubida r={p.subido} />}
            </div>
          )}

          {o.valor === 'ejemplo' && p.modo === 'ejemplo' && (
            <ul className="sensor__ejemplos" role="list">
              {p.ejemplos.length === 0 && <li className="campo__nota">Cargando ejemplos…</li>}
              {p.ejemplos.map((e) => (
                <li key={e.sensor_id}>
                  <button
                    type="button"
                    className="ejemplo"
                    aria-pressed={p.ejemplo?.sensor_id === e.sensor_id}
                    onClick={() => p.alElegirEjemplo(e)}
                  >
                    <span className="ejemplo__nombre">{e.nombre}</span>
                    <span className="ejemplo__desc">
                      {e.descripcion} Clima {e.clima}. Año {e.anio}.
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </fieldset>
  )
}

function ResumenSubida({ r }: { r: RespuestaSensor }) {
  const v = r.validacion
  return (
    <div className="subida">
      <dl className="subida__datos">
        <div>
          <dt>Registros útiles</dt>
          <dd className="cifra">{num(r.resumen.filas)}</dd>
        </div>
        <div>
          <dt>Resolución</dt>
          <dd>por {r.resumen.frecuencia}</dd>
        </div>
        <div>
          <dt>Año</dt>
          <dd className="cifra">{r.resumen.anio}</dd>
        </div>
      </dl>
      <p className="campo__nota cifra">
        De {r.resumen.desde} a {r.resumen.hasta} UTC{r.resumen.tiene_temperatura ? ', con temperatura del módulo' : ''}.
      </p>
      {(v?.errores ?? []).map((x) => (
        <p key={x} className="aviso aviso--error">
          {x}
        </p>
      ))}
      {(v?.advertencias ?? v?.avisos ?? []).map((x) => (
        <p key={x} className="aviso">
          {x}
        </p>
      ))}
    </div>
  )
}
