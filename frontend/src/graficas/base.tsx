import { useLayoutEffect, useRef, useState, type PointerEvent, type ReactNode } from 'react'

/** Ancho real del contenedor, para dibujar el SVG a tamaño de píxel (texto legible a 390 px). */
export function useAncho<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [ancho, setAncho] = useState(600)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    setAncho(el.clientWidth)
    const ro = new ResizeObserver(([e]) => setAncho(Math.round(e.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, ancho] as const
}

export const escala = (d0: number, d1: number, r0: number, r1: number) => (v: number) =>
  r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0)

/** Marcas "redondas" para un eje. */
export function marcas(min: number, max: number, n = 5) {
  const paso0 = (max - min) / n
  const mag = Math.pow(10, Math.floor(Math.log10(paso0)))
  const paso = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((k) => k >= paso0) ?? paso0
  const out: number[] = []
  for (let v = Math.ceil(min / paso) * paso; v <= max + paso * 1e-6; v += paso) out.push(Number(v.toFixed(6)))
  return out
}

export interface SerieLeyenda {
  nombre: string
  clase: string
  forma: 'barra' | 'contorno' | 'linea' | 'linea-discontinua' | 'punto' | 'marca'
}

export function Leyenda({ series }: { series: SerieLeyenda[] }) {
  return (
    <ul className="leyenda" aria-label="Leyenda">
      {series.map((s) => (
        <li key={s.nombre} className="leyenda__item">
          <svg width="22" height="12" aria-hidden="true" className={s.clase}>
            {s.forma === 'barra' && <rect x="5" y="1" width="12" height="10" rx="1" className="relleno" />}
            {s.forma === 'contorno' && <rect x="5.75" y="1.75" width="10.5" height="8.5" rx="1" className="contorno" />}
            {s.forma === 'linea' && <line x1="0" x2="22" y1="6" y2="6" className="trazo" />}
            {s.forma === 'linea-discontinua' && <line x1="0" x2="22" y1="6" y2="6" className="trazo trazo--discontinuo" />}
            {s.forma === 'punto' && <circle cx="11" cy="6" r="4" className="relleno" />}
            {s.forma === 'marca' && <line x1="4" x2="18" y1="6" y2="6" className="trazo" />}
          </svg>
          {s.nombre}
        </li>
      ))}
    </ul>
  )
}

interface FiguraProps {
  id: string
  numero: number
  titulo: string
  /** Una frase llana: qué mirar en la gráfica. */
  lectura: ReactNode
  leyenda?: SerieLeyenda[]
  tabla?: { columnas: string[]; filas: (string | number)[][] }
  children: ReactNode
}

/** Figura de informe técnico: número, título, lectura, gráfica, tabla de datos plegada. */
export function Figura({ id, numero, titulo, lectura, leyenda, tabla, children }: FiguraProps) {
  return (
    <figure className="figura" aria-labelledby={`${id}-t`}>
      <h3 className="figura__titulo" id={`${id}-t`}>
        <span className="figura__num">Fig. {numero}</span> {titulo}
      </h3>
      <p className="figura__lectura">{lectura}</p>
      {leyenda && <Leyenda series={leyenda} />}
      {children}
      {tabla && (
        <details className="figura__tabla">
          <summary>Ver los datos en tabla</summary>
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  {tabla.columnas.map((c) => (
                    <th key={c} scope="col">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tabla.filas.map((f, i) => (
                  <tr key={i}>
                    {f.map((c, j) =>
                      j === 0 ? (
                        <th key={j} scope="row">
                          {c}
                        </th>
                      ) : (
                        <td key={j}>{c}</td>
                      ),
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </figure>
  )
}

/** Caja de lectura que sigue al puntero. Se posiciona dentro del contenedor de la gráfica. */
export function Lectura({ x, y, ancho, children }: { x: number; y: number; ancho: number; children: ReactNode }) {
  const izquierda = x > ancho * 0.62
  return (
    <div
      className="lectura"
      role="status"
      style={{ left: izquierda ? undefined : x + 14, right: izquierda ? ancho - x + 14 : undefined, top: Math.max(0, y - 8) }}
    >
      {children}
    </div>
  )
}

/** Índice de banda bajo el puntero (meses, horas, desfases). */
export function useIndicePuntero(n: number, x0: number, x1: number) {
  const [i, setI] = useState<number | null>(null)
  const mover = (e: PointerEvent<SVGElement>) => {
    const caja = (e.currentTarget as SVGElement).getBoundingClientRect()
    const px = e.clientX - caja.left
    const k = Math.floor(((px - x0) / (x1 - x0)) * n)
    setI(k >= 0 && k < n ? k : null)
  }
  return { indice: i, setIndice: setI, mover, salir: () => setI(null) }
}

export const MARGEN = { t: 14, r: 16, b: 30, l: 46 }
