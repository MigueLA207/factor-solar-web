"""
[T] Calidad: reglas escritas como código, limpieza de cada fuente y reporte antes/después.

Copia adaptada de ae4/pipeline/src/calidad.py. Cambios:
- el sitio (lat, lon) y el año son argumentos; la noche se define con la elevación solar del sitio
  (también para NASA, en vez de "19:00 a 05:00 hora local", que solo vale cerca del ecuador);
- el sensor puede llegar por minuto o por hora (CSV subido); por hora no se interpola nada;
- "inyectados" es opcional: solo existe cuando el sensor es simulado;
- las etiquetas están en español llano para mostrarlas en la web.
"""

import numpy as np
import pandas as pd

from . import reglas, sol, transformacion


def porcentaje(parte, total):
    if total == 0:
        return 0.0
    return round(100 * parte / total, 3)


def fila_calidad(fuente, variable, dimension, regla, filas_antes, antes, accion,
                 despues, filas_despues, total, inyectados=None):
    return {"fuente": fuente, "variable": variable, "dimension": dimension, "regla": regla,
            "filas_antes": int(filas_antes), "problemas_antes": int(antes),
            "pct_antes": porcentaje(antes, total), "accion": accion,
            "problemas_despues": int(despues), "pct_despues": porcentaje(despues, total),
            "filas_despues": int(filas_despues),
            "inyectados": None if inyectados is None else int(inyectados)}


def aviso_filas_perdidas(fuente, filas_entrada, filas_salida):
    perdidas = filas_entrada - filas_salida
    if porcentaje(perdidas, filas_entrada) > reglas.PCT_ALERTA_FILAS_ELIMINADAS:
        return f"{fuente}: se eliminó el {porcentaje(perdidas, filas_entrada):.1f} % de las filas."
    return None


# ---------------------------------------------------------------------------
# Sensor
# ---------------------------------------------------------------------------

def calendario(anio, frecuencia):
    if frecuencia == "minuto":
        return transformacion.calendario_minutos(anio)
    return transformacion.calendario_horas(anio)


def revisar_estructura_sensor(crudo, anio, frecuencia):
    assert list(crudo.columns) == ["ts_utc", "irr_sitio", "t_modulo"], "columnas inesperadas"
    assert pd.api.types.is_datetime64_any_dtype(crudo["ts_utc"]), "ts_utc no es fecha"
    assert pd.api.types.is_float_dtype(crudo["irr_sitio"]), "irr_sitio no es numérica"
    assert pd.api.types.is_float_dtype(crudo["t_modulo"]), "t_modulo no es numérica"
    marcas = calendario(anio, frecuencia)
    assert crudo["ts_utc"].min() >= marcas[0], "hay registros antes del año"
    assert crudo["ts_utc"].max() <= marcas[-1], "hay registros después del año"


def elevacion_de_registro(ts_utc, lat, lon, frecuencia):
    # Por minuto: el sol en ese minuto. Por hora: el sol a mitad de (H-1, H].
    marcas = pd.DatetimeIndex(ts_utc)
    if frecuencia == "hora":
        marcas = marcas - pd.Timedelta(minutes=30)
    return sol.elevacion_solar(marcas, lat, lon)


def marcar_errores_sensor(sensor, lat, lon, frecuencia):
    irr = sensor["irr_sitio"]
    temp = sensor["t_modulo"]
    marcas = pd.DataFrame(index=sensor.index)
    marcas["nan_irradiancia"] = irr.isna()
    marcas["nan_temperatura"] = temp.isna()
    marcas["picos_irradiancia"] = irr > reglas.IRR_MAX
    marcas["negativos_nocturnos"] = (irr < 0) & (irr >= reglas.IRR_NEGATIVO_TOLERADO)
    marcas["negativos_invalidos"] = irr < reglas.IRR_NEGATIVO_TOLERADO
    marcas["temperatura_fuera_rango"] = (temp < reglas.T_MIN) | (temp > reglas.T_MAX)
    elevacion = elevacion_de_registro(sensor["ts_utc"], lat, lon, frecuencia)
    marcas["luz_de_noche"] = (elevacion < reglas.ELEVACION_NOCHE_PROFUNDA) & (irr > 0).to_numpy()
    return marcas


