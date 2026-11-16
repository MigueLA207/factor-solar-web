import type { KeyboardEvent } from 'react'
import type { EnergiaMensual, FilaFactor, PuntoDesfase, PuntoDiaTipico } from '../api/tipos'
import { MESES_CORTOS, MESES_LARGOS, num } from '../util/formato'
import { Lectura, MARGEN, escala, marcas, useAncho, useIndicePuntero } from './base'

const ALTO = 250

/** Flechas izquierda/derecha recorren la gráfica con el teclado. */
function teclas(n: number, indice: number | null, set: (i: number | null) => void) {
  return (e: KeyboardEvent) => {
    if (e.key === 'ArrowRight') set(Math.min(n - 1, (indice ?? -1) + 1))
    else if (e.key === 'ArrowLeft') set(Math.max(0, (indice ?? n) - 1))
    else if (e.key === 'Escape') set(null)
    else return
    e.preventDefault()
  }
}

function EjeY({ ticks, y, ancho, fmt }: { ticks: number[]; y: (v: number) => number; ancho: number; fmt: (v: number) => string }) {
  return (
    <g className="eje">
      {ticks.map((t) => (
        <g key={t} transform={`translate(0 ${y(t)})`}>
          <line x1={MARGEN.l} x2={ancho - MARGEN.r} className="eje__guia" />
          <text x={MARGEN.l - 8} dy="0.32em" textAnchor="end">
            {fmt(t)}
          </text>
        </g>
      ))}
    </g>
  )
}

/* ------------------------------------------------------------------ */
/* Fig. Factor mensual: tallo desde 1,0 (ERA5 sin corregir) hasta el factor */

