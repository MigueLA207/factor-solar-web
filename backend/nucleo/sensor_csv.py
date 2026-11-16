"""
Validación del CSV que sube el usuario: columnas ts_utc, irr_sitio[, t_modulo], por minuto o por
hora, en UTC. Devuelve la tabla normalizada y un reporte en español.

La limpieza (duplicados, picos, negativos, huecos) NO se hace aquí: la hace la etapa de calidad,
igual que con el sensor simulado. Aquí solo se decide si el archivo se puede usar.
"""

import io
import re

import numpy as np
import pandas as pd

from . import reglas, transformacion
from .formato import dec, miles, pct

COBERTURA_MINIMA_PCT = 5.0       # por debajo: el factor no tendría sentido
COBERTURA_AVISO_PCT = 80.0


class ErrorCSV(Exception):
    """El CSV no se puede usar; el mensaje explica por qué, en español."""

    def __init__(self, mensaje, reporte=None):
        super().__init__(mensaje)
        self.reporte = reporte or {}


def decodificar(contenido):
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    raise ErrorCSV("No se pudo leer el archivo como texto (use UTF-8).")


def leer_tabla(texto):
    primera = texto.splitlines()[0] if texto.strip() else ""
    separador = ";" if primera.count(";") > primera.count(",") else ","
    try:
        tabla = pd.read_csv(io.StringIO(texto), sep=separador, dtype=str, keep_default_na=False)
    except Exception as error:  # noqa: BLE001 - cualquier error de lectura se reporta igual
        raise ErrorCSV(f"El archivo no es un CSV válido: {error}") from error
    tabla.columns = [str(c).strip().lower() for c in tabla.columns]
    return tabla, separador


def a_numero(serie):
    texto = serie.str.strip().str.replace(",", ".", regex=False)
    vacio = texto.isin(["", "nan", "NaN", "null", "NA"])
    numero = pd.to_numeric(texto.where(~vacio), errors="coerce")
    no_numericos = int((numero.isna() & ~vacio).sum())
    return numero.astype("float64"), no_numericos


# Solo se aceptan fechas ISO AAAA-MM-DD hh:mm[:ss[.fff]] (con "T" o espacio), con zona opcional (Z, +hh:mm, +hhmm).
# Las fechas con barras (03/04/2024) son ambiguas (¿3 de abril o 4 de marzo?) y se rechazan.
ISO_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?\s*(Z|[+-]\d{2}:?\d{2})?$")
FECHA_CON_BARRAS = re.compile(r"^\d{1,4}/\d{1,2}/\d{1,4}")


def a_fecha_utc(serie):
    # Acepta fechas ISO sin zona (se asumen UTC) o con zona (se convierten a UTC).
    # Devuelve (fechas, filas_con_zona, filas_con_barras).
    texto = serie.str.strip()
    con_barras = int(texto.str.match(FECHA_CON_BARRAS).sum())
    valida = texto.str.match(ISO_FECHA)
    con_zona = int((valida & texto.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True)).sum())
    fechas = pd.to_datetime(texto.where(valida), errors="coerce", utc=True, format="ISO8601")
    return fechas.dt.tz_localize(None), con_zona, con_barras


# Reglas de contenido: el archivo se rechaza si los valores no pueden venir de un piranómetro en W/m².
MIN_VALORES_NUMERICOS_PCT = 50.0   # al menos la mitad de irr_sitio debe ser un número
MAX_IMPOSIBLES_PCT = 20.0          # como máximo 1 de cada 5 valores fuera de -10 a 1500 W/m²
MAX_MINIMO_DIA_WM2 = 50.0          # al sol, un piranómetro supera de lejos 50 W/m² en algún momento
T_MODULO_RANGO = (-40.0, 100.0)    # temperatura posible de la parte trasera de un panel


