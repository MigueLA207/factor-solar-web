// Cliente de la API. En producción la API vive en el mismo origen (FastAPI sirve frontend/dist);
// en desarrollo Vite reenvía /api a http://localhost:8000. Con VITE_API_MOCK=1 se usa mock.ts.
import { apiMock } from './mock'
import type {
  Ejemplo,
  EstadoAnalisis,
  Lugar,
  PeticionAnalisis,
  PeticionSimular,
  RespuestaBuscar,
  RespuestaCrearAnalisis,
  RespuestaEjemplos,
  RespuestaSensor,
  Salud,
} from './tipos'

export interface Api {
  /** true solo en modo demostración: la interfaz lo rotula siempre. */
  esDemo: boolean
  salud(): Promise<Salud>
  buscar(q: string): Promise<Lugar[]>
  ejemplos(): Promise<Ejemplo[]>
  simularSensor(p: PeticionSimular): Promise<RespuestaSensor>
  subirSensor(archivo: File, extra: { anio?: number; lat?: number; lon?: number }): Promise<RespuestaSensor>
  crearAnalisis(p: PeticionAnalisis): Promise<RespuestaCrearAnalisis>
  estadoAnalisis(id: string): Promise<EstadoAnalisis>
  /** null cuando no hay descarga (modo demostración) */
  urlDescarga(id: string): string | null
}

export class ErrorApi extends Error {
  /** Código HTTP; 0 = no hubo respuesta (servidor apagado o sin red). */
  readonly estado: number
  readonly cuerpo: unknown
  constructor(mensaje: string, estado: number, cuerpo?: unknown) {
    super(mensaje)
    this.estado = estado
    this.cuerpo = cuerpo
  }
}

export const MENSAJE_SIN_SERVIDOR =
  'No hay conexión con el servidor de la app. Ábrela con iniciar.bat y deja abierta la ventana de comandos mientras la usas.'

/** fetch que convierte "no hubo respuesta" en un ErrorApi con estado 0 y un mensaje en español. */
async function pedir(url: string, init?: RequestInit): Promise<Response> {
  try {
    const resp = await fetch(url, init)
    // Vite (desarrollo) responde 502/504 sin cuerpo JSON cuando el backend está apagado.
    if ((resp.status === 502 || resp.status === 503 || resp.status === 504) && !resp.headers.get('content-type')?.includes('json')) {
      throw new ErrorApi(MENSAJE_SIN_SERVIDOR, 0)
    }
    return resp
  } catch (e) {
    if (e instanceof ErrorApi) throw e
    throw new ErrorApi(MENSAJE_SIN_SERVIDOR, 0)
  }
}

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let mensaje = `El servidor respondió con un error (${resp.status}).`
    let cuerpo: unknown = null
    try {
      cuerpo = await resp.json()
      const d = (cuerpo as { detail?: unknown })?.detail
      if (typeof d === 'string') mensaje = d
      else if (d && typeof (d as { mensaje?: unknown }).mensaje === 'string') mensaje = (d as { mensaje: string }).mensaje
    } catch {
      /* cuerpo sin JSON */
    }
    throw new ErrorApi(mensaje, resp.status, cuerpo)
  }
  return resp.json() as Promise<T>
}

const enviar = (url: string, cuerpo: unknown) =>
  pedir(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo) })

const apiReal: Api = {
  esDemo: false,
  salud: () => pedir('/api/salud').then((r) => json<Salud>(r)),
  buscar: (q) => pedir(`/api/buscar?q=${encodeURIComponent(q)}`).then((r) => json<RespuestaBuscar>(r)).then((r) => r.lugares),
  ejemplos: () => pedir('/api/ejemplos').then((r) => json<RespuestaEjemplos>(r)).then((r) => r.ejemplos),
  simularSensor: (p) => enviar('/api/sensor/simular', p).then((r) => json<RespuestaSensor>(r)),
  subirSensor: (archivo, extra) => {
    const datos = new FormData()
    datos.append('archivo', archivo)
    if (extra.anio != null) datos.append('anio', String(extra.anio))
    if (extra.lat != null) datos.append('lat', String(extra.lat))
    if (extra.lon != null) datos.append('lon', String(extra.lon))
    return pedir('/api/sensor/subir', { method: 'POST', body: datos }).then((r) => json<RespuestaSensor>(r))
  },
  crearAnalisis: (p) => enviar('/api/analisis', p).then((r) => json<RespuestaCrearAnalisis>(r)),
  estadoAnalisis: (id) => pedir(`/api/analisis/${encodeURIComponent(id)}`).then((r) => json<EstadoAnalisis>(r)),
  urlDescarga: (id) => `/api/analisis/${encodeURIComponent(id)}/descargar`,
}

export const api: Api = import.meta.env.VITE_API_MOCK === '1' ? apiMock : apiReal
