import { useState, type ReactNode } from 'react'
import type { Celda, Resultado } from '../api/tipos'
import { Figura } from '../graficas/base'
import { GraficaDesfase, GraficaDiaTipico, GraficaEnergiaMensual, GraficaFactorMensual, horaDeIntervalo } from '../graficas/graficas'
import { EscalaSimulacion, ReglaCorreccion } from '../graficas/regla'
import { MESES_LARGOS, SIN_DATO, coord, hay, leerCorrelacion, leerSesgo, num, pct, signo } from '../util/formato'
import { useAsentar } from '../util/movimiento'

interface Props {
  r: Resultado
  urlDescarga: string | null
  esDemo: boolean
}

const celda = (c: Celda) =>
  `${coord(c.lat, 'lat')} · ${coord(c.lon, 'lon')}${c.elevacion_m != null ? ` · ${num(c.elevacion_m)} m` : ''}`

/** Avisos que el hallazgo ya muestra junto al número: no se repiten en la lista. */
const YA_EN_EL_HALLAZGO = ['Factor no confiable', 'Revise las unidades', 'Año parcial']

/** Anexo plegable: abierto en pantallas anchas y cerrado de entrada en pantallas angostas. */
function AnexoPlegable({ id, titulo, children }: { id: string; titulo: string; children: ReactNode }) {
  const [abierto] = useState(() => !(typeof window !== 'undefined' && window.matchMedia('(max-width: 560px)').matches))
  return (
    <details className="anexo anexo--ancho anexo--plegable" open={abierto} aria-labelledby={id}>
      <summary className="anexo__resumen">
        <h3 id={id} className="bloque__titulo">
          {titulo}
        </h3>
      </summary>
      {children}
    </details>
  )
}

