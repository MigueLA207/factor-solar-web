import { useId } from 'react'
import { num, pct } from '../util/formato'
import { escala, marcas, useAncho } from './base'

interface PropsRegla {
  /** Energía anual de ERA5 sin corregir en las horas del factor (kWh/m²) */
  era5: number
  /** Energía anual del sensor en las mismas horas (kWh/m²) */
  sensor: number
  /** Cuánto se pasa ERA5, en % (lo da la API) */
  sesgo: number
}

/**
 * Regla de corrección (la pieza propia de la app): la energía anual de ERA5 contra la del sensor
 * sobre una regla graduada. El tramo rayado es lo que ERA5 pone de más; el factor lo recorta.
 */
export function ReglaCorreccion({ era5, sensor, sesgo }: PropsRegla) {
  const [ref, ancho] = useAncho<HTMLDivElement>()
  const idRayado = 'rayado' + useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const max = Math.max(era5, sensor)
  const ticks = marcas(0, max * 1.04, ancho < 480 ? 4 : 8)
  const fin = ticks[ticks.length - 1]
  const x = escala(0, fin, 4, ancho - 18)
  const reglaY = 22
  const grosor = 20
  const yEra5 = 62
  const ySensor = 118
  const alto = ySensor + grosor + 8
  const sub = (ticks[1] - ticks[0]) / 5

  return (
    <div className="regla" ref={ref}>
      <svg
        width={ancho}
        height={alto}
        role="img"
        aria-label={`Energía anual en las horas del factor: ERA5 sin corregir ${num(era5)} kWh/m², sensor ${num(sensor)} kWh/m². ERA5 se pasa ${pct(sesgo)}.`}
      >
        <defs>
          <pattern id={idRayado} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" className="regla__raya" />
          </pattern>
        </defs>
        <line x1={x(0)} x2={x(fin)} y1={reglaY} y2={reglaY} className="regla__linea" />
        {ticks.map((t, i) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={reglaY} y2={reglaY - 9} className="regla__linea" />
            <text x={x(t)} y={reglaY - 13} textAnchor={i === 0 ? 'start' : 'middle'} className="regla__num">
              {num(t)}
            </text>
            {i < ticks.length - 1 &&
              [1, 2, 3, 4].map((k) => (
                <line key={k} x1={x(t + sub * k)} x2={x(t + sub * k)} y1={reglaY} y2={reglaY - 4} className="regla__linea regla__linea--fina" />
              ))}
          </g>
        ))}
        <text x={x(fin)} y={reglaY + 15} textAnchor="end" className="regla__unidad">
          kWh/m² en el año
        </text>

        <text x={x(0)} y={yEra5 - 7} className="regla__rotulo">
          ERA5 sin corregir <tspan className="regla__valor">{num(era5)}</tspan>
        </text>
        <rect x={x(0) + 0.75} y={yEra5 + 0.75} width={Math.max(0, x(era5) - x(0) - 1.5)} height={grosor - 1.5} className="serie-era5 contorno regla__barra" />
        <rect
          x={x(sensor)}
          y={yEra5 + 0.75}
          width={Math.max(0, x(era5) - x(sensor) - 0.75)}
          height={grosor - 1.5}
          className="regla__exceso"
          fill={`url(#${idRayado})`}
        />

        <text x={x(0)} y={ySensor - 7} className="regla__rotulo">
          Sensor = ERA5 × factor <tspan className="regla__valor">{num(sensor)}</tspan>
        </text>
        <rect x={x(0)} y={ySensor} width={Math.max(0, x(sensor) - x(0))} height={grosor} className="serie-sensor relleno regla__barra" />

        <line x1={x(sensor)} x2={x(sensor)} y1={yEra5 - 2} y2={ySensor + grosor} className="regla__corte" />
      </svg>
    </div>
  )
}

/** Factor recuperado contra factor verdadero de la simulación, sobre una escala corta. */
export function EscalaSimulacion({ recuperado, verdadero }: { recuperado: number; verdadero: number }) {
  const [ref, ancho] = useAncho<HTMLDivElement>()
  const a = Math.min(recuperado, verdadero)
  const b = Math.max(recuperado, verdadero)
  const margen = Math.max(0.01, (b - a) * 3)
  const ticks = marcas(a - margen, b + margen, 4)
  const x = escala(ticks[0], ticks[ticks.length - 1], 14, ancho - 14)
  const ly = 40
  return (
    <div className="escala-sim" ref={ref}>
      <svg width={ancho} height={84} role="img" aria-label={`Factor recuperado ${num(recuperado, 4)}, factor verdadero ${num(verdadero, 4)}.`}>
        <line x1={x(ticks[0])} x2={x(ticks[ticks.length - 1])} y1={ly} y2={ly} className="regla__linea" />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={ly} y2={ly + 6} className="regla__linea" />
            <text x={x(t)} y={ly + 34} textAnchor="middle" className="regla__num">
              {num(t, 3)}
            </text>
          </g>
        ))}
        <line x1={x(verdadero)} x2={x(verdadero)} y1={ly - 16} y2={ly} className="sim__verdadero" />
        <text x={x(verdadero)} y={ly - 20} textAnchor="middle" className="anotacion">
          verdadero
        </text>
        <circle cx={x(recuperado)} cy={ly} r={5.5} className="sim__recuperado" />
        <text x={x(recuperado)} y={ly + 20} textAnchor="middle" className="anotacion anotacion--sensor">
          recuperado
        </text>
      </svg>
    </div>
  )
}
