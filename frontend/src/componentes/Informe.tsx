import type { Celda, Resultado } from '../api/tipos'
import { Figura } from '../graficas/base'
import { GraficaDesfase, GraficaDiaTipico, GraficaEnergiaMensual, GraficaFactorMensual } from '../graficas/graficas'
import { EscalaSimulacion, ReglaCorreccion } from '../graficas/regla'
import { MESES_LARGOS, coord, leerCorrelacion, num, pct } from '../util/formato'
import { useAsentar } from '../util/movimiento'

interface Props {
  r: Resultado
  urlDescarga: string | null
  esDemo: boolean
}

const signo = (x: number) => (x > 0 ? '+' : '')
const celda = (c: Celda) =>
  `${coord(c.lat, 'lat')} · ${coord(c.lon, 'lon')}${c.elevacion_m != null ? ` · ${num(c.elevacion_m)} m` : ''}`

export function Informe({ r, urlDescarga, esDemo }: Props) {
  const e5 = r.factores.era5
  const anual = e5.anual
  const factorVisto = useAsentar(anual.factor)
  const cc = r.consistencia.era5_vs_nasa
  const nasa = r.factores.nasa.anual
  const paresDesfase = r.desfase.pares['sensor vs ERA5'] ?? Object.values(r.desfase.pares)[0] ?? []
  const mejorSensor = r.desfase.mejor_desfase_h['sensor vs ERA5'] ?? 0
  const mejorNasa = r.desfase.mejor_desfase_h['ERA5 vs NASA']
  const conVerdadero = r.simulado && anual.factor_verdadero != null
  const fases = r.fases_bimodal?.era5 ?? null

  return (
    <section className="informe" aria-labelledby="titulo-informe">
      <header className="informe__cabeza">
        <div>
          <h2 id="titulo-informe" className="seccion__titulo">
            Informe del sitio{r.sitio.nombre ? `: ${r.sitio.nombre}` : ''}
          </h2>
          <p className="informe__meta cifra">
            {coord(r.sitio.lat, 'lat')} · {coord(r.sitio.lon, 'lon')} · año {r.anio} · {r.simulado ? 'sensor simulado' : 'datos subidos por el usuario'}, por {r.frecuencia_sensor}
          </p>
          <p className="informe__celdas cifra">
            Celda ERA5 {celda(r.sitio.celda_era5)} <span aria-hidden="true">·</span> punto NASA {celda(r.sitio.celda_nasa)}
          </p>
        </div>
        <div className="informe__acciones">
          {urlDescarga ? (
            <a className="boton boton--secundario" href={urlDescarga} download>
              Descargar resultados (ZIP)
            </a>
          ) : (
            <span className="boton boton--secundario" aria-disabled="true" title="En modo demostración no hay archivo que descargar.">
              Descargar resultados (ZIP)
            </span>
          )}
        </div>
      </header>

      {r.simulado && (
        <div className="simulado" role="note" aria-label="Aviso: resultado simulado">
          <p className="simulado__sello">{r.etiqueta_sensor || 'SIMULADO'}</p>
          <div className="simulado__texto">
            <p className="simulado__frase">
              El sensor de este informe no existe: se fabricó a partir del clima de este punto. El factor sirve para comprobar que el método funciona; no es una medición del sitio ni sirve para cotizar.
            </p>
            {r.supuestos.length > 0 && (
              <>
                <p className="simulado__subtitulo">Supuestos de la simulación</p>
                <ol className="simulado__supuestos">
                  {r.supuestos.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
              </>
            )}
          </div>
        </div>
      )}

      {!r.simulado && (
        <div className="simulado simulado--usuario" role="note" aria-label="Aviso: datos subidos por el usuario">
          <p className="simulado__sello">Datos del usuario</p>
          <div className="simulado__texto">
            <p className="simulado__frase">
              Los datos del sensor son los del CSV que subiste. La app los limpia y los compara con ERA5 y NASA, pero no puede comprobar que vengan de un sensor real: el factor vale lo que valgan esos datos.
            </p>
          </div>
        </div>
      )}

      {r.advertencias.length > 0 && (
        <ul className="advertencias">
          {r.advertencias.map((a) => (
            <li key={a} className="aviso">
              {a}
            </li>
          ))}
        </ul>
      )}

      <div className="hallazgo">
        <div className="hallazgo__factor">
          <h3 className="hallazgo__titulo">Factor de corrección de ERA5</h3>
          <p className="hallazgo__numero cifra" aria-label={`Factor ${num(anual.factor, 4)}`}>
            {num(factorVisto, 4)}
          </p>
          <p className="hallazgo__formula">
            energía real <span aria-hidden="true">=</span>
            <span className="visualmente-oculto">igual a</span> ERA5 <span aria-hidden="true">×</span>
            <span className="visualmente-oculto">por</span> <span className="cifra">{num(anual.factor, 4)}</span>
          </p>
          <p className="hallazgo__frase">
            Sin factor, ERA5 sobrestima la energía del año en <strong className="cifra">{pct(anual.sesgo_relativo_pct)}</strong>.
          </p>
          <p className="nota">
            ERA5 es un reanálisis: un modelo global que estima la radiación de cada hora. El factor compara su energía con la del sensor en las mismas{' '}
            <span className="cifra">{num(anual.n_horas)}</span> horas con sol.
          </p>
        </div>
        <div className="hallazgo__regla">
          <ReglaCorreccion era5={anual.suma_fuente_kwh_m2} sensor={anual.suma_sensor_kwh_m2} sesgo={anual.sesgo_relativo_pct} />
          <p className="nota">El tramo rayado es lo que ERA5 pone de más. Multiplicar por el factor lo recorta hasta la energía del sensor.</p>
        </div>
      </div>

      {conVerdadero && anual.factor_verdadero != null && (
        <div className="validacion">
          <div>
            <h3 className="bloque__titulo">¿El método recupera el factor verdadero?</h3>
            <p className="validacion__cifras">
              Recuperado <strong className="cifra">{num(anual.factor, 4)}</strong> · verdadero <strong className="cifra">{num(anual.factor_verdadero, 4)}</strong>
              {anual.error_abs != null && (
                <>
                  {' '}
                  · error absoluto <strong className="cifra">{num(anual.error_abs, 4)}</strong>
                </>
              )}
            </p>
            <p className="nota">
              Como el sensor es simulado, se conoce el factor con el que se fabricó (el verdadero). Si el pipeline lo vuelve a encontrar, el cálculo está bien armado.
            </p>
          </div>
          <EscalaSimulacion recuperado={anual.factor} verdadero={anual.factor_verdadero} />
        </div>
      )}

      {fases && fases.length > 0 && (
        <div className="bimodal">
          <h3 className="bloque__titulo">Factor por fase del régimen bimodal</h3>
          <p className="nota">En los Andes colombianos el año tiene dos temporadas secas y dos de lluvias; cada una tiene su propio factor.</p>
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th scope="col">Fase</th>
                  <th scope="col" className="num">Factor</th>
                  <th scope="col" className="num">ERA5 se pasa</th>
                  {r.simulado && <th scope="col" className="num">Verdadero</th>}
                  <th scope="col" className="num">Horas con sol</th>
                </tr>
              </thead>
              <tbody>
                {fases.map((f) => (
                  <tr key={f.periodo}>
                    <th scope="row">{f.etiqueta ?? f.periodo}</th>
                    <td className="cifra num">{num(f.factor, 4)}</td>
                    <td className="cifra num">{pct(f.sesgo_relativo_pct)}</td>
                    {r.simulado && <td className="cifra num">{f.factor_verdadero == null ? '—' : num(f.factor_verdadero, 4)}</td>}
                    <td className="cifra num">{num(f.n_horas)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="figuras">
        <Figura
          id="fig-factor"
          numero={1}
          titulo="Factor mensual"
          lectura="Cada punto es el factor de un mes. Cuanto más abajo de la línea 1,00, más se pasa ERA5 ese mes."
          leyenda={[
            { nombre: 'Factor del mes', clase: 'serie-tinta', forma: 'punto' },
            { nombre: `Factor anual ${num(anual.factor, 4)}`, clase: 'serie-tinta', forma: 'linea' },
            ...(conVerdadero ? [{ nombre: 'Factor verdadero (simulación)', clase: 'serie-verdadero', forma: 'marca' as const }] : []),
          ]}
          tabla={{
            columnas: conVerdadero ? ['Mes', 'Factor', 'Verdadero', 'Horas con sol'] : ['Mes', 'Factor', 'Horas con sol'],
            filas: e5.mensual.map((d) => {
              const mes = d.mes ? MESES_LARGOS[d.mes - 1] : d.periodo
              return conVerdadero
                ? [mes, num(d.factor, 4), d.factor_verdadero == null ? '—' : num(d.factor_verdadero, 4), num(d.n_horas)]
                : [mes, num(d.factor, 4), num(d.n_horas)]
            }),
          }}
        >
          <GraficaFactorMensual datos={e5.mensual} anual={anual.factor} />
        </Figura>

        <Figura
          id="fig-energia"
          numero={2}
          titulo="Energía mensual"
          lectura="La barra rellena de ERA5 × factor debe quedar casi a la altura de la del sensor."
          leyenda={[
            { nombre: 'ERA5 sin corregir', clase: 'serie-era5', forma: 'contorno' },
            { nombre: 'ERA5 × factor', clase: 'serie-era5', forma: 'barra' },
            { nombre: 'Sensor', clase: 'serie-sensor', forma: 'barra' },
          ]}
          tabla={{
            columnas: ['Mes', 'ERA5 sin corregir (kWh/m²)', 'ERA5 × factor (kWh/m²)', 'Sensor (kWh/m²)', 'NASA (kWh/m²)'],
            filas: r.energia_mensual.map((d) => [
              MESES_LARGOS[d.mes - 1],
              num(d.era5_sin_corregir_kwh_m2, 1),
              num(d.era5_por_factor_kwh_m2, 1),
              num(d.sensor_kwh_m2, 1),
              d.nasa_kwh_m2 == null ? '—' : num(d.nasa_kwh_m2, 1),
            ]),
          }}
        >
          <GraficaEnergiaMensual datos={r.energia_mensual} />
        </Figura>

        <Figura
          id="fig-dia"
          numero={3}
          titulo="Día típico"
          lectura="Promedio de cada hora del día en el año, en hora solar aproximada (estimada con la longitud). Las tres curvas deben salir y ponerse con el sol a la vez."
          leyenda={[
            { nombre: 'Sensor', clase: 'serie-sensor', forma: 'linea' },
            { nombre: 'ERA5', clase: 'serie-era5', forma: 'linea' },
            { nombre: 'NASA POWER', clase: 'serie-nasa', forma: 'linea-discontinua' },
          ]}
          tabla={{
            columnas: ['Hora solar aprox.', 'Sensor (W/m²)', 'ERA5 (W/m²)', 'NASA (W/m²)'],
            filas: r.dia_tipico.map((d) => [
              `${d.hora_local}:00`,
              d.sensor == null ? '—' : num(d.sensor),
              d.era5 == null ? '—' : num(d.era5),
              d.nasa == null ? '—' : num(d.nasa),
            ]),
          }}
        >
          <GraficaDiaTipico datos={r.dia_tipico} />
        </Figura>

        <Figura
          id="fig-desfase"
          numero={4}
          titulo="Chequeo de desfase"
          lectura={
            <>
              Se corre el sensor hora por hora y se mide cuánto se parece a ERA5 (correlación).{' '}
              {mejorSensor === 0
                ? 'El máximo cae en 0 h: los relojes están alineados.'
                : `El máximo cae en ${signo(mejorSensor)}${mejorSensor} h: revisa la zona horaria del sensor.`}
              {mejorNasa != null && ` Entre ERA5 y NASA el máximo cae en ${signo(mejorNasa)}${mejorNasa} h.`}
            </>
          }
          tabla={{
            columnas: ['Corrimiento (h)', 'Correlación sensor–ERA5'],
            filas: paresDesfase.map((p) => [`${signo(p.desfase_h)}${p.desfase_h}`, num(p.correlacion, 4)]),
          }}
        >
          <GraficaDesfase puntos={paresDesfase} mejor={mejorSensor} />
        </Figura>
      </div>

      <div className="anexos">
        <section className="anexo" aria-labelledby="t-cruzado">
          <h3 id="t-cruzado" className="bloque__titulo">
            Chequeo cruzado: ERA5 contra NASA POWER
          </h3>
          <dl className="datos">
            <div>
              <dt>Parecido hora a hora</dt>
              <dd className="cifra">{num(cc.correlacion, 3)}</dd>
              <dd className="datos__nota">Correlación: 1 sería idéntico. Aquí {leerCorrelacion(cc.correlacion)}.</dd>
            </div>
            <div>
              <dt>Diferencia en energía del año</dt>
              <dd className="cifra">
                {signo(cc.diferencia_total_pct)}
                {pct(cc.diferencia_total_pct, 2)}
              </dd>
              <dd className="datos__nota">
                ERA5 {num(cc.suma_a_kwh_m2)} contra NASA {num(cc.suma_b_kwh_m2)} kWh/m², en {num(cc.n_horas)} horas comunes.
              </dd>
            </div>
          </dl>
          {cc.conclusion && <p className="nota">{cc.conclusion}</p>}
          <p className="nota">
            Con NASA en lugar de ERA5 el factor sería <span className="cifra">{num(nasa.factor, 4)}</span> (NASA se pasa{' '}
            <span className="cifra">{pct(nasa.sesgo_relativo_pct)}</span>). NASA solo se usa como chequeo, no para cotizar.
          </p>
        </section>

        <section className="anexo" aria-labelledby="t-integracion">
          <h3 id="t-integracion" className="bloque__titulo">
            Integración: cómo se unieron las fuentes
          </h3>
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th scope="col">Unión</th>
                  <th scope="col" className="num">Horas unidas</th>
                  <th scope="col" className="num">Coinciden</th>
                  <th scope="col" className="num">Sin cruce</th>
                </tr>
              </thead>
              <tbody>
                {r.linaje.map((l) => (
                  <tr key={l.paso}>
                    <th scope="row">
                      {l.fuentes_unidas}
                      <span className="tabla__sub">
                        por {l.llave}; {l.detalle_sin_cruce}
                      </span>
                    </th>
                    <td className="cifra num">{num(l.filas_resultado)}</td>
                    <td className="cifra num">{pct(l.pct_coincidencia)}</td>
                    <td className="cifra num">{num(l.llaves_sin_cruce)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="nota">
            NASA entrega la hora en hora solar local; se corrió <span className="cifra">{signo(r.desfase.desfase_nasa_aplicado_h)}{r.desfase.desfase_nasa_aplicado_h}</span> h para llevarla a UTC, y{' '}
            <span className="cifra">{num(r.desfase.horas_nasa_fuera_del_anio)}</span> horas de NASA quedaron fuera del año. {r.desfase.regla_nasa}
          </p>
        </section>

        <section className="anexo anexo--ancho" aria-labelledby="t-calidad">
          <h3 id="t-calidad" className="bloque__titulo">
            Calidad de los datos, antes y después de limpiar
          </h3>
          <p className="nota">
            Cada fila es una regla de calidad. «Antes» y «después» cuentan los registros que la incumplen.
            {r.simulado && ' «Inyectados» son los defectos que la simulación puso a propósito: la limpieza debe encontrarlos.'}
          </p>
          <div className="tabla-envoltura">
            <table className="tabla tabla--calidad">
              <thead>
                <tr>
                  <th scope="col">Fuente</th>
                  <th scope="col">Regla</th>
                  <th scope="col" className="num">Antes</th>
                  <th scope="col">Qué se hizo</th>
                  <th scope="col" className="num">Después</th>
                  {r.simulado && <th scope="col" className="num">Inyectados</th>}
                </tr>
              </thead>
              <tbody>
                {r.calidad.map((c, i) => (
                  <tr key={`${c.fuente}-${c.variable}-${i}`}>
                    <td>{c.fuente}</td>
                    <th scope="row">
                      {c.regla}
                      <span className="tabla__sub">
                        {c.variable} · {c.dimension}
                      </span>
                    </th>
                    <td className="cifra num">
                      {num(c.problemas_antes)}
                      <span className="tabla__sub">{pct(c.pct_antes, 3)}</span>
                    </td>
                    <td className="tabla__explica">{c.accion}</td>
                    <td className="cifra num">{num(c.problemas_despues)}</td>
                    {r.simulado && <td className="cifra num">{c.inyectados == null ? '—' : num(c.inyectados)}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="anexo anexo--ancho" aria-labelledby="t-fuentes">
          <h3 id="t-fuentes" className="bloque__titulo">
            De dónde sale cada dato
          </h3>
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th scope="col">Fuente</th>
                  <th scope="col">Origen</th>
                  <th scope="col" className="num">Filas</th>
                  <th scope="col">Llave de tiempo</th>
                  <th scope="col">Para qué sirve</th>
                </tr>
              </thead>
              <tbody>
                {r.fuentes.map((f) => (
                  <tr key={f.nombre}>
                    <th scope="row">{f.nombre}</th>
                    <td>{f.origen}</td>
                    <td className="cifra num">{num(f.filas)}</td>
                    <td>{f.llave}</td>
                    <td className="tabla__explica">{f.aporte}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {esDemo && <p className="aviso aviso--demo">Cifras de demostración generadas en el navegador (modo mock). Para un informe real, ejecuta la app con el backend.</p>}
    </section>
  )
}