def corregir_valores_sensor(sensor, marcas):
    corregido = sensor.copy()
    a_vacio = marcas["picos_irradiancia"] | marcas["negativos_invalidos"]
    corregido.loc[a_vacio, "irr_sitio"] = np.nan
    corregido.loc[marcas["negativos_nocturnos"], "irr_sitio"] = 0.0
    corregido.loc[marcas["temperatura_fuera_rango"], "t_modulo"] = np.nan
    return corregido


def completar_calendario(sensor, anio, frecuencia):
    marcas = calendario(anio, frecuencia)
    completo = sensor.set_index("ts_utc").reindex(marcas)
    completo.index.name = "ts_utc"
    return completo.reset_index()


def interpolar_huecos_cortos(serie):
    # Interpola solo huecos de hasta 5 minutos seguidos; los más largos quedan vacíos.
    vacio = serie.isna()
    numero_de_hueco = (~vacio).cumsum()
    largo_del_hueco = vacio.groupby(numero_de_hueco).transform("sum")
    llenar = vacio & (largo_del_hueco <= reglas.HUECO_MAX_INTERPOLABLE_MIN)
    interpolada = serie.interpolate(limit_area="inside")
    return serie.where(~llenar, interpolada)


def validar_sensor_limpio(sensor, anio, frecuencia):
    marcas = calendario(anio, frecuencia)
    assert len(sensor) == len(marcas), f"se esperaban {len(marcas)} registros, hay {len(sensor)}"
    assert sensor["ts_utc"].is_unique, "ts_utc repetido"
    assert sensor["ts_utc"].is_monotonic_increasing, "ts_utc desordenado"
    irr = sensor["irr_sitio"].dropna()
    temp = sensor["t_modulo"].dropna()
    assert irr.between(reglas.IRR_MIN, reglas.IRR_MAX).all(), "irradiancia fuera de rango"
    assert temp.between(reglas.T_MIN, reglas.T_MAX).all(), "temperatura fuera de rango"


def limpiar_sensor(crudo, anio, lat, lon, frecuencia="minuto"):
    # Todas las reglas de calidad del sensor. Devuelve la tabla limpia y los conteos detectados.
    revisar_estructura_sensor(crudo, anio, frecuencia)
    duplicados = crudo["ts_utc"].duplicated(keep="last")
    sin_duplicados = crudo[~duplicados].sort_values("ts_utc")      # se conserva el último envío
    marcas = marcar_errores_sensor(sin_duplicados, lat, lon, frecuencia)

    limpio = corregir_valores_sensor(sin_duplicados, marcas)
    limpio = completar_calendario(limpio, anio, frecuencia)
    if frecuencia == "minuto":
        limpio["irr_sitio"] = interpolar_huecos_cortos(limpio["irr_sitio"])
        limpio["t_modulo"] = interpolar_huecos_cortos(limpio["t_modulo"])
    validar_sensor_limpio(limpio, anio, frecuencia)

    detectados = marcas.sum().astype(int).to_dict()
    detectados["timestamps_duplicados"] = int(duplicados.sum())
    detectados["registros_faltantes"] = len(limpio) - len(sin_duplicados)
    return limpio, detectados


def siguen_vacios(crudo, limpio, columna):
    llegaron_vacios = crudo.loc[crudo[columna].isna(), "ts_utc"].unique()
    limpio_por_marca = limpio.set_index("ts_utc")[columna]
    return int(limpio_por_marca.loc[llegaron_vacios].isna().sum())


