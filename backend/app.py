"""
API de Factor Solar Web (FastAPI).

    cd backend && python -m uvicorn app:app --port 8000

Contrato v1 (ver odd/tasks/factor-solar-web.md). Si existe frontend/dist, se sirve en "/".
"""

import logging
import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

import almacen
from nucleo import extraccion, reglas, sensor_csv, simulador
from nucleo.formato import coord

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("factor_solar")
VERSION = "1.0.0"
MAX_CSV_BYTES = 30 * 1024 * 1024
HOSTS_PERMITIDOS = ["localhost", "127.0.0.1"]
# Al publicar en la nube, FACTOR_SOLAR_HOSTS agrega el dominio público (separados por coma, o "*").
HOSTS_PERMITIDOS += [h.strip() for h in os.environ.get("FACTOR_SOLAR_HOSTS", "").split(",") if h.strip()]
# Orígenes de desarrollo de Vite (dev y preview) además del mismo origen.
ORIGEN_DESARROLLO = re.compile(r"^http://(localhost|127\.0\.0\.1):(51\d\d|4173)$")

app = FastAPI(title="Factor Solar Web", version=VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
# Exposición local: la app solo atiende nombres de host locales (frena DNS rebinding) y los POST de otros sitios web.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=HOSTS_PERMITIDOS)


def origen_permitido(origen, host, esquema="http"):
    # Mismo origen (esquema y host:puerto iguales a los de la llamada) o un origen de desarrollo de Vite.
    partes = urlsplit(origen)
    if partes.scheme not in ("http", "https") or not partes.netloc:
        return False
    return (partes.scheme == esquema and partes.netloc == host) or ORIGEN_DESARROLLO.match(origen) is not None


@app.middleware("http")
async def revisar_origen(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origen = request.headers.get("origin")
        # Los navegadores siempre mandan Origin en un POST entre sitios; sin Origin es un cliente local (curl, pruebas).
        if origen is not None and not origen_permitido(origen, request.headers.get("host", ""), request.url.scheme):
            return JSONResponse(status_code=403, content={"detail": {
                "mensaje": "Pedido rechazado: viene de otro sitio web. Abra la aplicación desde http://localhost:8000."}})
    return await call_next(request)


def error(estado, mensaje, **extra):
    raise HTTPException(status_code=estado, detail={"mensaje": mensaje, **extra})


TRADUCCIONES = {
    "greater_than_equal": lambda c: f"debe ser mayor o igual que {c.get('ge')}",
    "less_than_equal": lambda c: f"debe ser menor o igual que {c.get('le')}",
    "greater_than": lambda c: f"debe ser mayor que {c.get('gt')}",
    "less_than": lambda c: f"debe ser menor que {c.get('lt')}",
    "missing": lambda c: "es obligatorio",
    "extra_forbidden": lambda c: "no es un parámetro admitido",
    "string_too_long": lambda c: f"admite como máximo {c.get('max_length')} caracteres",
    "string_too_short": lambda c: f"necesita al menos {c.get('min_length')} caracteres",
    "int_parsing": lambda c: "debe ser un número entero",
    "int_from_float": lambda c: "debe ser un número entero",
    "float_parsing": lambda c: "debe ser un número",
    "literal_error": lambda c: f"valor no admitido (opciones: {c.get('expected')})",
    "string_pattern_mismatch": lambda c: "tiene un formato no válido",
}


def traducir(e):
    campo = ".".join(str(p) for p in e["loc"][1:]) or "pedido"
    traductor = TRADUCCIONES.get(e["type"])
    if traductor:
        return f"{campo}: {traductor(e.get('ctx') or {})}"
    if e["type"] == "value_error":
        return f"{campo}: {str(e.get('msg', '')).removeprefix('Value error, ')}"
    return f"{campo}: valor no válido"


@app.exception_handler(RequestValidationError)
async def error_de_validacion(_request: Request, exc: RequestValidationError):
    errores = [traducir(e) for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": {
        "mensaje": "Datos del pedido inválidos: " + "; ".join(errores) + ".", "errores": errores}})


