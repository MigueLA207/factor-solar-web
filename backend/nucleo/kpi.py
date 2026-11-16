"""
[L] Indicadores: factor de corrección, sesgo, consistencia entre fuentes, día típico y energía.

Copia adaptada de ae4/pipeline/src/kpi.py. Mismo factor: Σ sensor / Σ fuente sobre las horas
diurnas donde el sensor y la fuente tienen dato (cociente de energías, no promedio de cocientes).
Cambios: factor anual + mensual (universal); fases del régimen bimodal solo si se piden; el factor
verdadero viene por hora desde el simulador (columna factor_verdadero), no de una tabla por fase.

Roles: el sensor es la verdad del sitio; ERA5 es la fuente con la que se cotiza (su factor es el
"factor de cotización"); NASA POWER es el "chequeo cruzado".
"""

import numpy as np
import pandas as pd

from . import reglas, sol
from .formato import dec, pct

COLUMNA_DE_FUENTE = {"era5": "irr_era5", "nasa": "irr_nasa"}
ROL_DE_FUENTE = {"era5": "factor de cotización", "nasa": "chequeo cruzado"}


def _r(valor, decimales):
    if valor is None or pd.isna(valor):
        return None
    return round(float(valor), decimales)


def horas_comparables(integrado, columna_fuente):
    # Horas diurnas donde el sensor y la fuente tienen valor: solo ahí se comparan.
    filtro = integrado["es_diurna"] & integrado["irr_sitio"].notna() & integrado[columna_fuente].notna()
    return integrado[filtro]


def fila_factor(horas, columna, periodo):
    suma_sensor = horas["irr_sitio"].sum()
    suma_fuente = horas[columna].sum()
    factor = suma_sensor / suma_fuente if suma_fuente > 0 else np.nan
    sesgo = 100 * (suma_fuente - suma_sensor) / suma_sensor if suma_sensor > 0 else np.nan
    fila = {"periodo": periodo, "n_horas": int(len(horas)),
            "suma_sensor_kwh_m2": _r(suma_sensor / 1000, 2),
            "suma_fuente_kwh_m2": _r(suma_fuente / 1000, 2),
            "factor": _r(factor, 4), "sesgo_relativo_pct": _r(sesgo, 2),
            "factor_verdadero": None, "error_abs": None}
    if "factor_verdadero" in horas.columns and columna == "irr_era5" and suma_fuente > 0:
        con_verdad = horas["factor_verdadero"].notna()
        if con_verdad.any():
            pesos = horas.loc[con_verdad, columna]
            verdadero = (horas.loc[con_verdad, "factor_verdadero"] * pesos).sum() / pesos.sum()
            fila["factor_verdadero"] = _r(verdadero, 4)
            fila["error_abs"] = _r(abs(factor - verdadero), 4)
    return fila


def calcular_factores(integrado, regimen=None):
    resultado = {}
    for fuente, columna in COLUMNA_DE_FUENTE.items():
        horas = horas_comparables(integrado, columna)
        anual = fila_factor(horas, columna, "anual")
        mensual = []
        for mes in range(1, 13):
            del_mes = horas[horas["mes"] == mes]
            fila = fila_factor(del_mes, columna, reglas.MESES[mes - 1])
            fila["mes"] = mes
            mensual.append(fila)
        bloque = {"rol": ROL_DE_FUENTE[fuente], "anual": anual, "mensual": mensual}
        if regimen == "bimodal_andino":
            fases = horas["mes"].map(reglas.FASES_BIMODAL_POR_MES)
            bloque["fases_bimodal"] = []
            for fase in reglas.ORDEN_FASES_BIMODAL:
                fila = fila_factor(horas[fases == fase], columna, fase)
                fila["etiqueta"] = reglas.ETIQUETAS_FASES_BIMODAL[fase]
                bloque["fases_bimodal"].append(fila)
        resultado[fuente] = bloque
    return resultado


def tabla_factores(factores):
    # Versión plana (para el CSV del ZIP).
    filas = []
    for fuente, bloque in factores.items():
        for grupo in ("anual", "mensual", "fases_bimodal"):
            if grupo not in bloque:
                continue
            for fila in ([bloque[grupo]] if grupo == "anual" else bloque[grupo]):
                filas.append({"fuente": fuente.upper(), "rol": bloque["rol"], "grupo": grupo, **fila})
    return pd.DataFrame(filas)


def comparar_dos_series(horas, columna_a, columna_b):
    diferencia = horas[columna_a] - horas[columna_b]
    suma_a = horas[columna_a].sum()
    suma_b = horas[columna_b].sum()
    return {"serie_a": columna_a, "serie_b": columna_b, "n_horas": int(len(horas)),
            "diferencia_media": _r(diferencia.mean(), 3),
            "mae": _r(diferencia.abs().mean(), 3),
            "correlacion": _r(horas[columna_a].corr(horas[columna_b]), 4),
            "suma_a_kwh_m2": _r(suma_a / 1000, 2), "suma_b_kwh_m2": _r(suma_b / 1000, 2),
            "diferencia_total_pct": _r(100 * (suma_a - suma_b) / suma_b, 2) if suma_b > 0 else None}


