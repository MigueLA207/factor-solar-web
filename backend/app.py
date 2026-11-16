"""
API de Factor Solar Web (FastAPI).

    cd backend && python -m uvicorn app:app --port 8000

Contrato v1 (ver odd/tasks/factor-solar-web.md). Si existe frontend/dist, se sirve en "/".
"""

import logging
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import almacen
from nucleo import extraccion, reglas, sensor_csv, simulador

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
VERSION = "1.0.0"
MAX_CSV_BYTES = 100 * 1024 * 1024

app = FastAPI(title="Factor Solar Web", version=VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


def error(estado, mensaje, **extra):
    raise HTTPException(status_code=estado, detail={"mensaje": mensaje, **extra})


@app.exception_handler(RequestValidationError)
async def error_de_validacion(_request: Request, exc: RequestValidationError):
    errores = [f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": {"mensaje": "Datos del pedido inválidos.",
                                                             "errores": errores}})


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class PedidoSimulacion(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    anio: int = reglas.ANIO_POR_DEFECTO
    semilla: int | None = 2026
    parametros: dict | None = None
    nombre: str | None = None


class PedidoAnalisis(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    anio: int
    sensor_id: str
    regimen: Literal["bimodal_andino"] | None = None
    nombre: str | None = None


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
    meta = {"sensor_id": sensor_id, "nombre": nombre or f"Sensor simulado ({lat:.4f}, {lon:.4f})",
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
        meta, sim = simular_y_guardar(pedido.lat, pedido.lon, pedido.anio, pedido.semilla
                                      if pedido.semilla is not None else 2026, pedido.parametros, pedido.nombre)
    except ValueError as e:
        error(400, str(e))
    except extraccion.ErrorFuente as e:
        error(502, str(e))
    almacen.guardar_sensor(meta["sensor_id"], sim["crudo"], meta, sim["verdadero"])
    return {"sensor_id": meta["sensor_id"], "resumen": almacen.resumen_sensor(meta)}


@app.post("/api/sensor/subir")
async def sensor_subir(archivo: UploadFile = File(...), anio: int | None = Form(None),
                       lat: float | None = Form(None), lon: float | None = Form(None),
                       nombre: str | None = Form(None)):
    contenido = await archivo.read(MAX_CSV_BYTES + 1)
    if len(contenido) > MAX_CSV_BYTES:
        error(413, "El archivo supera 100 MB.")
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
