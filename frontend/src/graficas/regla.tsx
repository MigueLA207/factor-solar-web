import { useId } from 'react'
import { hay, leerSesgo, num, pct } from '../util/formato'
import { escala, marcas, marcasQueCubren, useAncho } from './base'

interface PropsRegla {
  /** Energía de ERA5 sin corregir en las horas del factor (kWh/m²) */
  era5: number | null
  /** Energía del sensor en las mismas horas (kWh/m²) */
  sensor: number | null
  /** (ERA5 − sensor) / sensor, en %: positivo = ERA5 se pasa, negativo = se queda corto (lo da la API) */
  sesgo: number | null
  /** Con sensor simulado el rótulo lo dice */
  simulado?: boolean
  /** "el año" o, con un año parcial, "los meses con datos" */
  periodo?: string
}

/**
 * Regla de corrección (la pieza propia de la app): la energía de ERA5 contra la del sensor sobre una regla
 * graduada. El tramo rayado es la diferencia entre las dos: lo que ERA5 pone de más (si se pasa) o lo que le
 * falta (si se queda corto); el factor la cierra.
 */
export function ReglaCorreccion({ era5, sensor, sesgo, simulado = false, periodo = 'el año' }: PropsRegla) {
  const [ref, ancho] = useAncho<HTMLDivElement>()
  const idRayado = 'rayado' + useId().replace(/[^a-zA-Z0-9_-]/g, '')
  if (!hay(era5) || !hay(sensor)) return <p className="nota">Sin datos suficientes para dibujar la regla.</p>
  const lectura = leerSesgo(sesgo)
  const max = Math.max(era5, sensor)
  const ticks = marcasQueCubren(0, max, ancho < 480 ? 4 : 8)
  const fin = ticks[ticks.length - 1]
  const x = escala(0, fin, 4, ancho - 34)
  const reglaY = 22
  const grosor = 20
  const yEra5 = 62
  const ySensor = 118
  const alto = ySensor + grosor + 8
  const sub = (ticks[1] - ticks[0]) / 5
  const nombreSensor = simulado ? 'Sensor simulado' : 'Sensor'
  const sobra = era5 >= sensor

  return (
    <div className="regla" ref={ref}>
      <svg
        width={ancho}
        height={alto}
        role="img"
        aria-label={`Energía ${periodo === 'el año' ? 'del año' : 'de los meses con datos'} en las horas del factor: ERA5 sin corregir ${num(era5)} kWh/m², ${nombreSensor.toLowerCase()} ${num(sensor)} kWh/m². ${lectura ? `ERA5 ${lectura.verbo}${lectura.magnitud ? ` ${pct(lectura.magnitud)}` : ''}.` : ''}`}
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
          kWh/m² en {periodo}
        </text>

        <text x={x(0)} y={yEra5 - 7} className="regla__rotulo">
          ERA5 sin corregir <tspan className="regla__valor">{num(era5)}</tspan>
        </text>
        <rect x={x(0) + 0.75} y={yEra5 + 0.75} width={Math.max(0, x(era5) - x(0) - 1.5)} height={grosor - 1.5} className="serie-era5 contorno regla__barra" />
        {/* Tramo rayado = diferencia entre ERA5 y el sensor. Si ERA5 se pasa, va dentro de la barra de ERA5 (el exceso);
            si se queda corto, continúa la barra de ERA5 hasta la del sensor (lo que le falta). */}
        <rect
          x={sobra ? x(sensor) : x(era5)}
          y={yEra5 + 0.75}
          width={Math.max(0, sobra ? x(era5) - x(sensor) - 0.75 : x(sensor) - x(era5) - 0.75)}
          height={grosor - 1.5}
          className="regla__exceso"
          fill={`url(#${idRayado})`}
        />

        <text x={x(0)} y={ySensor - 7} className="regla__rotulo">
          {nombreSensor} = ERA5 × factor <tspan className="regla__valor">{num(sensor)}</tspan>
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
  const x = escala(ticks[0], ticks[ticks.length - 1], 24, ancho - 24)
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