@app.exception_handler(Exception)
async def error_inesperado(request: Request, exc: Exception):
    # Nunca se devuelve la traza al navegador; queda en el registro del servidor.
    log.error("Error no controlado en %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": {
        "mensaje": "Ocurrió un error inesperado en el servidor. Intente de nuevo; si se repite, revise el registro del servidor."}})


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class DefectosPedido(BaseModel):
    model_config = ConfigDict(extra="forbid")
    huecos_cortos: int | None = Field(None, ge=0, le=10_000)
    huecos_medios: int | None = Field(None, ge=0, le=10_000)
    corte_largo_min: int | None = Field(None, ge=0, le=10_000)
    nan_irradiancia: int | None = Field(None, ge=0, le=10_000)
    nan_temperatura: int | None = Field(None, ge=0, le=10_000)
    picos_irradiancia: int | None = Field(None, ge=0, le=10_000)
    negativos_nocturnos: int | None = Field(None, ge=0, le=10_000)
    temperatura_fuera_rango: int | None = Field(None, ge=0, le=10_000)
    timestamps_duplicados: int | None = Field(None, ge=0, le=10_000)


class ParametrosPedido(BaseModel):
    """Parámetros del simulador, acotados. Lo que no se manda queda en el valor por defecto."""
    model_config = ConfigDict(extra="forbid")
    a: float | None = Field(None, ge=0, le=2)
    b: float | None = Field(None, ge=0, le=2)
    factor_min: float | None = Field(None, ge=0.1, le=2)
    factor_max: float | None = Field(None, ge=0.1, le=2)
    ruido_sigma: float | None = Field(None, ge=0, le=0.5)
    ruido_ventana_min: int | None = Field(None, ge=1, le=60)
    k_calentamiento: float | None = Field(None, ge=0, le=0.1)
    ruido_t_c: float | None = Field(None, ge=0, le=5)
    defectos: DefectosPedido | None = None

    @model_validator(mode="after")
    def _orden(self):
        por_defecto = simulador.ParametrosSimulacion()
        minimo = self.factor_min if self.factor_min is not None else por_defecto.factor_min
        maximo = self.factor_max if self.factor_max is not None else por_defecto.factor_max
        if minimo > maximo:
            raise ValueError("factor_min no puede ser mayor que factor_max")
        return self

    def como_dict(self):
        return self.model_dump(exclude_none=True)


class PedidoSimulacion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    anio: int = Field(reglas.ANIO_POR_DEFECTO, ge=reglas.ANIO_MIN, le=reglas.ANIO_MAX)
    semilla: int | None = Field(2026, ge=0, le=2**32 - 1)
    parametros: ParametrosPedido | None = None
    nombre: str | None = Field(None, max_length=120)


