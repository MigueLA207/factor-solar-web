"""
[E] Extracción: Open-Meteo (ERA5), NASA POWER y Geocoding de Open-Meteo, con caché en disco.

Copia adaptada de ae4/pipeline/src/extraccion.py. Cambios:
- lat, lon y anio son argumentos (sin constantes de Rionegro);
- la respuesta cruda se guarda en datos/cache/ con llave (fuente, lat 4 dp, lon 4 dp, año)
  y se reutiliza: la misma consulta no vuelve a la API;
- los errores se lanzan como ErrorFuente con un mensaje claro en español (no SystemExit).
"""

import calendar
import io
import json
import logging
import os
import tempfile
import threading
import time

import numpy as np
import pandas as pd
import requests

from . import reglas

log = logging.getLogger("factor_solar")


class ErrorFuente(Exception):
    """Una API no respondió, respondió con error o no tiene datos para el punto pedido."""


def redondear(valor):
    return round(float(valor), 4)


def ruta_cache(fuente, lat, lon, anio, extension):
    return reglas.CACHE / f"{fuente}_{redondear(lat):.4f}_{redondear(lon):.4f}_{anio}.{extension}"


def _motivo_error(respuesta):
    # Extrae el mensaje de error que devuelven Open-Meteo ({"reason"}) o NASA ({"messages"}).
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return respuesta.text[:200]
    if isinstance(cuerpo, dict):
        if "reason" in cuerpo:
            return str(cuerpo["reason"])
        for clave in ("messages", "message", "detail", "errors"):
            if clave in cuerpo:
                return str(cuerpo[clave])[:300]
    return str(cuerpo)[:200]


def descargar_con_reintentos(fuente, url, parametros, marca_valida, espera_base_s=None):
    # GET hasta 3 veces con backoff (2 s y 4 s). Devuelve el texto o lanza ErrorFuente.
    espera = reglas.ESPERA_BASE_S if espera_base_s is None else espera_base_s
    ultimo = "sin respuesta"
    for intento in range(1, reglas.REINTENTOS + 1):
        try:
            respuesta = requests.get(url, params=parametros, timeout=reglas.TIMEOUT_S)
            if respuesta.status_code == 200 and marca_valida in respuesta.text[:3000]:
                return respuesta.text
            if 400 <= respuesta.status_code < 500 and respuesta.status_code != 429:
                # Error del pedido (coordenadas, fechas): reintentar no sirve.
                raise ErrorFuente(f"{fuente} rechazó la consulta (HTTP {respuesta.status_code}): "
                                  f"{_motivo_error(respuesta)}")
            ultimo = f"HTTP {respuesta.status_code}"
        except requests.RequestException as error:
            ultimo = type(error).__name__
        log.warning("%s: %s, intento %d de %d", fuente, ultimo, intento, reglas.REINTENTOS)
        if intento < reglas.REINTENTOS:
            time.sleep(espera * 2 ** (intento - 1))
    raise ErrorFuente(f"{fuente} no respondió después de {reglas.REINTENTOS} intentos ({ultimo}). "
                      "Revise la conexión a internet o intente más tarde: el servicio puede estar caído.")


_candado_llaves = threading.Lock()
_candados_cache = {}


def _candado_de(ruta):
    # Un candado por archivo de caché: dos análisis simultáneos del mismo punto no descargan dos veces
    # ni leen un archivo a medio escribir.
    with _candado_llaves:
        return _candados_cache.setdefault(str(ruta), threading.Lock())


def _escribir_atomico(ruta, texto):
    # Escribe en un archivo temporal de la misma carpeta y lo cambia de nombre: nunca queda un archivo a medias.
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=ruta.name + ".", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as archivo:
            archivo.write(texto)
        os.replace(temporal, ruta)
    except BaseException:
        try:
            os.unlink(temporal)
        except OSError:
            pass
        raise


