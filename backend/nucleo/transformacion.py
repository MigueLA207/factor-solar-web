"""
[T] Transformación: calendarios, hora de NASA a UTC, agregación del sensor de minuto a hora
y chequeo de desfase.

Copia adaptada de ae4/pipeline/src/transformacion.py. Cambios:
- el desfase NASA -> UTC se deriva de la longitud (sol.desfase_nasa_h), no es un 6 fijo;
- el chequeo de desfase ya no detiene el proceso: devuelve el mejor desfase y una advertencia.
"""

import pandas as pd

from . import reglas, sol


def calendario_minutos(anio):
    return pd.date_range(f"{anio}-01-01 00:00", f"{anio}-12-31 23:59", freq="min")


def calendario_horas(anio):
    # Todas las horas del año con la etiqueta de Open-Meteo (8.784 en un año bisiesto).
    return pd.date_range(f"{anio}-01-01 00:00", f"{anio}-12-31 23:00", freq="h")


def elegir_desfase_nasa(era5, nasa, lon):
    """
    Desfase LST -> UTC de NASA POWER. La regla es la de la documentación de POWER: la hora solar local
    sale de franjas de 15° de longitud -> offset = round(lon/15) y desfase = 1 - offset.
    En el borde de una franja la regla puede fallar por 1 h (ejemplo medido: Turín, lon 7,69, la regla da
    offset +1 pero NASA usó 0). Por eso se prueban la regla y sus vecinos (±1 h) contra ERA5 y se usa el de
    mayor correlación. Devuelve (desfase, info).
    """
    por_regla = sol.desfase_nasa_h(lon)
    correlaciones = {}
    base = era5.set_index("ts_utc")["irr_era5"]
    for candidato in (por_regla - 1, por_regla, por_regla + 1):
        corrida = nasa.set_index(nasa["ts_lst"] + pd.Timedelta(hours=candidato))["irr_nasa"]
        corrida = corrida[~corrida.index.duplicated()]
        unida = pd.concat([base, corrida.reindex(base.index)], axis=1).dropna()
        r = unida.iloc[:, 0].corr(unida.iloc[:, 1]) if len(unida) > 24 else float("nan")
        correlaciones[candidato] = None if pd.isna(r) else round(float(r), 4)
    validas = {k: v for k, v in correlaciones.items() if v is not None}
    elegido = max(validas, key=validas.get) if validas else por_regla
    info = {"por_longitud_h": por_regla, "elegido_h": elegido, "coincide_con_regla": elegido == por_regla,
            "correlacion_por_candidato": {f"{k:+d}": v for k, v in correlaciones.items()}}
    return elegido, info


def pasar_nasa_a_utc(nasa, lon, anio, desfase=None):
    # LST -> UTC con etiqueta al final de la hora. Se quitan las horas que caen fuera del año UTC
    # (vienen del día extra que se pide a cada lado). Devuelve (tabla, desfase_h, horas_fuera).
    if desfase is None:
        desfase = sol.desfase_nasa_h(lon)
    nasa_utc = nasa.copy()
    nasa_utc["ts_utc"] = nasa_utc["ts_lst"] + pd.Timedelta(hours=desfase)
    horas = calendario_horas(anio)
    dentro = nasa_utc["ts_utc"].between(horas[0], horas[-1])
    nasa_utc = nasa_utc[dentro][["ts_utc", "irr_nasa", "t_aire_nasa"]].reset_index(drop=True)
    return nasa_utc, desfase, int((~dentro).sum())


def agregar_sensor_a_hora(sensor_minuto, anio):
    # closed="right", label="right": la hora H promedia los minutos de (H-1, H] (convención Open-Meteo).
    serie = sensor_minuto.set_index("ts_utc")
    grupos = serie[["irr_sitio", "t_modulo"]].resample("h", closed="right", label="right")
    promedio = grupos.mean()
    minutos_validos = grupos.count()

    minimo = 60 * reglas.MIN_FRACCION_MINUTOS_HORA      # 48 de 60 minutos
    horario = pd.DataFrame(index=promedio.index)
    horario["irr_sitio"] = promedio["irr_sitio"].where(minutos_validos["irr_sitio"] >= minimo)
    horario["t_modulo"] = promedio["t_modulo"].where(minutos_validos["t_modulo"] >= minimo)
    horario["minutos_validos"] = minutos_validos["irr_sitio"]

    horario = horario.reindex(calendario_horas(anio))   # la última hora cae en el 1 de enero siguiente
    horario["minutos_validos"] = horario["minutos_validos"].fillna(0).astype("int64")
    horario.index.name = "ts_utc"
    return horario.reset_index()


def sensor_horario_a_calendario(sensor_hora, anio):
    # Sensor que ya llega por hora: solo se lleva al calendario del año. Se asume la misma
    # convención de Open-Meteo (la hora H es el promedio de (H-1, H]); el chequeo de desfase lo verifica.
    horario = sensor_hora.set_index("ts_utc")[["irr_sitio", "t_modulo"]].reindex(calendario_horas(anio))
    horario["minutos_validos"] = horario["irr_sitio"].notna().astype("int64") * 60
    horario.index.name = "ts_utc"
    return horario.reset_index()


def correlacion_con_desfase(serie_a, serie_b, horas):
    corrida = serie_b.shift(horas)
    ambas = serie_a.notna() & corrida.notna()
    return serie_a[ambas].corr(corrida[ambas])


def chequear_desfase(integrado):
    # Si las horas están bien alineadas, la correlación es máxima con desfase 0.
    pares = [("ERA5 vs NASA", "irr_era5", "irr_nasa"),
             ("sensor vs ERA5", "irr_sitio", "irr_era5")]
    filas = []
    for nombre, columna_a, columna_b in pares:
        for horas in range(-reglas.DESFASE_MAX_H, reglas.DESFASE_MAX_H + 1):
            r = correlacion_con_desfase(integrado[columna_a], integrado[columna_b], horas)
            filas.append({"par": nombre, "desfase_h": horas,
                          "correlacion": None if pd.isna(r) else round(float(r), 4)})
    tabla = pd.DataFrame(filas)

    mejores = {}
    advertencias = []
    for nombre in tabla["par"].unique():
        del_par = tabla[(tabla["par"] == nombre) & tabla["correlacion"].notna()]
        if del_par.empty:
            mejores[nombre] = None
            advertencias.append(f"No se pudo calcular el desfase de {nombre}: faltan datos.")
            continue
        mejor = int(del_par.loc[del_par["correlacion"].idxmax(), "desfase_h"])
        mejores[nombre] = mejor
        if mejor != 0:
            causa = ("la hora de NASA POWER (hora solar local) no quedó bien alineada con UTC"
                     if nombre == "ERA5 vs NASA" else
                     "la hora del sensor no parece estar en UTC o no usa la etiqueta al final de la hora")
            advertencias.append(f"Desfase en {nombre}: la correlación es máxima en {mejor:+d} h, no en 0. "
                                f"Posible causa: {causa}. Los factores pueden estar sesgados.")
    return tabla, mejores, advertencias
