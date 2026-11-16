"""
Orquestación del análisis por etapas E -> T -> L para un sitio (lat, lon, año) y un sensor.

Cada etapa avisa su estado por un callback (avance) para que la web muestre el progreso en vivo.
El resultado es un dict listo para JSON más las tablas para el ZIP.
"""

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import calidad, extraccion, integracion, kpi, sol, transformacion
from .formato import coord, dec, miles, pct

ETAPAS = [
    ("E", "era5", "Extraer ERA5 (Open-Meteo, models=era5)"),
    ("E", "nasa", "Extraer NASA POWER (horario, comunidad RE)"),
    ("E", "sensor", "Leer el sensor"),
    ("T", "calidad_sensor", "Calidad del sensor"),
    ("T", "calidad_fuentes", "Calidad de ERA5 y NASA"),
    ("T", "hora_utc", "Llevar todo a hora UTC (NASA y sensor)"),
    ("T", "integracion", "Unir las tres fuentes por ts_utc"),
    ("T", "desfase", "Chequeo de desfase (correlación −8 a +8 h)"),
    ("L", "factores", "Factores de corrección"),
    ("L", "consistencia", "Consistencia entre fuentes"),
    ("L", "resumen", "Día típico y energía mensual"),
]


@dataclass
class Sensor:
    """Sensor listo para analizar: tabla cruda + metadatos."""
    crudo: pd.DataFrame                      # ts_utc, irr_sitio, t_modulo
    frecuencia: str = "minuto"               # "minuto" | "hora"
    simulado: bool = True
    verdadero: pd.DataFrame | None = None    # ts_utc, factor_verdadero (solo simulado)
    inyectados: dict | None = None           # defectos inyectados (solo simulado)
    supuestos: list = field(default_factory=list)
    tiene_temperatura: bool = True
    lat: float | None = None
    lon: float | None = None
    nombre: str | None = None