def revisar_contenido(datos, errores, advertencias, reporte):
    """Bloquea archivos cuyos valores no son de irradiancia en W/m²; avisa si t_modulo no sirve."""
    irr = datos["irr_sitio"]
    total = len(irr)
    numericos = int(irr.notna().sum())
    if 100 * numericos / total < MIN_VALORES_NUMERICOS_PCT:
        errores.append(f"Solo {pct(100 * numericos / total)} de los valores de irr_sitio son números; "
                       f"se necesita al menos el {MIN_VALORES_NUMERICOS_PCT:.0f} %.")
        raise ErrorCSV(errores[0], reporte)
    imposibles = int(((irr < -10) | (irr > reglas.IRR_MAX)).sum())
    if 100 * imposibles / numericos > MAX_IMPOSIBLES_PCT:
        errores.append(f"{pct(100 * imposibles / numericos)} de los valores de irr_sitio están fuera de -10 a "
                       f"{miles(reglas.IRR_MAX)} W/m², que es lo físicamente posible. Revise que la columna sea "
                       "irradiancia en W/m².")
        raise ErrorCSV(errores[0], reporte)
    maximo = irr[(irr >= -10) & (irr <= reglas.IRR_MAX)].max()
    if maximo < MAX_MINIMO_DIA_WM2:
        errores.append(f"irr_sitio nunca pasa de {dec(maximo, 2)} W/m². Un piranómetro al sol supera varios "
                       "cientos de W/m² cerca del mediodía: ¿los datos están en kW/m² o en Wh por minuto, o el "
                       "sensor estuvo tapado?")
        raise ErrorCSV(errores[0], reporte)
    temp = datos["t_modulo"]
    con_temp = int(temp.notna().sum())
    if con_temp:
        fuera = int(((temp < T_MODULO_RANGO[0]) | (temp > T_MODULO_RANGO[1])).sum())
        if 100 * fuera / con_temp > MAX_IMPOSIBLES_PCT:
            advertencias.append(f"{pct(100 * fuera / con_temp)} de t_modulo está fuera de "
                                f"{T_MODULO_RANGO[0]:.0f} a {T_MODULO_RANGO[1]:.0f} °C: se ignora la temperatura "
                                "(no afecta al factor).")
            datos["t_modulo"] = np.nan


