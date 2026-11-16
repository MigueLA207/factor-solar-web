"""
Almacenamiento de sensores (simulados, subidos y de ejemplo) y de análisis.

- Sensores de esta instalación: datos/sensores/<id>/ (meta.json, crudo.pkl, verdadero.pkl).
- Sensores de ejemplo: datos/ejemplos/<slug>.csv.gz (+ _verdadero.csv.gz y .json); id "ejemplo-<slug>".
- Análisis: en memoria mientras corren; al terminar se guardan en datos/analisis/<id>/
  (resultado.json y las tablas CSV del ZIP), así sobreviven a un reinicio.
"""

import io
import json
import re
import threading
import time
import traceback
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import pandas as pd

from nucleo import extraccion, pipeline, reglas, simulador

# ---------------------------------------------------------------------------
# Sensores
# ---------------------------------------------------------------------------


def nuevo_id(prefijo):
    return f"{prefijo}-{uuid.uuid4().hex[:10]}"


# Identificadores estrictos: se comprueban ANTES de tocar el disco (nada de "..", rutas ni unidades "C:x").
RE_ID_ANALISIS = re.compile(r"^an-[0-9a-f]{10}$")
RE_ID_SENSOR = re.compile(r"^(sim|csv)-[0-9a-f]{10}$")
RE_SLUG_EJEMPLO = re.compile(r"^[a-z0-9_]{1,40}$")


def id_analisis_valido(analisis_id):
    return isinstance(analisis_id, str) and RE_ID_ANALISIS.fullmatch(analisis_id) is not None


def slugs_de_ejemplos():
    return {ruta.stem for ruta in reglas.EJEMPLOS.glob("*.json")}


def id_sensor_valido(sensor_id):
    if not isinstance(sensor_id, str):
        return False
    if RE_ID_SENSOR.fullmatch(sensor_id):
        return True
    if sensor_id.startswith("ejemplo-"):
        slug = sensor_id.removeprefix("ejemplo-")
        return RE_SLUG_EJEMPLO.fullmatch(slug) is not None and slug in slugs_de_ejemplos()
    return False


