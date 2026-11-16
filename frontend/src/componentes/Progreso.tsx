import type { Etapa, Fase } from '../api/tipos'

const FASES: { fase: Fase; nombre: string; que: string }[] = [
  { fase: 'E', nombre: 'Extraer', que: 'traer los datos crudos de cada fuente' },
  { fase: 'T', nombre: 'Transformar', que: 'limpiar, llevar a la misma hora y unir' },
  { fase: 'L', nombre: 'Cargar', que: 'guardar tablas listas para usar' },
]

/** Por qué se detuvo: sin servidor, pedido rechazado por la API o error dentro de una etapa. */
export interface Falla {
  tipo: 'conexion' | 'pedido' | 'analisis'
  mensaje: string
}

interface Props {
  etapas: Etapa[]
  falla?: Falla | null
  alReintentar?: () => void
  alRevisar?: () => void
}

function Marca({ estado }: { estado: Etapa['estado'] }) {
  // Cuadro vacío = pendiente; medio = en curso; lleno con visto = listo; aspa = error.
  return (
    <svg className={`marca marca--${estado}`} width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <rect x="1.5" y="1.5" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="1.5" />
      {estado === 'en_curso' && <rect x="1.5" y="1.5" width="6.5" height="13" fill="currentColor" />}
      {estado === 'listo' && (
        <>
          <rect x="1.5" y="1.5" width="13" height="13" fill="currentColor" />
          <path d="M4.5 8.2l2.4 2.4 4.6-5" fill="none" stroke="var(--papel)" strokeWidth="1.8" />
        </>
      )}
      {estado === 'error' && <path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="currentColor" strokeWidth="1.8" />}
    </svg>
  )
}

const NOMBRE_ESTADO: Record<Etapa['estado'], string> = {
  pendiente: 'pendiente',
  en_curso: 'en curso',
  listo: 'listo',
  error: 'con error',
}

export function Progreso({ etapas, falla, alReintentar, alRevisar }: Props) {
  const hechos = etapas.filter((e) => e.estado === 'listo').length
  const total = etapas.length
  const numero = new Map(etapas.map((e, i) => [e.paso, i + 1]))
  const enCurso = etapas.find((e) => e.estado === 'en_curso')
  return (
    <section className="progreso" aria-labelledby="titulo-progreso">
      <div className="progreso__cabeza">
        <h2 id="titulo-progreso" className="seccion__titulo">
          Ejecución del pipeline
        </h2>
        <p className="progreso__cuenta" aria-live="polite">
          <span className="cifra">{hechos}</span> de <span className="cifra">{total}</span> pasos
          {enCurso && <span className="progreso__ahora"> · ahora: {enCurso.titulo}</span>}
        </p>
      </div>
      <div
        className="progreso__regla"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={hechos}
        aria-label="Pasos terminados"
      >
        <div className="progreso__relleno" style={{ transform: `scaleX(${hechos / total})` }} />
      </div>
      {/* El error va antes del registro de pasos: a 390 px quedaría bajo once casillas vacías. */}
      {falla && <Detenido falla={falla} etapa={etapas.find((e) => e.estado === 'error')} alReintentar={alReintentar} alRevisar={alRevisar} />}
      <ol className="progreso__fases">
        {FASES.map((f) => (
          <li key={f.fase} className="fase">
            <h3 className="fase__nombre">{f.nombre}</h3>
            <p className="fase__que">{f.que}</p>
            <ol className="fase__pasos">
              {etapas
                .filter((e) => e.fase === f.fase)
                .map((e) => (
                  <li key={e.paso} className="paso" data-estado={e.estado}>
                    <Marca estado={e.estado} />
                    <span className="paso__num cifra">{numero.get(e.paso)}</span>
                    <span className="paso__texto">
                      <span className="paso__titulo">{e.titulo}</span>
                      <span className="visualmente-oculto">: {NOMBRE_ESTADO[e.estado]}</span>
                      {e.detalle && <span className="paso__detalle">{e.detalle}</span>}
                    </span>
                  </li>
                ))}
            </ol>
          </li>
        ))}
      </ol>
    </section>
  )
}

/** Bloque de error: qué pasó, qué hacer, y reintentar sin volver a llenar nada. */
function Detenido({ falla, etapa, alReintentar, alRevisar }: { falla: Falla; etapa?: Etapa; alReintentar?: () => void; alRevisar?: () => void }) {
  const titulo =
    falla.tipo === 'conexion'
      ? 'No hay conexión con el servidor'
      : falla.tipo === 'pedido'
        ? 'El servidor no aceptó el pedido'
        : `El análisis se detuvo${etapa ? ` en «${etapa.titulo}»` : ''}`
  const consejo =
    falla.tipo === 'conexion'
      ? 'Los datos que elegiste siguen aquí. Cuando el servidor esté abierto, reintenta.'
      : falla.tipo === 'pedido'
        ? 'Revisa el sitio, el año y el sensor de los pasos 1 a 3; los datos elegidos siguen aquí.'
        : 'Si el fallo viene de Open-Meteo o NASA POWER, suele ser pasajero: espera un minuto y reintenta. Las consultas que ya respondieron quedan guardadas y no se repiten.'
  return (
    <div className="detenido" role="alert">
      <h3 className="detenido__titulo">{titulo}</h3>
      <p className="detenido__mensaje">{falla.mensaje}</p>
      <p className="detenido__consejo">{consejo}</p>
      <div className="detenido__acciones">
        {alReintentar && (
          <button type="button" className="boton boton--primario" onClick={alReintentar}>
            Reintentar
          </button>
        )}
        {alRevisar && (
          <button type="button" className="boton boton--secundario" onClick={alRevisar}>
            Revisar los datos
          </button>
        )}
      </div>
    </div>
  )
}