def validar_csv(contenido, anio=None):
    """Devuelve (tabla, reporte). Lanza ErrorCSV si el archivo no sirve."""
    errores, advertencias = [], []
    texto = decodificar(contenido)
    tabla, separador = leer_tabla(texto)
    reporte = {"valido": False, "filas_leidas": len(tabla), "separador": separador,
               "columnas_encontradas": list(tabla.columns), "errores": errores, "advertencias": advertencias}

    faltan = [c for c in ("ts_utc", "irr_sitio") if c not in tabla.columns]
    if faltan:
        errores.append(f"Faltan columnas obligatorias: {', '.join(faltan)}. "
                       "El formato es ts_utc, irr_sitio[, t_modulo].")
        raise ErrorCSV(errores[0], reporte)
    if len(tabla) == 0:
        errores.append("El archivo no tiene filas de datos.")
        raise ErrorCSV(errores[0], reporte)
    extra = [c for c in tabla.columns if c not in ("ts_utc", "irr_sitio", "t_modulo")]
    if extra:
        advertencias.append(f"Se ignoran las columnas que no son del formato: {', '.join(extra)}.")
    tiene_temperatura = "t_modulo" in tabla.columns

    fechas, con_zona, con_barras = a_fecha_utc(tabla["ts_utc"])
    if con_barras:
        errores.append(f"{miles(con_barras)} fechas de ts_utc usan barras (p. ej. 03/04/2024) y son ambiguas: "
                       "no se sabe si el día va antes o después del mes. Use el formato ISO AAAA-MM-DD hh:mm[:ss] "
                       "(p. ej. 2024-04-03 13:00:00), en UTC o con la zona (Z o +hh:mm).")
        raise ErrorCSV(errores[0], reporte)
    if con_zona:
        advertencias.append(f"{con_zona} fechas traían zona horaria y se convirtieron a UTC.")
    malas = int(fechas.isna().sum())
    if malas > 0.01 * len(tabla):
        errores.append(f"{malas} de {len(tabla)} fechas de ts_utc no se pudieron leer "
                       "(use el formato ISO AAAA-MM-DD hh:mm[:ss], en UTC o con zona).")
        raise ErrorCSV(errores[0], reporte)
    if malas:
        advertencias.append(f"Se descartan {malas} filas con fecha ilegible.")

    irr, irr_no_num = a_numero(tabla["irr_sitio"])
    if tiene_temperatura:
        temp, t_no_num = a_numero(tabla["t_modulo"])
    else:
        temp, t_no_num = pd.Series(np.nan, index=tabla.index, dtype="float64"), 0
        advertencias.append("El archivo no trae t_modulo: no se calculará el calentamiento del módulo.")
    if irr_no_num:
        advertencias.append(f"{irr_no_num} valores de irr_sitio no son números; quedan vacíos.")
    if t_no_num:
        advertencias.append(f"{t_no_num} valores de t_modulo no son números; quedan vacíos.")

    datos = pd.DataFrame({"ts_utc": fechas, "irr_sitio": irr, "t_modulo": temp})
    datos = datos[datos["ts_utc"].notna()]
    if datos["irr_sitio"].notna().sum() == 0:
        errores.append("irr_sitio no tiene ningún valor numérico.")
        raise ErrorCSV(errores[0], reporte)

    # Frecuencia: la mediana de la distancia entre marcas únicas.
    unicas = datos["ts_utc"].drop_duplicates().sort_values()
    if len(unicas) < 3:
        errores.append("Hay muy pocas marcas de tiempo para deducir la frecuencia.")
        raise ErrorCSV(errores[0], reporte)
    paso_s = unicas.diff().dt.total_seconds().median()
    if paso_s == 60:
        frecuencia = "minuto"
        desalineadas = int((unicas.dt.second != 0).sum())
    elif paso_s == 3600:
        frecuencia = "hora"
        desalineadas = int(((unicas.dt.minute != 0) | (unicas.dt.second != 0)).sum())
    else:
        errores.append(f"La frecuencia no es por minuto ni por hora (paso típico: {miles(paso_s)} s).")
        raise ErrorCSV(errores[0], reporte)
    if desalineadas:
        errores.append(f"{miles(desalineadas)} marcas no caen en el {frecuencia} exacto "
                       f"(deben terminar en :00{' :00' if frecuencia == 'hora' else ''}).")
        raise ErrorCSV(errores[0], reporte)

    # Año: el pedido o el que tiene más registros.
    if anio is None:
        anio = int(datos["ts_utc"].dt.year.mode().iloc[0])
    if not (reglas.ANIO_MIN <= anio <= reglas.ANIO_MAX):
        errores.append(f"El año de los datos ({anio}) está fuera del rango admitido "
                       f"({reglas.ANIO_MIN}–{reglas.ANIO_MAX}).")
        raise ErrorCSV(errores[0], reporte)
    calendario = (transformacion.calendario_minutos(anio) if frecuencia == "minuto"
                  else transformacion.calendario_horas(anio))
    dentro = datos["ts_utc"].between(calendario[0], calendario[-1])
    if (~dentro).sum():
        advertencias.append(f"Se descartan {miles((~dentro).sum())} filas fuera del año {anio}.")
    datos = datos[dentro].sort_values("ts_utc", kind="stable").reset_index(drop=True)

    cobertura = 100 * datos["ts_utc"].nunique() / len(calendario)
    if cobertura < COBERTURA_MINIMA_PCT:
        errores.append(f"El archivo cubre solo el {pct(cobertura)} del año {anio}; "
                       f"se necesita al menos el {COBERTURA_MINIMA_PCT:.0f} %.")
        raise ErrorCSV(errores[0], reporte)
    if cobertura < COBERTURA_AVISO_PCT:
        advertencias.append(f"El archivo cubre el {pct(cobertura)} del año {anio}: el factor solo usa "
                            "los meses con datos; los factores mensuales sin datos quedan vacíos.")
    if frecuencia == "hora":
        advertencias.append("Datos por hora: se asume que cada hora H es el promedio de (H-1, H] en UTC, "
                            "como Open-Meteo. El chequeo de desfase lo verifica.")

    revisar_contenido(datos, errores, advertencias, reporte)

    duplicados = int(datos["ts_utc"].duplicated().sum())
    picos = int((datos["irr_sitio"] > reglas.IRR_MAX).sum())
    negativos = int((datos["irr_sitio"] < 0).sum())
    reporte.update({
        "valido": True, "frecuencia": frecuencia, "anio": anio, "filas_utiles": len(datos),
        "tiene_temperatura": tiene_temperatura,
        "desde": f"{datos['ts_utc'].min():%Y-%m-%d %H:%M}", "hasta": f"{datos['ts_utc'].max():%Y-%m-%d %H:%M}",
        "cobertura_pct": round(cobertura, 2), "duplicados": duplicados,
        "valores_sobre_1500": picos, "valores_negativos": negativos,
        "irr_vacia": int(datos["irr_sitio"].isna().sum()),
        "nota": "Los duplicados, picos, negativos y huecos los corrige la etapa de calidad del análisis.",
    })
    return datos, reporte