def reporte_sensor(crudo, limpio, detectados, lat, lon, frecuencia="minuto", inyectados=None,
                   tiene_temperatura=True):
    inyectados = inyectados or {}
    entrada, salida = len(crudo), len(limpio)
    total = len(limpio)
    d = detectados
    despues = marcar_errores_sensor(limpio, lat, lon, frecuencia)
    unidad = "minuto" if frecuencia == "minuto" else "hora"
    interpola = ("se interpola si el hueco dura hasta 5 min" if frecuencia == "minuto"
                 else "se deja vacía (por hora no se interpola)")
    filas = [
        fila_calidad("sensor", "ts_utc", "unicidad", f"Registros repetidos (mismo {unidad})",
                     entrada, d["timestamps_duplicados"], "se conserva el último envío",
                     limpio["ts_utc"].duplicated().sum(), salida, total,
                     inyectados.get("timestamps_duplicados")),
        fila_calidad("sensor", "ts_utc", "oportunidad", f"Registros faltantes (el registrador no envió ese {unidad})",
                     entrada, d["registros_faltantes"],
                     ("se agrega el minuto vacío; huecos de hasta 5 min se interpolan; los cortes largos "
                      "quedan vacíos (después = minutos sin irradiancia)") if frecuencia == "minuto"
                     else "se agrega la hora vacía (después = horas sin irradiancia)",
                     limpio["irr_sitio"].isna().sum(), salida, total,
                     inyectados.get("minutos_faltantes")),
        fila_calidad("sensor", "irr_sitio", "completitud", "Irradiancia vacía",
                     entrada, d["nan_irradiancia"], interpola,
                     siguen_vacios(crudo, limpio, "irr_sitio"), salida, total,
                     inyectados.get("nan_irradiancia")),
    ]
    if tiene_temperatura:
        filas.append(fila_calidad("sensor", "t_modulo", "completitud", "Temperatura del módulo vacía",
                                  entrada, d["nan_temperatura"], interpola,
                                  siguen_vacios(crudo, limpio, "t_modulo"), salida, total,
                                  inyectados.get("nan_temperatura")))
    filas += [
        fila_calidad("sensor", "irr_sitio", "validez", "Valores imposibles (más de 1500 W/m²)",
                     entrada, d["picos_irradiancia"], "se vacían" + (" y luego se interpolan" if frecuencia == "minuto" else ""),
                     despues["picos_irradiancia"].sum(), salida, total,
                     inyectados.get("picos_irradiancia")),
        fila_calidad("sensor", "irr_sitio", "validez", "Negativos pequeños de noche (-10 a 0 W/m²)",
                     entrada, d["negativos_nocturnos"], "se llevan a 0 (offset del piranómetro)",
                     despues["negativos_nocturnos"].sum(), salida, total,
                     inyectados.get("negativos_nocturnos")),
    ]
    if tiene_temperatura:
        filas.append(fila_calidad("sensor", "t_modulo", "validez",
                                  f"Temperaturas imposibles (fuera de {reglas.T_MIN:.0f} a {reglas.T_MAX:.0f} °C)",
                                  entrada, d["temperatura_fuera_rango"], "se vacían",
                                  despues["temperatura_fuera_rango"].sum(), salida, total,
                                  inyectados.get("temperatura_fuera_rango")))
    filas += [
        fila_calidad("sensor", "irr_sitio", "validez", "Negativos grandes (menos de -10 W/m²)",
                     entrada, d["negativos_invalidos"], "se vacían",
                     despues["negativos_invalidos"].sum(), salida, total),
        fila_calidad("sensor", "irr_sitio", "consistencia", "Luz de noche (sol 15° bajo el horizonte)",
                     entrada, d["luz_de_noche"], "solo se reporta",
                     despues["luz_de_noche"].sum(), salida, total),
    ]
    return filas, aviso_filas_perdidas("sensor", entrada, salida)


# ---------------------------------------------------------------------------
# ERA5
# ---------------------------------------------------------------------------

def validar_tabla_horaria(tabla, llave, columna_irr, nombre):
    assert tabla[llave].is_unique, f"{nombre}: ts_utc repetido"
    valores = tabla[columna_irr].dropna()
    assert valores.between(reglas.IRR_MIN, reglas.IRR_MAX).all(), f"{nombre}: irradiancia fuera de rango"


def contar_luz_de_noche(horas_utc, irradiancia, lat, lon):
    elevacion = sol.elevacion_solar(pd.DatetimeIndex(horas_utc) - pd.Timedelta(minutes=30), lat, lon)
    return int(((elevacion < reglas.ELEVACION_NOCHE_PROFUNDA) & (irradiancia.to_numpy() > 0)).sum())