def obtener_con_cache(fuente, url, parametros, ruta, marca_valida, validador=None):
    # Devuelve (texto, origen). Si la respuesta ya está en caché y se puede leer, no consulta la API.
    # Un archivo de caché corrupto (truncado, ilegible) se borra y se vuelve a pedir.
    # `validador(texto)` debe lanzar una excepción si el texto no sirve; una respuesta nueva inválida no se guarda.
    with _candado_de(ruta):
        if ruta.exists():
            try:
                texto = ruta.read_text(encoding="utf-8")
                if validador is not None:
                    validador(texto)
                return texto, "caché local"
            except Exception:  # noqa: BLE001 - cualquier fallo de lectura o validación = caché corrupta
                log.warning("%s: caché corrupta en %s; se borra y se vuelve a pedir", fuente, ruta.name)
                try:
                    ruta.unlink()
                except OSError:
                    pass
        texto = descargar_con_reintentos(fuente, url, parametros, marca_valida)
        if validador is not None:
            try:
                validador(texto)
            except ErrorFuente:
                raise
            except Exception as error:  # noqa: BLE001
                raise ErrorFuente(f"{fuente} respondió con un formato que no se pudo leer ({type(error).__name__}).") from error
        _escribir_atomico(ruta, texto)
        return texto, "API en vivo"


# ---------------------------------------------------------------------------
# Open-Meteo (ERA5)
# ---------------------------------------------------------------------------

def parametros_openmeteo(lat, lon, anio):
    # ERA5 explícito, hora UTC y formato CSV (mismos parámetros de la AE4).
    return {
        "latitude": redondear(lat),
        "longitude": redondear(lon),
        "start_date": f"{anio}-01-01",
        "end_date": f"{anio}-12-31",
        "hourly": "shortwave_radiation,temperature_2m",
        "timezone": "UTC",
        "models": reglas.MODELO_OPENMETEO,
        "format": "csv",
    }


def _validar_openmeteo(texto, anio):
    # Además de leerse, el año debe estar COMPLETO: un archivo truncado se lee bien pero le faltan horas.
    leer_celda_openmeteo(texto)
    horas = len(leer_openmeteo(texto))
    esperadas = 24 * (366 if calendar.isleap(anio) else 365)
    if horas != esperadas:
        raise ErrorFuente(f"Open-Meteo devolvió {horas} horas y se esperaban {esperadas}.")


def obtener_openmeteo(lat, lon, anio):
    return obtener_con_cache("Open-Meteo", reglas.URL_OPENMETEO, parametros_openmeteo(lat, lon, anio),
                             ruta_cache("openmeteo_era5", lat, lon, anio, "csv"), "latitude",
                             lambda texto: _validar_openmeteo(texto, anio))


def leer_celda_openmeteo(texto):
    # Primera línea de datos: latitud, longitud y elevación de la celda ERA5 usada.
    cabecera = pd.read_csv(io.StringIO(texto), nrows=1)
    fila = cabecera.iloc[0]
    return {"lat": float(fila["latitude"]), "lon": float(fila["longitude"]),
            "elevacion_m": float(fila["elevation"])}


def leer_openmeteo(texto):
    # shortwave_radiation en la hora H es el promedio de (H-1, H]; temperature_2m es instantánea.
    tabla = pd.read_csv(io.StringIO(texto), skiprows=3)
    tabla.columns = ["time", "irr_era5", "t_aire_era5"]
    tabla["ts_utc"] = pd.to_datetime(tabla["time"], format="%Y-%m-%dT%H:%M")
    tabla = tabla[["ts_utc", "irr_era5", "t_aire_era5"]]
    if tabla["irr_era5"].notna().sum() == 0:
        raise ErrorFuente("Open-Meteo ERA5 no tiene datos de irradiancia para este punto y año.")
    return tabla


# ---------------------------------------------------------------------------
# NASA POWER
# ---------------------------------------------------------------------------