def guardar_sensor(sensor_id, crudo, meta, verdadero=None):
    if not RE_ID_SENSOR.fullmatch(sensor_id):
        raise ValueError(f"Identificador de sensor no válido: {sensor_id!r}")
    carpeta = reglas.SENSORES / sensor_id
    carpeta.mkdir(parents=True, exist_ok=True)
    crudo.to_pickle(carpeta / "crudo.pkl")
    if verdadero is not None:
        verdadero.to_pickle(carpeta / "verdadero.pkl")
    (carpeta / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _leer_csv_sensor(ruta):
    tabla = pd.read_csv(ruta, dtype={"irr_sitio": "float64", "t_modulo": "float64"})
    tabla["ts_utc"] = pd.to_datetime(tabla["ts_utc"], format="%Y-%m-%d %H:%M:%S")
    return tabla


@lru_cache(maxsize=3)
def _cargar_ejemplo(slug):
    crudo = _leer_csv_sensor(reglas.EJEMPLOS / f"{slug}.csv.gz")
    verdadero = pd.read_csv(reglas.EJEMPLOS / f"{slug}_verdadero.csv.gz")
    verdadero["ts_utc"] = pd.to_datetime(verdadero["ts_utc"], format="%Y-%m-%d %H:%M:%S")
    return crudo, verdadero


def leer_meta(sensor_id):
    if not id_sensor_valido(sensor_id):
        return None
    if sensor_id.startswith("ejemplo-"):
        ruta = reglas.EJEMPLOS / f"{sensor_id.removeprefix('ejemplo-')}.json"
    else:
        ruta = reglas.SENSORES / sensor_id / "meta.json"
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def _supuestos_para_personas(meta):
    """Los supuestos guardados pueden traer punto decimal (ejemplos viejos): se redactan de nuevo con coma."""
    if meta.get("simulado") and meta.get("parametros") and meta.get("semilla") is not None:
        return simulador.supuestos(simulador.ParametrosSimulacion.desde(meta["parametros"]), meta["semilla"])
    return meta.get("supuestos", [])


def cargar_sensor(sensor_id):
    """Devuelve (pipeline.Sensor, meta) o None si no existe."""
    meta = leer_meta(sensor_id)
    if meta is None:
        return None
    if sensor_id.startswith("ejemplo-"):
        crudo, verdadero = _cargar_ejemplo(sensor_id.removeprefix("ejemplo-"))
        crudo = crudo.copy()
    else:
        carpeta = reglas.SENSORES / sensor_id
        crudo = pd.read_pickle(carpeta / "crudo.pkl")
        verdadero = pd.read_pickle(carpeta / "verdadero.pkl") if (carpeta / "verdadero.pkl").exists() else None
    sensor = pipeline.Sensor(
        crudo=crudo, frecuencia=meta["frecuencia"], simulado=meta["simulado"], verdadero=verdadero,
        inyectados=meta.get("defectos_inyectados"), supuestos=_supuestos_para_personas(meta),
        tiene_temperatura=meta.get("tiene_temperatura", True), lat=meta.get("lat"), lon=meta.get("lon"),
        nombre=meta.get("nombre"))
    return sensor, meta


def listar_ejemplos():
    ejemplos = []
    for ruta in sorted(reglas.EJEMPLOS.glob("*.json")):
        meta = json.loads(ruta.read_text(encoding="utf-8"))
        ejemplos.append({k: meta.get(k) for k in (
            "sensor_id", "slug", "nombre", "lugar", "lat", "lon", "anio", "descripcion", "clima",
            "simulado", "factor_verdadero_anual", "frecuencia", "filas")})
    return ejemplos


def resumen_sensor(meta):
    claves = ("sensor_id", "nombre", "simulado", "frecuencia", "anio", "lat", "lon", "filas", "desde", "hasta",
              "tiene_temperatura", "factor_verdadero_anual", "defectos_inyectados", "supuestos", "parametros",
              "semilla")
    return {k: meta.get(k) for k in claves if k in meta}


# ---------------------------------------------------------------------------
# Análisis
# ---------------------------------------------------------------------------

_analisis = {}
MAX_ANALISIS_EN_MEMORIA = 20      # los terminados que sobren se sacan de memoria (los resultados siguen en disco)
_candado = threading.Lock()
_ejecutor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analisis")


def _etapas_iniciales():
    return [{"fase": fase, "paso": paso, "titulo": titulo, "estado": "pendiente", "detalle": ""}
            for fase, paso, titulo in pipeline.ETAPAS]


def _guardar_resultado(analisis_id, resultado, tablas):
    if not id_analisis_valido(analisis_id):
        raise ValueError(f"Identificador de análisis no válido: {analisis_id!r}")
    carpeta = reglas.ANALISIS / analisis_id
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, tabla in tablas.items():
        tabla.to_csv(carpeta / nombre, index=False, encoding="utf-8", date_format="%Y-%m-%d %H:%M")
    (carpeta / "resultado.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")


def _mensaje_de_error(error):
    if isinstance(error, extraccion.ErrorFuente):
        return str(error)
    if isinstance(error, AssertionError):
        return f"Una regla de calidad no se cumplió: {error}"
    if isinstance(error, ValueError):
        return str(error)
    return f"Error inesperado ({type(error).__name__}): {error}"


def _correr(analisis_id, lat, lon, anio, sensor, regimen, nombre):
    registro = _analisis[analisis_id]

    def avance(paso, estado, detalle=""):
        with _candado:
            for etapa in registro["etapas"]:
                if etapa["paso"] == paso:
                    etapa["estado"] = estado
                    etapa["detalle"] = detalle

    try:
        resultado, tablas = pipeline.ejecutar_analisis(lat, lon, anio, sensor, regimen, avance, nombre=nombre)
        resultado["analisis_id"] = analisis_id
        _guardar_resultado(analisis_id, resultado, tablas)
        with _candado:
            registro["resultado"] = resultado
            registro["estado"] = "listo"
    except Exception as error:  # noqa: BLE001 - todo error se muestra en la etapa
        mensaje = _mensaje_de_error(error)
        traceback.print_exc()
        with _candado:
            _marcar_error(registro, mensaje)
    finally:
        with _candado:
            registro["terminado"] = time.time()
            _expulsar_terminados()


def _marcar_error(registro, mensaje):
    # Siempre deja UNA etapa en error, para que la interfaz nunca muestre todo en verde junto a un error:
    # la que estaba en curso; si la excepción cayó entre etapas, la primera pendiente; si ya estaban todas
    # listas (p. ej. falló el guardado), la última.
    etapas = registro["etapas"]
    objetivo = next((e for e in etapas if e["estado"] == "en_curso"), None)         or next((e for e in etapas if e["estado"] == "pendiente"), None) or etapas[-1]
    objetivo["estado"] = "error"
    objetivo["detalle"] = mensaje
    registro["estado"] = "error"
    registro["error"] = mensaje
    registro["resultado"] = None


def _expulsar_terminados():
    # Llamar con _candado tomado. Conserva en memoria los MAX_ANALISIS_EN_MEMORIA terminados más recientes
    # (más todos los que siguen corriendo); el resto se pide al disco (listos) o deja de existir (con error).
    terminados = sorted((r for r in _analisis.values() if "terminado" in r), key=lambda r: r["terminado"])
    for registro in terminados[:max(0, len(terminados) - MAX_ANALISIS_EN_MEMORIA)]:
        _analisis.pop(registro["analisis_id"], None)


def iniciar_analisis(lat, lon, anio, sensor, regimen=None, nombre=None):
    analisis_id = nuevo_id("an")
    with _candado:
        _analisis[analisis_id] = {"analisis_id": analisis_id, "estado": "en_curso", "etapas": _etapas_iniciales(),
                                  "resultado": None, "error": None, "creado": time.time(),
                                  "pedido": {"lat": lat, "lon": lon, "anio": anio, "regimen": regimen}}
    _ejecutor.submit(_correr, analisis_id, lat, lon, anio, sensor, regimen, nombre)
    return analisis_id


def estado_analisis(analisis_id):
    # Mientras corre, solo se devuelven las etapas (sin resultado); el resultado va cuando está listo.
    if not id_analisis_valido(analisis_id):
        return None
    with _candado:
        registro = _analisis.get(analisis_id)
        if registro is not None:
            salida = {"analisis_id": registro["analisis_id"], "estado": registro["estado"],
                      "etapas": [dict(e) for e in registro["etapas"]], "error": registro["error"],
                      "resultado": registro["resultado"] if registro["estado"] == "listo" else None}
            return json.loads(json.dumps(salida))
    ruta = reglas.ANALISIS / analisis_id / "resultado.json"
    if not ruta.exists():
        return None
    etapas = _etapas_iniciales()
    for etapa in etapas:
        etapa["estado"] = "listo"
    return {"analisis_id": analisis_id, "estado": "listo", "etapas": etapas,
            "resultado": json.loads(ruta.read_text(encoding="utf-8")), "error": None}


def zip_analisis(analisis_id):
    if not id_analisis_valido(analisis_id):
        return None
    carpeta = reglas.ANALISIS / analisis_id
    if not carpeta.is_dir():
        return None
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as archivo:
        for ruta in sorted(carpeta.iterdir()):
            archivo.write(ruta, ruta.name)
        archivo.writestr("LEEME.txt", (
            "Tablas del análisis del factor de corrección (Factor Solar Web).\n"
            "factor = suma(irr_sitio) / suma(irr_fuente) en horas diurnas con ambos datos.\n"
            "ERA5 = factor de cotización; NASA POWER = chequeo cruzado.\n"
            "Si resultado.json dice \"simulado\": true, el sensor es SIMULADO: el factor valida el método,\n"
            "no es una medición del sitio. Si dice \"simulado\": false, los datos los subió el usuario\n"
            "(la app no puede comprobar si vienen de un sensor real).\n"
            "Formato de los números: los CSV y el JSON usan PUNTO decimal y no llevan separador de miles,\n"
            "para que Excel, Python o R los lean sin cambios. Las frases (detalles, conclusiones, avisos)\n"
            "usan coma decimal, como la interfaz.\n"))
    return memoria.getvalue()