def limpiar_era5(era5, anio, lat, lon):
    horas = transformacion.calendario_horas(anio)
    duplicados = era5["ts_utc"].duplicated(keep="last")
    fuera_de_rango = (era5["irr_era5"] < reglas.IRR_MIN) | (era5["irr_era5"] > reglas.IRR_MAX)
    limpio = era5[~duplicados].copy()
    limpio.loc[fuera_de_rango[~duplicados], "irr_era5"] = np.nan
    validar_tabla_horaria(limpio, "ts_utc", "irr_era5", "ERA5")
    assert len(limpio) == len(horas), f"ERA5 debería tener {len(horas)} horas y tiene {len(limpio)}"

    entrada, salida = len(era5), len(limpio)
    total = len(horas)
    vacios = era5["irr_era5"].isna().sum()
    luz_de_noche = contar_luz_de_noche(limpio["ts_utc"], limpio["irr_era5"], lat, lon)
    filas = [
        fila_calidad("ERA5", "ts_utc", "unicidad", "Registros repetidos (misma hora)",
                     entrada, duplicados.sum(), "se conserva el último",
                     limpio["ts_utc"].duplicated().sum(), salida, total),
        fila_calidad("ERA5", "irr_era5", "completitud", "Irradiancia vacía",
                     entrada, vacios, "se deja vacía (sin imputar)",
                     limpio["irr_era5"].isna().sum(), salida, total),
        fila_calidad("ERA5", "irr_era5", "validez", "Valores imposibles (fuera de 0 a 1500 W/m²)",
                     entrada, fuera_de_rango.sum(), "se vacían", 0, salida, total),
        fila_calidad("ERA5", "irr_era5", "consistencia", "Luz de noche (sol 15° bajo el horizonte)",
                     entrada, luz_de_noche, "solo se reporta", luz_de_noche, salida, total),
        fila_calidad("ERA5", "ts_utc", "oportunidad", "Horas faltantes del año",
                     entrada, total - entrada, "consultar años ya publicados",
                     total - salida, salida, total),
    ]
    return limpio, filas, aviso_filas_perdidas("ERA5", entrada, salida)


# ---------------------------------------------------------------------------
# NASA POWER
# ---------------------------------------------------------------------------

def limpiar_nasa(nasa, lat, lon):
    # Reemplaza el código -999 por vacío; si se deja, entra a las sumas como si fuera medición.
    faltantes_irr = (nasa["irr_nasa"] == reglas.NASA_VALOR_FALTANTE).sum()
    faltantes_t = (nasa["t_aire_nasa"] == reglas.NASA_VALOR_FALTANTE).sum()
    duplicados = nasa["ts_lst"].duplicated(keep="last")
    limpio = nasa[~duplicados].replace(reglas.NASA_VALOR_FALTANTE, np.nan)
    validar_tabla_horaria(limpio, "ts_lst", "irr_nasa", "NASA")

    entrada, salida = len(nasa), len(limpio)
    desfase = sol.desfase_nasa_h(lon)
    horas_utc = limpio["ts_lst"] + pd.Timedelta(hours=desfase)
    luz_de_noche = contar_luz_de_noche(horas_utc, limpio["irr_nasa"], lat, lon)
    offset = sol.offset_lst_h(lon)
    filas = [
        fila_calidad("NASA", "ts_lst", "unicidad", "Registros repetidos (misma hora)",
                     entrada, duplicados.sum(), "se conserva el último",
                     limpio["ts_lst"].duplicated().sum(), salida, entrada),
        fila_calidad("NASA", "irr_nasa", "completitud", "Irradiancia sin dato (código -999)",
                     entrada, faltantes_irr, "el -999 se cambia por vacío (sin imputar)",
                     limpio["irr_nasa"].isna().sum(), salida, entrada),
        fila_calidad("NASA", "t_aire_nasa", "completitud", "Temperatura sin dato (código -999)",
                     entrada, faltantes_t, "el -999 se cambia por vacío (sin imputar)",
                     limpio["t_aire_nasa"].isna().sum(), salida, entrada),
        fila_calidad("NASA", "irr_nasa", "consistencia", "Luz de noche (sol 15° bajo el horizonte)",
                     entrada, luz_de_noche, "solo se reporta", luz_de_noche, salida, entrada),
        fila_calidad("NASA", "ts_lst", "consistencia",
                     f"Hora en hora solar local (UTC{offset:+d}), no en UTC",
                     entrada, entrada, f"se corre {desfase:+d} h a UTC (etiqueta al final de la hora)",
                     0, salida, entrada),
    ]
    return limpio, filas, aviso_filas_perdidas("NASA", entrada, salida)