class PedidoAnalisis(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    anio: int
    sensor_id: str = Field(max_length=60)
    regimen: Literal["bimodal_andino"] | None = None
    nombre: str | None = Field(None, max_length=120)


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

@app.get("/api/salud")
def salud():
    return {"estado": "ok", "version": VERSION, "anio_min": reglas.ANIO_MIN, "anio_max": reglas.ANIO_MAX,
            "anio_por_defecto": reglas.ANIO_POR_DEFECTO,
            "parametros_simulacion": simulador.ParametrosSimulacion().__dict__}


@app.get("/api/buscar")
def buscar(q: str = Query(min_length=2, max_length=100)):
    try:
        return {"lugares": extraccion.buscar_lugares(q)}
    except extraccion.ErrorFuente as e:
        error(502, str(e))


@app.get("/api/ejemplos")
def ejemplos():
    return {"ejemplos": almacen.listar_ejemplos()}


def simular_y_guardar(lat, lon, anio, semilla=2026, parametros=None, nombre=None, sensor_id=None):
    """Simula un sensor en (lat, lon, anio) y lo guarda. Devuelve (meta, resultado de la simulación)."""
    mensaje = reglas.validar_sitio(lat, lon, anio)
    if mensaje:
        raise ValueError(mensaje)
    texto, _origen = extraccion.obtener_openmeteo(lat, lon, anio)
    era5 = extraccion.leer_openmeteo(texto)
    sim = simulador.simular_sensor(era5, anio, lat, lon, semilla=semilla, parametros=parametros)
    sensor_id = sensor_id or almacen.nuevo_id("sim")
    crudo = sim["crudo"]
    meta = {"sensor_id": sensor_id, "nombre": nombre or f"Sensor simulado ({coord(lat, lon)})",
            "simulado": True, "frecuencia": "minuto", "anio": anio, "lat": lat, "lon": lon,
            "filas": len(crudo), "desde": f"{crudo['ts_utc'].min():%Y-%m-%d %H:%M}",
            "hasta": f"{crudo['ts_utc'].max():%Y-%m-%d %H:%M}", "tiene_temperatura": True,
            "factor_verdadero_anual": sim["factor_verdadero_anual"],
            "defectos_inyectados": {k: v for k, v in sim["defectos"].items() if k != "descripcion_huecos"},
            "descripcion_defectos": sim["defectos"]["descripcion_huecos"],
            "supuestos": sim["supuestos"], "parametros": sim["parametros"], "semilla": sim["semilla"]}
    return meta, sim


@app.post("/api/sensor/simular")
def sensor_simular(pedido: PedidoSimulacion):
    try:
        parametros = pedido.parametros.como_dict() if pedido.parametros is not None else None
        meta, sim = simular_y_guardar(pedido.lat, pedido.lon, pedido.anio, pedido.semilla
                                      if pedido.semilla is not None else 2026, parametros, pedido.nombre)
    except ValueError as e:
        error(400, str(e))
    except extraccion.ErrorFuente as e:
        error(502, str(e))
    almacen.guardar_sensor(meta["sensor_id"], sim["crudo"], meta, sim["verdadero"])
    return {"sensor_id": meta["sensor_id"], "resumen": almacen.resumen_sensor(meta)}


@app.post("/api/sensor/subir")
def sensor_subir(archivo: UploadFile = File(...), anio: int | None = Form(None),
                       lat: float | None = Form(None), lon: float | None = Form(None),
                       nombre: str | None = Form(None, max_length=120)):
    # `def` (no `async def`): FastAPI lo corre en un hilo, así que leer y validar el CSV no bloquea el servidor.
    contenido = archivo.file.read(MAX_CSV_BYTES + 1)
    if len(contenido) > MAX_CSV_BYTES:
        error(413, f"El archivo supera {MAX_CSV_BYTES // (1024 * 1024)} MB.")
    try:
        tabla, validacion = sensor_csv.validar_csv(contenido, anio)
    except sensor_csv.ErrorCSV as e:
        error(422, str(e), validacion=e.reporte)
    sensor_id = almacen.nuevo_id("csv")
    meta = {"sensor_id": sensor_id, "nombre": nombre or (archivo.filename or "Sensor subido"),
            "simulado": False, "frecuencia": validacion["frecuencia"], "anio": validacion["anio"],
            "lat": lat, "lon": lon, "filas": validacion["filas_utiles"], "desde": validacion["desde"],
            "hasta": validacion["hasta"], "tiene_temperatura": validacion["tiene_temperatura"],
            "archivo": archivo.filename}
    almacen.guardar_sensor(sensor_id, tabla, meta)
    return {"sensor_id": sensor_id, "resumen": almacen.resumen_sensor(meta), "validacion": validacion}


@app.post("/api/analisis")
def analisis_crear(pedido: PedidoAnalisis):
    mensaje = reglas.validar_sitio(pedido.lat, pedido.lon, pedido.anio)
    if mensaje:
        error(400, mensaje)
    cargado = almacen.cargar_sensor(pedido.sensor_id)
    if cargado is None:
        error(404, f"No existe el sensor {pedido.sensor_id}.")
    sensor, meta = cargado
    if meta["anio"] != pedido.anio:
        error(400, f"El sensor tiene datos de {meta['anio']} y se pidió el año {pedido.anio}.")
    analisis_id = almacen.iniciar_analisis(pedido.lat, pedido.lon, pedido.anio, sensor, pedido.regimen,
                                           pedido.nombre)
    return {"analisis_id": analisis_id}


@app.get("/api/analisis/{analisis_id}")
def analisis_estado(analisis_id: str):
    estado = almacen.estado_analisis(analisis_id)
    if estado is None:
        error(404, f"No existe el análisis {analisis_id}.")
    return estado


@app.get("/api/analisis/{analisis_id}/descargar")
def analisis_descargar(analisis_id: str):
    contenido = almacen.zip_analisis(analisis_id)
    if contenido is None:
        error(404, "El análisis no existe o todavía no termina.")
    return Response(content=contenido, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="factor_solar_{analisis_id}.zip"'})


# ---------------------------------------------------------------------------
# Frontend construido (W2)
# ---------------------------------------------------------------------------
DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