def limpiar_json(valor):
    # NaN -> None y tipos numpy -> tipos de Python.
    if isinstance(valor, dict):
        return {str(k): limpiar_json(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [limpiar_json(v) for v in valor]
    if isinstance(valor, (np.bool_,)):
        return bool(valor)
    if isinstance(valor, (np.integer,)):
        return int(valor)
    if isinstance(valor, (float, np.floating)):
        return None if math.isnan(valor) or math.isinf(valor) else float(valor)
    if isinstance(valor, pd.Timestamp):
        return valor.strftime("%Y-%m-%d %H:%M")
    return valor


def _nada(*_args, **_kwargs):
    return None


UNIDADES_FACTOR_MIN, UNIDADES_FACTOR_MAX = 0.5, 1.5
UNIDADES_MAXIMO_DIARIO_MIN_W_M2 = 50.0


def _confiabilidad(sensor, integrado, mejores, f_era5, advertencias):
    # Señales de que un CSV subido puede no ser confiable. Solo datos subidos: un sensor simulado se fabrica con
    # ERA5 y estas señales no tienen sentido.
    salida = {"factor_no_confiable": False, "motivo_no_confiable": None,
              "unidades_sospechosas": False, "motivo_unidades": None}
    if sensor.simulado:
        return salida
    mejor_sensor = mejores.get("sensor vs ERA5")
    if mejor_sensor not in (None, 0):
        salida["factor_no_confiable"] = True
        salida["motivo_no_confiable"] = (f"posible desfase de hora en el CSV: la correlación sensor–ERA5 es máxima con "
                                         f"{mejor_sensor:+d} h, no con 0 h")
    maximos_diarios = integrado.dropna(subset=["irr_sitio"]).groupby(integrado["ts_utc"].dt.floor("D"))["irr_sitio"].max()
    mediana_maximos = float(maximos_diarios.median()) if len(maximos_diarios) else None
    motivos = []
    if f_era5 is not None and (f_era5 < UNIDADES_FACTOR_MIN or f_era5 > UNIDADES_FACTOR_MAX):
        motivos.append(f"el factor anual ({dec(f_era5, 4)}) está fuera de {dec(UNIDADES_FACTOR_MIN, 1)}–{dec(UNIDADES_FACTOR_MAX, 1)}")
    if mediana_maximos is not None and mediana_maximos < UNIDADES_MAXIMO_DIARIO_MIN_W_M2:
        motivos.append(f"el máximo diario típico del sensor es de solo {dec(mediana_maximos, 1)} W/m²")
    if motivos:
        salida["unidades_sospechosas"] = True
        salida["motivo_unidades"] = "; ".join(motivos)
        advertencias.append("Revise las unidades del CSV (¿kW/m² o Wh en lugar de W/m²?): " + salida["motivo_unidades"] + ".")
    if salida["factor_no_confiable"]:
        advertencias.append("Factor no confiable: " + salida["motivo_no_confiable"] + ".")
    return salida


def ejecutar_analisis(lat, lon, anio, sensor, regimen=None, avance=_nada, crudos=None, nombre=None):
    """
    Corre el pipeline completo. `crudos` permite inyectar los textos crudos de las API
    ({"era5": texto_csv, "nasa": texto_json}) en vez de consultarlas (pruebas y prueba cruzada AE4).
    Devuelve (resultado_json, tablas) donde tablas es {nombre_archivo: DataFrame}.
    """
    crudos = crudos or {}
    advertencias = []

    # ---------------- [E] ----------------
    avance("era5", "en_curso", "Consultando…")
    if "era5" in crudos:
        texto_era5, origen_era5 = crudos["era5"], "copia de referencia"
    else:
        texto_era5, origen_era5 = extraccion.obtener_openmeteo(lat, lon, anio)
    era5_crudo = extraccion.leer_openmeteo(texto_era5)
    celda_era5 = extraccion.leer_celda_openmeteo(texto_era5)
    avance("era5", "listo", f"{miles(len(era5_crudo))} horas ({origen_era5}); celda ERA5 "
                            f"{dec(celda_era5['lat'], 2)}; {dec(celda_era5['lon'], 2)}")

    avance("nasa", "en_curso", "Consultando…")
    if "nasa" in crudos:
        texto_nasa, origen_nasa = crudos["nasa"], "copia de referencia"
    else:
        texto_nasa, origen_nasa = extraccion.obtener_nasa(lat, lon, anio)
    nasa_crudo = extraccion.leer_nasa(texto_nasa)
    cabecera_nasa = extraccion.leer_cabecera_nasa(texto_nasa)
    if cabecera_nasa["time_standard"] not in (None, "LST"):
        raise extraccion.ErrorFuente(f"NASA POWER devolvió la hora en {cabecera_nasa['time_standard']}, "
                                     "se esperaba LST (hora solar local).")
    avance("nasa", "listo", f"{miles(len(nasa_crudo))} horas en hora solar local ({origen_nasa})")

    avance("sensor", "en_curso", "")
    crudo = sensor.crudo[["ts_utc", "irr_sitio", "t_modulo"]].copy()
    crudo["irr_sitio"] = crudo["irr_sitio"].astype("float64")
    crudo["t_modulo"] = crudo["t_modulo"].astype("float64")
    avance("sensor", "listo", f"{miles(len(crudo))} registros por {sensor.frecuencia}"
           + (" — SIMULADO" if sensor.simulado else ""))

    # ---------------- [T] ----------------
    avance("calidad_sensor", "en_curso", "")
    limpio, detectados = calidad.limpiar_sensor(crudo, anio, lat, lon, sensor.frecuencia)
    filas_sensor, aviso = calidad.reporte_sensor(crudo, limpio, detectados, lat, lon, sensor.frecuencia,
                                                 sensor.inyectados, sensor.tiene_temperatura)
    if aviso:
        advertencias.append(aviso)
    corregidos = sum(f["problemas_antes"] for f in filas_sensor if f["dimension"] != "oportunidad")
    avance("calidad_sensor", "listo", f"{miles(corregidos)} problemas detectados y tratados")

    avance("calidad_fuentes", "en_curso", "")
    era5, filas_era5, aviso_era5 = calidad.limpiar_era5(era5_crudo, anio, lat, lon)
    # La regla de franjas de 15° se aplica a la longitud de la celda que NASA devolvió (cabecera), no a la pedida.
    lon_nasa = cabecera_nasa["lon"] if cabecera_nasa["lon"] is not None else lon
    nasa, filas_nasa, aviso_nasa = calidad.limpiar_nasa(nasa_crudo, lat, lon, sol.desfase_nasa_h(lon_nasa))
    advertencias += [a for a in (aviso_era5, aviso_nasa) if a]
    faltantes_nasa = int(filas_nasa[1]["problemas_antes"])
    avance("calidad_fuentes", "listo", f"ERA5 {miles(era5['irr_era5'].isna().sum())} vacíos; "
                                       f"NASA {miles(faltantes_nasa)} valores -999")

    avance("hora_utc", "en_curso", "")
    desfase_elegido, info_desfase = transformacion.elegir_desfase_nasa(era5, nasa, lon_nasa)
    if not info_desfase["coincide_con_regla"]:
        advertencias.append(
            f"La regla de longitud daba {info_desfase['por_longitud_h']:+d} h para NASA, pero la correlación con "
            f"ERA5 es mayor con {desfase_elegido:+d} h (punto cerca del borde de una franja de 15°); "
            f"se usó {desfase_elegido:+d} h.")
        # El conteo de luz de noche y la fila de calidad deben usar el corrimiento ELEGIDO, no el de la regla.
        nasa, filas_nasa, _ = calidad.limpiar_nasa(nasa_crudo, lat, lon, desfase_elegido)
    nasa_utc, desfase_nasa, horas_fuera = transformacion.pasar_nasa_a_utc(nasa, lon_nasa, anio, desfase_elegido)
    filas_nasa[-1]["regla"] = f"Hora en hora solar local (UTC{1 - desfase_elegido:+d}), no en UTC"
    filas_nasa[-1]["accion"] = f"se corre {desfase_elegido:+d} h a UTC (etiqueta al final de la hora)"
    if sensor.frecuencia == "minuto":
        sensor_hora = transformacion.agregar_sensor_a_hora(limpio, anio)
        texto_sensor = "sensor minuto → hora (H = promedio de (H-1, H], ≥48 min)"
    else:
        sensor_hora = transformacion.sensor_horario_a_calendario(limpio, anio)
        texto_sensor = "sensor ya viene por hora"
    avance("hora_utc", "listo", f"NASA hora solar local {desfase_nasa:+d} h → UTC; {texto_sensor}")

    avance("integracion", "en_curso", "")
    integrado, linaje = integracion.integrar_fuentes(sensor_hora, era5, nasa_utc, lat, lon)
    if sensor.verdadero is not None:
        integrado = integrado.merge(sensor.verdadero[["ts_utc", "factor_verdadero"]], on="ts_utc",
                                    how="left", validate="1:1")
    avance("integracion", "listo", f"{miles(len(integrado))} horas; {pct(linaje[0]['pct_coincidencia'])} sensor+ERA5, "
                                   f"{pct(linaje[1]['pct_coincidencia'])} +NASA")

    avance("desfase", "en_curso", "")
    tabla_desfase, mejores, avisos_desfase = transformacion.chequear_desfase(integrado)
    advertencias += avisos_desfase
    avance("desfase", "listo", ("ADVERTENCIA: " if avisos_desfase else "") + ", ".join(f"{par}: máximo en {m:+d} h" if m is not None else f"{par}: sin datos"
                     for par, m in mejores.items()))

    # ---------------- [L] ----------------
    avance("factores", "en_curso", "")
    factores = kpi.calcular_factores(integrado, regimen)
    f_era5 = factores["era5"]["anual"]["factor"]
    f_nasa = factores["nasa"]["anual"]["factor"]
    if f_era5 is None:
        raise ValueError("No hay horas diurnas con sensor y ERA5 a la vez: no se puede calcular el factor.")
    avance("factores", "listo", f"ERA5 {dec(f_era5, 4)} (cotización) · NASA "
                                f"{'—' if f_nasa is None else dec(f_nasa, 4)} (chequeo cruzado)")

    avance("consistencia", "en_curso", "")
    consistencia = kpi.calcular_consistencia(integrado)
    calentamiento = kpi.calcular_calentamiento(integrado)
    ch = consistencia["era5_vs_nasa"]
    avance("consistencia", "listo", f"ERA5 vs NASA: r = {'—' if ch['correlacion'] is None else dec(ch['correlacion'], 3)}, diferencia total "
                                    f"{'—' if ch['diferencia_total_pct'] is None else pct(ch['diferencia_total_pct'], 2, signo=True)}")

    avance("resumen", "en_curso", "")
    dia_tipico = kpi.calcular_dia_tipico(integrado, lon)
    energia = kpi.calcular_energia_mensual(integrado, f_era5)
    cobertura = kpi.calcular_cobertura(integrado)
    if not cobertura["anio_completo"]:
        advertencias.append(
            "Año parcial: el factor anual solo usa los meses con datos (" + ", ".join(cobertura["meses_con_datos"])
            + "); sin datos suficientes: " + ", ".join(cobertura["meses_sin_datos"]) + ". No es un factor de año completo.")
    confiabilidad = _confiabilidad(sensor, integrado, mejores, f_era5, advertencias)
    avance("resumen", "listo", "24 horas y 12 meses")

    if sensor.lat is not None and (abs(sensor.lat - lat) > 0.01 or abs(sensor.lon - lon) > 0.01):
        advertencias.append(f"El sensor se simuló/registró en ({coord(sensor.lat, sensor.lon)}) y el "
                            f"análisis se pidió en ({coord(lat, lon)}).")

    tabla_calidad = pd.DataFrame(filas_sensor + filas_era5 + filas_nasa)
    supuestos = list(sensor.supuestos) if sensor.simulado else []
    resultado = {
        "sitio": {"lat": lat, "lon": lon, "nombre": nombre or sensor.nombre,
                  "celda_era5": celda_era5,
                  "celda_nasa": {"lat": cabecera_nasa["lat"], "lon": cabecera_nasa["lon"],
                                 "elevacion_m": cabecera_nasa["elevacion_m"]},
                  "offset_hora_solar_local_h": 1 - desfase_nasa},
        "anio": anio,
        "simulado": sensor.simulado,
        "etiqueta_sensor": "SIMULADO" if sensor.simulado else "DATOS DEL USUARIO (CSV subido)",
        "supuestos": supuestos,
        "frecuencia_sensor": sensor.frecuencia,
        "fuentes": integracion.tabla_fuentes(crudo, era5_crudo, nasa_crudo, sensor.simulado,
                                             desfase_nasa, sensor.frecuencia),
        "calidad": tabla_calidad.to_dict(orient="records"),
        "linaje": linaje,
        "desfase": {
            "pares": {par: tabla_desfase[tabla_desfase["par"] == par][["desfase_h", "correlacion"]]
                      .to_dict(orient="records") for par in tabla_desfase["par"].unique()},
            "mejor_desfase_h": mejores,
            "desfase_nasa_aplicado_h": desfase_nasa,
            "horas_nasa_fuera_del_anio": horas_fuera,
            "verificacion_desfase_nasa": info_desfase,
            "regla_nasa": (f"NASA POWER entrega la hora en hora solar local (time_standard="
                           f"{cabecera_nasa['time_standard'] or 'LST'}), por franjas de 15° de longitud (se usó la "
                           f"longitud de la celda que devolvió NASA, {dec(lon_nasa, 4)}): UTC{1 - desfase_nasa:+d}. "
                           f"Se suma {desfase_nasa:+d} h: {desfase_nasa - 1:+d} h a UTC y +1 h porque NASA etiqueta "
                           "la hora por su inicio y Open-Meteo por su final. La regla round(lon/15) se contrastó con "
                           "ERA5 probando ±1 h y se quedó el corrimiento de mayor correlación: por eso este corrimiento "
                           "se ajustó contra ERA5 y la correlación ERA5–NASA no verifica la hora de forma independiente."),
            "era5_nasa_independiente": False,
            "sensor_era5_independiente": not sensor.simulado,
            "longitud_regla_nasa": lon_nasa,
            "ok": all(m == 0 for m in mejores.values()),
        },
        "factores": {
            "era5": {**factores["era5"], "nombre": "factor de cotización"},
            "nasa": {**factores["nasa"], "nombre": "chequeo cruzado"},
            "verdadero_anual": factores["era5"]["anual"]["factor_verdadero"] if sensor.simulado else None,
        },
        "consistencia": consistencia,
        "dia_tipico": dia_tipico,
        "cobertura": cobertura,
        "confiabilidad": confiabilidad,
        "energia_mensual": energia,
        "sesgo_era5_pct": factores["era5"]["anual"]["sesgo_relativo_pct"],
        "sesgo_nasa_pct": factores["nasa"]["anual"]["sesgo_relativo_pct"],
        "calentamiento_modulo_c": calentamiento,
        "advertencias": advertencias,
        "fuentes_api": {"era5": origen_era5, "nasa": origen_nasa,
                        "nasa_version": cabecera_nasa["version_api"], "nasa_origen": cabecera_nasa["fuentes"]},
    }
    if regimen == "bimodal_andino":
        resultado["fases_bimodal"] = {"era5": factores["era5"]["fases_bimodal"],
                                      "nasa": factores["nasa"]["fases_bimodal"]}

    tablas = {
        "integrado_horario.csv": integrado,
        "factores.csv": kpi.tabla_factores(factores),
        "calidad.csv": tabla_calidad,
        "linaje.csv": pd.DataFrame(linaje),
        "chequeo_desfase.csv": tabla_desfase,
        "consistencia.csv": pd.DataFrame([{"comparacion": k, **v} for k, v in consistencia.items()]),
        "dia_tipico.csv": pd.DataFrame(dia_tipico),
        "energia_mensual.csv": pd.DataFrame(energia),
        "fuentes.csv": pd.DataFrame(resultado["fuentes"]),
    }
    return limpiar_json(resultado), tablas