def con_ambas(integrado, columna_a, columna_b, solo_diurnas=True):
    horas = integrado[integrado[columna_a].notna() & integrado[columna_b].notna()]
    if solo_diurnas:
        horas = horas[horas["es_diurna"]]
    return horas


def calcular_consistencia(integrado):
    # ERA5 vs NASA (chequeo final) sobre las mismas horas del factor: diurnas con sensor, ERA5 y NASA.
    horas_chequeo = horas_comparables(integrado, "irr_nasa")
    horas_chequeo = horas_chequeo[horas_chequeo["irr_era5"].notna()]
    chequeo = comparar_dos_series(horas_chequeo, "irr_era5", "irr_nasa")
    chequeo["filtro"] = "horas diurnas del factor (con sensor, ERA5 y NASA)"
    if chequeo["correlacion"] is not None and chequeo["diferencia_total_pct"] is not None:
        chequeo["conclusion"] = (
            f"Correlación {dec(chequeo['correlacion'], 3)}: hora a hora ERA5 y NASA ven el mismo patrón de sol "
            f"y nubes, así que la alineación de la hora (ts_utc) está bien. Diferencia de "
            f"{pct(chequeo['diferencia_total_pct'], 2, signo=True)} en el total: las fuentes gratuitas no coinciden en la "
            f"cantidad de energía, por eso hace falta un sensor en el sitio. Que coincidan valida el proceso, "
            f"no la exactitud de ninguna de las dos.")
    sensor_era5 = comparar_dos_series(con_ambas(integrado, "irr_sitio", "irr_era5"), "irr_sitio", "irr_era5")
    sensor_era5["filtro"] = "horas diurnas"
    sensor_nasa = comparar_dos_series(con_ambas(integrado, "irr_sitio", "irr_nasa"), "irr_sitio", "irr_nasa")
    sensor_nasa["filtro"] = "horas diurnas"
    era5_nasa_todas = comparar_dos_series(con_ambas(integrado, "irr_era5", "irr_nasa"), "irr_era5", "irr_nasa")
    era5_nasa_todas["filtro"] = "horas diurnas (todas con ERA5 y NASA)"
    temperatura = comparar_dos_series(con_ambas(integrado, "t_aire_era5", "t_aire_nasa", False),
                                      "t_aire_era5", "t_aire_nasa")
    temperatura["filtro"] = "todas las horas"
    return {"era5_vs_nasa": chequeo, "sensor_vs_era5": sensor_era5, "sensor_vs_nasa": sensor_nasa,
            "era5_vs_nasa_todas": era5_nasa_todas, "temperatura_aire_era5_vs_nasa": temperatura}


def calcular_calentamiento(integrado):
    con_datos = integrado["t_modulo"].notna() & integrado["t_aire_era5"].notna()
    horas = integrado[integrado["es_diurna"] & con_datos]
    if horas.empty:
        return None
    return _r((horas["t_modulo"] - horas["t_aire_era5"]).mean(), 2)


def calcular_dia_tipico(integrado, lon):
    # Promedio por hora local aproximada (UTC + round(lon/15)) de las horas con las tres fuentes.
    # La etiqueta H es el promedio de (H-1, H], igual que en las fuentes.
    completas = integrado[integrado[["irr_sitio", "irr_era5", "irr_nasa"]].notna().all(axis=1)].copy()
    completas["hora_local"] = sol.hora_local_aprox(completas["ts_utc"], lon)
    promedio = completas.groupby("hora_local")[["irr_sitio", "irr_era5", "irr_nasa"]].mean()
    promedio = promedio.reindex(range(24))
    filas = []
    for hora, fila in promedio.iterrows():
        filas.append({"hora_local": int(hora), "sensor": _r(fila["irr_sitio"], 1),
                      "era5": _r(fila["irr_era5"], 1), "nasa": _r(fila["irr_nasa"], 1)})
    return filas


def calcular_energia_mensual(integrado, factor_anual_era5):
    # kWh/m² por mes sobre las horas del factor ERA5 (diurnas con sensor y ERA5). NASA se suma en
    # esas mismas horas cuando tiene dato. "ERA5 × factor" usa el factor anual (así se cotizaría).
    horas = horas_comparables(integrado, "irr_era5")
    filas = []
    for mes in range(1, 13):
        del_mes = horas[horas["mes"] == mes]
        era5 = del_mes["irr_era5"].sum() / 1000
        filas.append({
            "mes": mes, "etiqueta": reglas.MESES[mes - 1], "n_horas": int(len(del_mes)),
            "era5_sin_corregir_kwh_m2": _r(era5, 2),
            "era5_por_factor_kwh_m2": _r(era5 * factor_anual_era5, 2) if factor_anual_era5 else None,
            "sensor_kwh_m2": _r(del_mes["irr_sitio"].sum() / 1000, 2),
            "nasa_kwh_m2": _r(del_mes["irr_nasa"].sum() / 1000, 2),
        })
    return filas
