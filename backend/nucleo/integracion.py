"""
[T] Integración: sensor horario + ERA5 + NASA sobre la llave ts_utc.

Copia adaptada de ae4/pipeline/src/integracion.py: misma unión left con validate="1:1" e
indicator=True sobre el calendario horario del sensor; las columnas de análisis dependen del sitio.
"""

import pandas as pd

from . import sol


def unir_por_hora(tabla_a, tabla_b):
    unida = pd.merge(tabla_a, tabla_b, on="ts_utc", how="left", validate="1:1", indicator=True)
    assert len(unida) == len(tabla_a), "la unión cambió el número de filas"
    return unida


def describir_horas(horas, maximo_tramos=6):
    # Convierte una lista de horas en tramos seguidos, por ejemplo "2024-01-01 00:00–05:00".
    horas = sorted(horas)
    tramos = []
    inicio = anterior = horas[0]
    for hora in horas[1:]:
        if hora - anterior != pd.Timedelta(hours=1):
            tramos.append((inicio, anterior))
            inicio = hora
        anterior = hora
    tramos.append((inicio, anterior))
    textos = []
    for inicio, fin in tramos[:maximo_tramos]:
        if inicio == fin:
            textos.append(f"{inicio:%Y-%m-%d %H:%M}")
        elif inicio.date() == fin.date():
            textos.append(f"{inicio:%Y-%m-%d %H:%M}–{fin:%H:%M}")
        else:
            textos.append(f"{inicio:%Y-%m-%d %H:%M}–{fin:%Y-%m-%d %H:%M}")
    if len(tramos) > maximo_tramos:
        textos.append(f"y {len(tramos) - maximo_tramos} tramos más")
    return ", ".join(textos)


def detalle_sin_cruce(nombre_a, nombre_b, solo_a, solo_b):
    partes = []
    if len(solo_a) > 0:
        partes.append(f"{len(solo_a)} h solo en {nombre_a}, sin {nombre_b}: {describir_horas(solo_a)} UTC")
    if len(solo_b) > 0:
        partes.append(f"{len(solo_b)} h solo en {nombre_b}, fuera del calendario: {describir_horas(solo_b)} UTC")
    if not partes:
        return "todas las horas cruzaron"
    return "; ".join(partes)


def fila_linaje(paso, nombre_a, nombre_b, tabla_a, tabla_b, unida):
    cruzaron = int((unida["_merge"] == "both").sum())
    solo_a = list(unida.loc[unida["_merge"] == "left_only", "ts_utc"])
    solo_b = list(tabla_b.loc[~tabla_b["ts_utc"].isin(tabla_a["ts_utc"]), "ts_utc"])
    return {
        "paso": paso,
        "fuentes_unidas": f"{nombre_a} + {nombre_b}",
        "llave": "ts_utc",
        "tipo_union": "left (validate 1:1)",
        "filas_entrada_A": len(tabla_a),
        "filas_entrada_B": len(tabla_b),
        "filas_resultado": len(unida),
        "pct_coincidencia": round(100 * cruzaron / len(tabla_a), 2),
        "columnas_resultado": unida.shape[1] - 1,
        "filas_si_inner": cruzaron,
        "filas_perdidas_inner": len(unida) - cruzaron,
        "llaves_sin_cruce": len(solo_a) + len(solo_b),
        "detalle_sin_cruce": detalle_sin_cruce(nombre_a, nombre_b, solo_a, solo_b),
    }


def unir_con_reporte(paso, nombre_a, nombre_b, tabla_a, tabla_b):
    unida = unir_por_hora(tabla_a, tabla_b)
    linaje = fila_linaje(paso, nombre_a, nombre_b, tabla_a, tabla_b, unida)
    return unida.drop(columns="_merge"), linaje


def integrar_fuentes(sensor_hora, era5, nasa_utc, lat, lon):
    # Paso 1: sensor + ERA5. Paso 2: (sensor + ERA5) + NASA. Ambos left sobre el calendario del sensor.
    paso1, linaje1 = unir_con_reporte(1, "sensor", "ERA5", sensor_hora, era5)
    paso2, linaje2 = unir_con_reporte(2, "sensor+ERA5", "NASA", paso1, nasa_utc)
    integrado = paso2
    integrado.insert(1, "mes", integrado["ts_utc"].dt.month)
    integrado.insert(2, "es_diurna", sol.marcar_horas_diurnas(integrado["ts_utc"], lat, lon))
    assert integrado["ts_utc"].is_unique, "la integración repitió horas"
    return integrado, [linaje1, linaje2]


def tabla_fuentes(sensor_crudo, era5_crudo, nasa_crudo, simulado, desfase_nasa_h, frecuencia):
    origen_sensor = "simulador (supuesto declarado)" if simulado else "CSV subido por el usuario"
    return [
        {"nombre": "Sensor en sitio" + (" (SIMULADO)" if simulado else ""), "origen": origen_sensor,
         "filas": len(sensor_crudo), "columnas": len(sensor_crudo.columns),
         "llave": f"ts_utc ({frecuencia}" + (" agregado a hora)" if frecuencia == "minuto" else ")"),
         "aporte": "irradiancia y temperatura del módulo en el sitio (numerador del factor)"},
        {"nombre": "Open-Meteo ERA5", "origen": "API Open-Meteo, models=era5",
         "filas": len(era5_crudo), "columnas": len(era5_crudo.columns),
         "llave": "ts_utc (ya viene en UTC)",
         "aporte": "irradiancia y temperatura del aire de la fuente gratuita (denominador del factor)"},
        {"nombre": "NASA POWER", "origen": "API NASA POWER horaria, comunidad RE",
         "filas": len(nasa_crudo), "columnas": len(nasa_crudo.columns),
         "llave": f"ts_utc (hora solar local {desfase_nasa_h:+d} h)",
         "aporte": "segunda fuente gratuita para el chequeo cruzado"},
    ]