export function GraficaFactorMensual({ datos, anual }: { datos: FilaFactor[]; anual: number }) {
  const [ref, ancho] = useAncho<HTMLDivElement>()
  const x0 = MARGEN.l
  const x1 = ancho - MARGEN.r
  const banda = (x1 - x0) / datos.length
  const vals = datos.map((d) => d.factor)
  const verdaderos = datos.map((d) => d.factor_verdadero).filter((v): v is number => v != null)
  const yMin = Math.min(...vals, ...verdaderos, anual) - 0.03
  const yMax = Math.max(1.02, Math.max(...vals, ...verdaderos) + 0.02)
  const y = escala(yMin, yMax, ALTO - MARGEN.b, MARGEN.t)
  const { indice, setIndice, mover, salir } = useIndicePuntero(datos.length, x0, x1)
  const sel = indice != null ? datos[indice] : null
  const cx = (i: number) => x0 + banda * (i + 0.5)

  return (
    <div className="grafica" ref={ref}>
      <svg
        width={ancho}
        height={ALTO}
        role="img"
        aria-label={`Factor mensual de ${num(Math.min(...vals), 4)} a ${num(Math.max(...vals), 4)}; factor anual ${num(anual, 4)}. Use las flechas para leer cada mes.`}
        tabIndex={0}
        onPointerMove={mover}
        onPointerLeave={salir}
        onKeyDown={teclas(datos.length, indice, setIndice)}
        onBlur={salir}
      >
        <EjeY ticks={marcas(yMin, yMax, 4)} y={y} ancho={ancho} fmt={(v) => num(v, 2)} />
        <line x1={x0} x2={x1} y1={y(1)} y2={y(1)} className="referencia" />
        <text x={x1} y={y(1) - 6} textAnchor="end" className="anotacion">
          1,00 = ERA5 sin corregir
        </text>
        <line x1={x0} x2={x1} y1={y(anual)} y2={y(anual)} className="referencia referencia--anual" />
        {sel && indice != null && <rect x={x0 + banda * indice} y={MARGEN.t} width={banda} height={ALTO - MARGEN.t - MARGEN.b} className="foco-banda" />}
        {datos.map((d, i) => {
          // El tallo mide "cuánto se pasa ERA5": va de la línea 1,00 al punto del mes y termina en él.
          const yPunto = y(d.factor)
          const r = indice === i ? 6 : 4.5
          const fin = yPunto + (yPunto > y(1) ? -r : r)
          return (
            <g key={d.periodo} className="tallo">
              {Math.abs(yPunto - y(1)) > r && <line x1={cx(i)} x2={cx(i)} y1={y(1)} y2={fin} />}
              {d.factor_verdadero != null && (
                // Muesca del factor verdadero a la derecha del tallo, sin cruzarlo ni taparse con el punto.
                <line x1={cx(i) + 7} x2={cx(i) + 17} y1={y(d.factor_verdadero)} y2={y(d.factor_verdadero)} className="tallo__verdadero" />
              )}
              <circle cx={cx(i)} cy={yPunto} r={r} />
            </g>
          )
        })}
        <g className="eje">
          {datos.map((d, i) => (
            <text key={d.periodo} x={cx(i)} y={ALTO - 10} textAnchor="middle">
              {ancho < 480 ? d.periodo[0].toUpperCase() : d.periodo}
            </text>
          ))}
        </g>
      </svg>
      {sel && indice != null && (
        <Lectura x={cx(indice)} y={y(sel.factor)} ancho={ancho}>
          <strong>{sel.mes ? MESES_LARGOS[sel.mes - 1] : sel.periodo}</strong>
          <span>factor {num(sel.factor, 4)}</span>
          {sel.factor_verdadero != null && <span>verdadero {num(sel.factor_verdadero, 4)}</span>}
          <span className="lectura__suave">{num(sel.n_horas)} horas con sol</span>
        </Lectura>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Fig. Energía mensual: tres barras por mes */

export function GraficaEnergiaMensual({ datos }: { datos: EnergiaMensual[] }) {
  const [ref, ancho] = useAncho<HTMLDivElement>()
  const x0 = MARGEN.l
  const x1 = ancho - MARGEN.r
  const banda = (x1 - x0) / datos.length
  const max = Math.max(...datos.flatMap((d) => [d.era5_sin_corregir_kwh_m2, d.sensor_kwh_m2, d.era5_por_factor_kwh_m2]))
  const ticks = marcas(0, max * 1.05, 4)
  const yMax = ticks[ticks.length - 1]
  const y = escala(0, yMax, ALTO - MARGEN.b, MARGEN.t)
  const hueco = 2
  const barra = Math.max(3, Math.min(14, (banda * 0.78 - hueco * 2) / 3))
  const grupo = barra * 3 + hueco * 2
  const { indice, setIndice, mover, salir } = useIndicePuntero(datos.length, x0, x1)
  const sel = indice != null ? datos[indice] : null
  const base = y(0)
  const bx = (i: number, k: number) => x0 + banda * i + (banda - grupo) / 2 + k * (barra + hueco)

  return (
    <div className="grafica" ref={ref}>
      <svg
        width={ancho}
        height={ALTO}
        role="img"
        aria-label="Energía mensual en kWh/m²: ERA5 sin corregir, ERA5 por el factor y sensor. Use las flechas para leer cada mes."
        tabIndex={0}
        onPointerMove={mover}
        onPointerLeave={salir}
        onKeyDown={teclas(datos.length, indice, setIndice)}
        onBlur={salir}
      >
        <EjeY ticks={ticks} y={y} ancho={ancho} fmt={(v) => num(v)} />
        {indice != null && <rect x={x0 + banda * indice} y={MARGEN.t} width={banda} height={ALTO - MARGEN.t - MARGEN.b} className="foco-banda" />}
        {datos.map((d, i) => (
          <g key={d.mes}>
            <rect className="serie-era5 contorno barra-crece" x={bx(i, 0) + 0.75} y={y(d.era5_sin_corregir_kwh_m2) + 0.75} width={barra - 1.5} height={Math.max(0, base - y(d.era5_sin_corregir_kwh_m2) - 0.75)} />
            <rect className="serie-era5 relleno barra-crece" x={bx(i, 1)} y={y(d.era5_por_factor_kwh_m2)} width={barra} height={base - y(d.era5_por_factor_kwh_m2)} />
            <rect className="serie-sensor relleno barra-crece" x={bx(i, 2)} y={y(d.sensor_kwh_m2)} width={barra} height={base - y(d.sensor_kwh_m2)} />
          </g>
        ))}
        <line x1={x0} x2={x1} y1={base} y2={base} className="eje__base" />
        <g className="eje">
          {datos.map((d, i) => (
            <text key={d.mes} x={x0 + banda * (i + 0.5)} y={ALTO - 10} textAnchor="middle">
              {ancho < 480 ? MESES_CORTOS[d.mes - 1][0].toUpperCase() : MESES_CORTOS[d.mes - 1]}
            </text>
          ))}
        </g>
      </svg>
      {sel && indice != null && (
        <Lectura x={x0 + banda * (indice + 0.5)} y={y(sel.era5_sin_corregir_kwh_m2)} ancho={ancho}>
          <strong>{MESES_LARGOS[sel.mes - 1]}</strong>
          <span>ERA5 sin corregir {num(sel.era5_sin_corregir_kwh_m2, 1)}</span>
          <span>ERA5 × factor {num(sel.era5_por_factor_kwh_m2, 1)}</span>
          <span>Sensor {num(sel.sensor_kwh_m2, 1)}</span>
          <span className="lectura__suave">kWh/m²</span>
        </Lectura>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Fig. Día típico: tres curvas por hora solar aproximada */

export function GraficaDiaTipico({ datos }: { datos: PuntoDiaTipico[] }) {
  const [ref, ancho] = useAncho<HTMLDivElement>()
  const x0 = MARGEN.l
  const x1 = ancho - MARGEN.r
  const x = escala(0, 23, x0, x1)
  const max = Math.max(...datos.flatMap((d) => [d.sensor ?? 0, d.era5 ?? 0, d.nasa ?? 0]))
  const ticks = marcas(0, max * 1.05, 4)
  const y = escala(0, ticks[ticks.length - 1], ALTO - MARGEN.b, MARGEN.t)
  const paso = (x1 - x0) / 23
  const { indice, setIndice, mover, salir } = useIndicePuntero(24, x0 - paso / 2, x1 + paso / 2)
  const sel = indice != null ? datos.find((d) => d.hora_local === indice) : null

  const trazo = (val: (d: PuntoDiaTipico) => number | null) => {
    let d = ''
    let corte = true
    for (const p of datos) {
      const v = val(p)
      if (v == null) {
        corte = true
        continue
      }
      d += `${corte ? 'M' : 'L'}${x(p.hora_local).toFixed(1)},${y(v).toFixed(1)}`
      corte = false
    }
    return d
  }
  const punto = (v: number | null, clase: string) =>
    sel && v != null ? <circle cx={x(sel.hora_local)} cy={y(v)} r={4.5} className={`${clase} relleno anillo`} /> : null
  const leer = (v: number | null) => (v == null ? 'sin dato' : num(v))

  return (
    <div className="grafica" ref={ref}>
      <svg
        width={ancho}
        height={ALTO}
        role="img"
        aria-label="Día típico: irradiancia media por hora solar aproximada del sensor, ERA5 y NASA POWER, en W/m². Use las flechas para leer cada hora."
        tabIndex={0}
        onPointerMove={mover}
        onPointerLeave={salir}
        onKeyDown={teclas(24, indice, setIndice)}
        onBlur={salir}
      >
        <EjeY ticks={ticks} y={y} ancho={ancho} fmt={(v) => num(v)} />
        {sel && <line x1={x(sel.hora_local)} x2={x(sel.hora_local)} y1={MARGEN.t} y2={ALTO - MARGEN.b} className="cruz" />}
        <path d={trazo((d) => d.nasa)} className="serie-nasa trazo trazo--discontinuo" />
        <path d={trazo((d) => d.era5)} className="serie-era5 trazo linea-dibuja" pathLength={1} />
        <path d={trazo((d) => d.sensor)} className="serie-sensor trazo linea-dibuja" pathLength={1} />
        {sel && (
          <g>
            {punto(sel.nasa, 'serie-nasa')}
            {punto(sel.era5, 'serie-era5')}
            {punto(sel.sensor, 'serie-sensor')}
          </g>
        )}
        <line x1={x0} x2={x1} y1={y(0)} y2={y(0)} className="eje__base" />
        <g className="eje">
          {[0, 3, 6, 9, 12, 15, 18, 21].map((h) => (
            <text key={h} x={x(h)} y={ALTO - 10} textAnchor="middle">
              {`${h} h`}
            </text>
          ))}
        </g>
      </svg>
      {sel && (
        <Lectura x={x(sel.hora_local)} y={y(Math.max(sel.era5 ?? 0, sel.sensor ?? 0))} ancho={ancho}>
          <strong>{sel.hora_local}:00, hora solar aprox.</strong>
          <span>Sensor {leer(sel.sensor)}</span>
          <span>ERA5 {leer(sel.era5)}</span>
          <span>NASA {leer(sel.nasa)}</span>
          <span className="lectura__suave">W/m²</span>
        </Lectura>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Fig. Chequeo de desfase: correlación por corrimiento en horas */

export function GraficaDesfase({ puntos, mejor }: { puntos: PuntoDesfase[]; mejor: number }) {
  const [ref, ancho] = useAncho<HTMLDivElement>()
  const alto = 220
  const x0 = MARGEN.l
  const x1 = ancho - MARGEN.r
  const banda = (x1 - x0) / puntos.length
  const yMin = Math.floor(Math.min(0, ...puntos.map((p) => p.correlacion)) * 4) / 4
  const ticks = marcas(yMin, 1, 4)
  const y = escala(yMin, 1, alto - MARGEN.b, MARGEN.t)
  const { indice, setIndice, mover, salir } = useIndicePuntero(puntos.length, x0, x1)
  const sel = indice != null ? puntos[indice] : null
  const barra = Math.min(22, banda * 0.62)

  return (
    <div className="grafica" ref={ref}>
      <svg
        width={ancho}
        height={alto}
        role="img"
        aria-label={`Correlación entre sensor y ERA5 al correr el sensor de ${puntos[0]?.desfase_h} a ${puntos[puntos.length - 1]?.desfase_h} horas. Máximo en ${mejor} h.`}
        tabIndex={0}
        onPointerMove={mover}
        onPointerLeave={salir}
        onKeyDown={teclas(puntos.length, indice, setIndice)}
        onBlur={salir}
      >
        <EjeY ticks={ticks} y={y} ancho={ancho} fmt={(v) => num(v, 2)} />
        {puntos.map((p, i) => {
          const esMax = p.desfase_h === mejor
          const cx = x0 + banda * (i + 0.5)
          const arriba = Math.min(y(p.correlacion), y(0))
          return (
            <g key={p.desfase_h}>
              <rect
                x={cx - barra / 2}
                y={arriba}
                width={barra}
                height={Math.abs(y(p.correlacion) - y(0))}
                className={`barra-crece ${esMax ? 'desfase--max' : 'desfase'} ${indice === i ? 'desfase--sel' : ''}`}
              />
              {esMax && (
                <text x={cx} y={y(p.correlacion) - 6} textAnchor="middle" className="anotacion anotacion--fuerte">
                  {num(p.correlacion, 3)}
                </text>
              )}
            </g>
          )
        })}
        <line x1={x0} x2={x1} y1={y(0)} y2={y(0)} className="eje__base" />
        <g className="eje">
          {puntos.map((p, i) =>
            (ancho < 480 ? p.desfase_h % 4 !== 0 : p.desfase_h % 2 !== 0) ? null : (
              <text key={p.desfase_h} x={x0 + banda * (i + 0.5)} y={alto - 10} textAnchor="middle">
                {p.desfase_h > 0 ? `+${p.desfase_h}` : p.desfase_h}
              </text>
            ),
          )}
        </g>
      </svg>
      {sel && indice != null && (
        <Lectura x={x0 + banda * (indice + 0.5)} y={y(Math.max(0, sel.correlacion))} ancho={ancho}>
          <strong>sensor corrido {sel.desfase_h > 0 ? `+${sel.desfase_h}` : sel.desfase_h} h</strong>
          <span>correlación {num(sel.correlacion, 3)}</span>
        </Lectura>
      )}
    </div>
  )
}