def parametros_nasa(lat, lon, anio):
    # Comunidad RE, irradiancia y temperatura. Se pide un día extra a cada lado porque la hora
    # viene en hora solar local: así, al pasarla a UTC, el año UTC queda completo en cualquier longitud.
    return {
        "parameters": "ALLSKY_SFC_SW_DWN,T2M",
        "community": "RE",
        "latitude": redondear(lat),
        "longitude": redondear(lon),
        "start": f"{anio - 1}1231",
        "end": f"{anio + 1}0101",
        "format": "JSON",
    }


def _validar_nasa(texto, anio):
    # Se pide un día extra a cada lado (año + 2 días); una copia sin esos días (la de la AE4) también sirve.
    leer_cabecera_nasa(texto)
    horas = len(leer_nasa(texto))
    minimas = 24 * (366 if calendar.isleap(anio) else 365)
    if not (minimas <= horas <= minimas + 48):
        raise ErrorFuente(f"NASA POWER devolvió {horas} horas y se esperaban entre {minimas} y {minimas + 48}.")


def obtener_nasa(lat, lon, anio):
    return obtener_con_cache("NASA POWER", reglas.URL_NASA, parametros_nasa(lat, lon, anio),
                             ruta_cache("nasapower", lat, lon, anio, "json"), "ALLSKY_SFC_SW_DWN",
                             lambda texto: _validar_nasa(texto, anio))


def leer_cabecera_nasa(texto):
    datos = json.loads(texto)
    cabecera = datos.get("header", {})
    coordenadas = datos.get("geometry", {}).get("coordinates", [None, None, None])
    return {"time_standard": cabecera.get("time_standard"),
            "fuentes": cabecera.get("sources"),
            "version_api": cabecera.get("api", {}).get("version"),
            "lat": coordenadas[1], "lon": coordenadas[0],
            "elevacion_m": coordenadas[2] if len(coordenadas) > 2 else None}


def leer_nasa(texto):
    # Tabla en hora solar local (LST) y todavía con los -999: corregirlos es transformación.
    datos = json.loads(texto)
    parametros = datos["properties"]["parameter"]
    irradiancia = pd.Series(parametros["ALLSKY_SFC_SW_DWN"], dtype="float64")
    temperatura = pd.Series(parametros["T2M"], dtype="float64")
    tabla = pd.DataFrame({"irr_nasa": irradiancia, "t_aire_nasa": temperatura})
    tabla["ts_lst"] = pd.to_datetime(tabla.index, format="%Y%m%d%H")
    tabla = tabla[["ts_lst", "irr_nasa", "t_aire_nasa"]].reset_index(drop=True)
    if (tabla["irr_nasa"] != reglas.NASA_VALOR_FALTANTE).sum() == 0:
        raise ErrorFuente("NASA POWER no tiene datos de irradiancia para este punto y año "
                          "(todas las horas llegaron con el código -999).")
    return tabla


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def buscar_lugares(texto, cantidad=8):
    # Busca lugares por nombre en el Geocoding de Open-Meteo, en español.
    parametros = {"name": texto, "count": cantidad, "language": "es", "format": "json"}
    try:
        respuesta = requests.get(reglas.URL_GEOCODING, params=parametros, timeout=20)
    except requests.RequestException as error:
        raise ErrorFuente(f"El buscador de lugares no respondió ({type(error).__name__}).") from error
    if respuesta.status_code != 200:
        raise ErrorFuente(f"El buscador de lugares respondió con error (HTTP {respuesta.status_code}).")
    lugares = []
    for r in respuesta.json().get("results", []) or []:
        partes = [r.get("admin1"), r.get("country")]
        lugares.append({
            "nombre": r.get("name"),
            "region": r.get("admin1"),
            "pais": r.get("country"),
            "codigo_pais": r.get("country_code"),
            "descripcion": ", ".join(p for p in partes if p),
            "lat": r.get("latitude"),
            "lon": r.get("longitude"),
            "elevacion_m": r.get("elevation"),
            "zona_horaria": r.get("timezone"),
        })
    return lugares


def sin_nan(valor):
    # Convierte NaN en None para JSON.
    if valor is None:
        return None
    try:
        return None if np.isnan(valor) else valor
    except TypeError:
        return valor