/** Correlación ERA5–NASA con cada corrimiento candidato, ANTES de elegir: la evidencia del ajuste de NASA. */
function EvidenciaNasa({ r }: { r: Resultado }) {
  const v = r.desfase.verificacion_desfase_nasa
  if (!v) return null
  const filas = Object.entries(v.correlacion_por_candidato)
    .map(([k, c]) => ({ desfase: Number(k), c }))
    .sort((a, b) => a.desfase - b.desfase)
  return (
    <div className="evidencia" aria-labelledby="t-evidencia-nasa">
      <h4 id="t-evidencia-nasa" className="evidencia__titulo">
        Hora de NASA: lo que se comparó antes de elegir su corrimiento
      </h4>
      <div className="tabla-envoltura">
        <table className="tabla tabla--corta">
          <thead>
            <tr>
              <th scope="col">Corrimiento de NASA a UTC</th>
              <th scope="col" className="num">
                Correlación con ERA5
              </th>
              <th scope="col">Papel</th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => (
              <tr key={f.desfase} data-elegido={f.desfase === v.elegido_h}>
                <th scope="row" className="cifra">
                  {signo(f.desfase)}
                  {f.desfase} h
                </th>
                <td className="cifra num">{num(f.c, 4)}</td>
                <td>
                  {[f.desfase === v.por_longitud_h ? 'regla de longitud' : null, f.desfase === v.elegido_h ? 'elegido' : null].filter(Boolean).join(' · ') || SIN_DATO}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="nota">
        La regla de franjas de 15° da <span className="cifra">{signo(v.por_longitud_h)}{v.por_longitud_h} h</span>; se probó ±1 h contra ERA5 y se usó el de mayor correlación ({signo(v.elegido_h)}
        {v.elegido_h} h{v.coincide_con_regla ? ', igual a la regla' : ', distinto de la regla'}). Como el corrimiento se eligió mirando a ERA5, <strong>la coincidencia de hora entre ERA5 y NASA no es un chequeo independiente</strong>: solo descarta errores de más de 1 h.
      </p>
    </div>
  )
}

export function Informe({ r, urlDescarga, esDemo }: Props) {
  const e5 = r.factores.era5
  const anual = e5.anual
  const factorVisto = useAsentar(anual.factor)
  const cc = r.consistencia.era5_vs_nasa
  const nasa = r.factores.nasa.anual
  const paresDesfase = r.desfase.pares['sensor vs ERA5'] ?? Object.values(r.desfase.pares)[0] ?? []
  const mejorSensor = r.desfase.mejor_desfase_h['sensor vs ERA5'] ?? null
  const conVerdadero = r.simulado && anual.factor_verdadero != null
  const fases = r.fases_bimodal?.era5 ?? null
  const sim = r.simulado
  const sesgo = leerSesgo(anual.sesgo_relativo_pct)
  const sesgoNasa = leerSesgo(nasa.sesgo_relativo_pct)
  const parcial = r.cobertura ? !r.cobertura.anio_completo : false
  const periodo = parcial ? 'los meses con datos' : 'el año'
  const conf = r.confiabilidad
  const sensorNombre = sim ? 'del sensor simulado' : 'del sensor'
  const avisos = r.advertencias.filter((a) => !YA_EN_EL_HALLAZGO.some((p) => a.startsWith(p)) || !(conf || r.cobertura))

  return (
    <section className="informe" aria-labelledby="titulo-informe">
      <header className="informe__cabeza">
        <div>
          <h2 id="titulo-informe" className="seccion__titulo">
            Informe del sitio{r.sitio.nombre ? `: ${r.sitio.nombre}` : ''}
          </h2>
          <p className="informe__meta cifra">
            {coord(r.sitio.lat, 'lat')} · {coord(r.sitio.lon, 'lon')} · año {r.anio} · {sim ? 'sensor simulado' : 'datos subidos por el usuario'}, por {r.frecuencia_sensor}
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

      {sim && (
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

      {!sim && (
        <div className="simulado simulado--usuario" role="note" aria-label="Aviso: datos subidos por el usuario">
          <p className="simulado__sello">Datos del usuario</p>
          <div className="simulado__texto">
            <p className="simulado__frase">
              Los datos del sensor son los del CSV que subiste. La app los limpia y los compara con ERA5 y NASA, pero no puede comprobar que vengan de un sensor real: el factor vale lo que valgan esos datos.
            </p>
          </div>
        </div>
      )}

      {avisos.length > 0 && (
        <ul className="advertencias">
          {avisos.map((a) => (
            <li key={a} className="aviso">
              {a}
            </li>
          ))}
        </ul>
      )}

      <div className="hallazgo">
        <div className="hallazgo__factor">
          <div className="hallazgo__cabeza">
            <h3 className="hallazgo__titulo">
              {sim ? 'Factor de ERA5 con un sensor simulado' : 'Factor de corrección de ERA5'}
              {parcial ? ' (parcial)' : ''}
            </h3>
            {sim && (
              <p className="hallazgo__sello" role="note">
                {r.etiqueta_sensor || 'SIMULADO'}
              </p>
            )}
          </div>
          <p className="hallazgo__numero cifra" aria-label={`Factor ${num(anual.factor, 4)}`}>
            {num(factorVisto, 4)}
          </p>
          {conf?.factor_no_confiable && (
            <p className="hallazgo__alerta" role="alert">
              <strong>No confiable:</strong> {conf.motivo_no_confiable ?? 'posible desfase de hora en el CSV'}.
            </p>
          )}
          {parcial && r.cobertura && (
            <p className="hallazgo__alerta">
              <strong>Parcial:</strong> cobertura suficiente (≥ 50 % de horas diurnas) {r.cobertura.meses_con_datos.length ? `en ${r.cobertura.meses_con_datos.join(', ')}` : 'en ningún mes'}; poca o ninguna en {r.cobertura.meses_sin_datos.join(', ')}. El factor usa todas las horas comparables. No es un factor de año completo.
            </p>
          )}
          {conf?.unidades_sospechosas && (
            <p className="hallazgo__alerta">
              <strong>Revise las unidades del CSV</strong> (¿kW/m² o Wh en lugar de W/m²?): {conf.motivo_unidades}.
            </p>
          )}
          <p className="hallazgo__formula">
            energía {sensorNombre} <span aria-hidden="true">=</span>
            <span className="visualmente-oculto">igual a</span> ERA5 <span aria-hidden="true">×</span>
            <span className="visualmente-oculto">por</span> <span className="cifra">{num(anual.factor, 4)}</span>
          </p>
          {sesgo && sesgo.magnitud > 0 && (
            <p className="hallazgo__frase">
              {sim ? (
                <>
                  En esta simulación ERA5 {sesgo.verbo} <strong className="cifra">{pct(sesgo.magnitud)}</strong> (porque la simulación lo supone).
                </>
              ) : (
                <>
                  Sin factor, ERA5 {sesgo.verboSin} la energía de {periodo} en <strong className="cifra">{pct(sesgo.magnitud)}</strong> respecto de los datos subidos.
                </>
              )}
            </p>
          )}
          {sesgo && sesgo.magnitud === 0 && <p className="hallazgo__frase">ERA5 y {sim ? 'el sensor simulado' : 'el sensor'} suman lo mismo.</p>}
          <p className="nota">
            ERA5 es un reanálisis: un modelo global que estima la radiación de cada hora. El factor compara su energía con la {sensorNombre} en las mismas{' '}
            <span className="cifra">{num(anual.n_horas)}</span> horas diurnas.
          </p>
        </div>
        <div className="hallazgo__regla">
          <ReglaCorreccion era5={anual.suma_fuente_kwh_m2} sensor={anual.suma_sensor_kwh_m2} sesgo={anual.sesgo_relativo_pct} simulado={sim} periodo={periodo} />
          <p className="nota">
            {sesgo && !sesgo.sobre && sesgo.magnitud > 0
              ? 'El tramo rayado es lo que le falta a ERA5 para igualar la energía. Multiplicar por el factor la sube hasta la del sensor.'
              : 'El tramo rayado es lo que ERA5 pone de más. Multiplicar por el factor lo recorta hasta la energía del sensor.'}
          </p>
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
              Esto comprueba la coherencia interna del cálculo: que el pipeline devuelva el factor con el que se fabricó el sensor simulado. No mide el error real de ERA5: el sensor se inventó a partir de ERA5 con un supuesto.
            </p>
          </div>
          {hay(anual.factor) && <EscalaSimulacion recuperado={anual.factor} verdadero={anual.factor_verdadero} />}
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
                  <th scope="col" className="num">ERA5 frente al sensor</th>
                  {sim && <th scope="col" className="num">Verdadero</th>}
                  <th scope="col" className="num">Horas diurnas</th>
                </tr>
              </thead>
              <tbody>
                {fases.map((f) => {
                  const s = leerSesgo(f.sesgo_relativo_pct)
                  return (
                    <tr key={f.periodo}>
                      <th scope="row">{f.etiqueta ?? f.periodo}</th>
                      <td className="cifra num">{num(f.factor, 4)}</td>
                      <td className="cifra num">{s ? (s.magnitud === 0 ? 'igual' : `${s.verbo} ${pct(s.magnitud)}`) : SIN_DATO}</td>
                      {sim && <td className="cifra num">{f.factor_verdadero == null ? SIN_DATO : num(f.factor_verdadero, 4)}</td>}
                      <td className="cifra num">{num(f.n_horas)}</td>
                    </tr>
                  )
                })}
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
          lectura="Cada punto es el factor de un mes. Por debajo de 1,00, ERA5 se pasa ese mes; por encima de 1,00, ERA5 se queda corto. Un mes sin punto no tiene datos."
          leyenda={[
            { nombre: 'Factor del mes', clase: 'serie-tinta', forma: 'punto' },
            { nombre: `${parcial ? 'Factor de los meses con datos' : 'Factor anual'} ${num(anual.factor, 4)}`, clase: 'serie-tinta', forma: 'linea' },
            ...(conVerdadero ? [{ nombre: 'Factor verdadero (simulación)', clase: 'serie-verdadero', forma: 'marca' as const }] : []),
          ]}
          tabla={{
            columnas: conVerdadero ? ['Mes', 'Factor', 'Verdadero', 'Horas diurnas'] : ['Mes', 'Factor', 'Horas diurnas'],
            filas: e5.mensual.map((d) => {
              const mes = d.mes ? MESES_LARGOS[d.mes - 1] : d.periodo
              return conVerdadero
                ? [mes, num(d.factor, 4), d.factor_verdadero == null ? SIN_DATO : num(d.factor_verdadero, 4), num(d.n_horas)]
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
          lectura="La barra rellena de ERA5 × factor debe quedar casi a la altura de la del sensor. NASA aparece solo en la tabla y suma únicamente las horas en que NASA tiene dato."
          leyenda={[
            { nombre: 'ERA5 sin corregir', clase: 'serie-era5', forma: 'contorno' },
            { nombre: 'ERA5 × factor', clase: 'serie-era5', forma: 'barra' },
            { nombre: sim ? 'Sensor simulado' : 'Sensor', clase: 'serie-sensor', forma: 'barra' },
          ]}
          tabla={{
            columnas: ['Mes', 'ERA5 sin corregir (kWh/m²)', 'ERA5 × factor (kWh/m²)', 'Sensor (kWh/m²)', 'NASA (kWh/m²)', 'Horas con dato de NASA'],
            filas: r.energia_mensual.map((d) => [
              MESES_LARGOS[d.mes - 1],
              num(d.era5_sin_corregir_kwh_m2, 1),
              num(d.era5_por_factor_kwh_m2, 1),
              num(d.sensor_kwh_m2, 1),
              hay(d.nasa_kwh_m2) ? num(d.nasa_kwh_m2, 1) : SIN_DATO,
              `${num(d.nasa_n_horas)} de ${num(d.n_horas)}`,
            ]),
          }}
        >
          <GraficaEnergiaMensual datos={r.energia_mensual} />
        </Figura>

        <Figura
          id="fig-dia"
          numero={3}
          titulo="Día típico"
          lectura="Promedio de cada hora del día en el año, en hora solar aproximada (estimada con la longitud). Cada punto va en el centro de su hora: el dato de las 7 h es el promedio de 6:00 a 7:00 y se dibuja a las 6:30. Las tres curvas deben salir y ponerse con el sol a la vez."
          leyenda={[
            { nombre: sim ? 'Sensor simulado' : 'Sensor', clase: 'serie-sensor', forma: 'linea' },
            { nombre: 'ERA5', clase: 'serie-era5', forma: 'linea' },
            { nombre: 'NASA POWER', clase: 'serie-nasa', forma: 'linea-discontinua' },
          ]}
          tabla={{
            columnas: ['Hora solar aprox. (intervalo)', 'Sensor (W/m²)', 'ERA5 (W/m²)', 'NASA (W/m²)'],
            filas: r.dia_tipico.map((d) => [horaDeIntervalo(d.hora_centro), num(d.sensor), num(d.era5), num(d.nasa)]),
          }}
        >
          <GraficaDiaTipico datos={r.dia_tipico} />
        </Figura>

        <Figura
          id="fig-desfase"
          numero={4}
          titulo="Chequeo de desfase"
          lectura={
            sim ? (
              <>
                Sensor–ERA5: <strong>no informativo</strong>. El sensor simulado se fabricó con ERA5, así que su desfase con ERA5 es 0 h por construcción y no dice nada sobre ningún reloj real. El único chequeo independiente de la hora es sensor–ERA5 con datos subidos.
              </>
            ) : (
              <>
                Se corre el sensor hora por hora y se mide cuánto se parece a ERA5 (correlación). Es el único chequeo independiente de la hora, porque el sensor no sale de ERA5.{' '}
                {mejorSensor == null
                  ? 'No se pudo calcular el máximo.'
                  : mejorSensor === 0
                    ? 'El máximo cae en 0 h: no se ve desfase de reloj (la prueba resuelve 1 h).'
                    : `El máximo cae en ${signo(mejorSensor)}${mejorSensor} h: posible desfase de hora en el CSV; el factor no es confiable.`}
              </>
            )
          }
          tabla={
            sim
              ? undefined
              : {
                  columnas: ['Corrimiento (h)', 'Correlación sensor–ERA5'],
                  filas: paresDesfase.map((p) => [`${signo(p.desfase_h)}${p.desfase_h}`, num(p.correlacion, 4)]),
                }
          }
        >
          {sim ? (
            <div className="noinfo" role="note">
              <p className="noinfo__sello">No informativo</p>
              <p className="noinfo__texto">El sensor se fabricó con ERA5: la correlación sensor–ERA5 es máxima en 0 h por construcción. No se dibuja porque no prueba nada.</p>
            </div>
          ) : (
            <GraficaDesfase puntos={paresDesfase} mejor={mejorSensor} />
          )}
          <EvidenciaNasa r={r} />
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
              {hay(cc.correlacion) && <dd className="datos__nota">Correlación: 1 sería idéntico. Aquí {leerCorrelacion(cc.correlacion)}.</dd>}
            </div>
            <div>
              <dt>Diferencia en energía del año</dt>
              <dd className="cifra">
                {signo(cc.diferencia_total_pct)}
                {pct(cc.diferencia_total_pct, 2)}
              </dd>
              {hay(cc.suma_a_kwh_m2) && hay(cc.suma_b_kwh_m2) && (
                <dd className="datos__nota">
                  ERA5 {num(cc.suma_a_kwh_m2)} contra NASA {num(cc.suma_b_kwh_m2)} kWh/m², en {num(cc.n_horas)} horas comunes.
                </dd>
              )}
            </div>
          </dl>
          {cc.conclusion && <p className="nota">{cc.conclusion}</p>}
          {sim ? (
            <p className="nota">Con un sensor simulado no se muestra «el factor con NASA»: el sensor se fabricó con ERA5, así que ese número no mide nada de NASA.</p>
          ) : (
            hay(nasa.factor) && (
              <p className="nota">
                Con NASA en lugar de ERA5 el factor sería <span className="cifra">{num(nasa.factor, 4)}</span>
                {sesgoNasa && sesgoNasa.magnitud > 0 && (
                  <>
                    {' '}
                    (NASA {sesgoNasa.verbo} <span className="cifra">{pct(sesgoNasa.magnitud)}</span>)
                  </>
                )}
                . NASA solo se usa como chequeo, no para cotizar.
              </p>
            )
          )}
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

        <AnexoPlegable id="t-calidad" titulo="Calidad de los datos, antes y después de limpiar">
          <p className="nota">
            Cada fila es una regla de calidad. «Antes» y «después» cuentan los registros que la incumplen.
            {sim && ' «Inyectados» son los defectos que la simulación puso a propósito: la limpieza debe encontrarlos.'}
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
                  {sim && <th scope="col" className="num">Inyectados</th>}
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
                    {sim && <td className="cifra num">{c.inyectados == null ? SIN_DATO : num(c.inyectados)}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AnexoPlegable>

        <AnexoPlegable id="t-fuentes" titulo="De dónde sale cada dato">
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
        </AnexoPlegable>
      </div>

      {esDemo && <p className="aviso aviso--demo">Cifras de demostración generadas en el navegador (modo mock). Para un informe real, ejecuta la app con el backend.</p>}
    </section>
  )
}
