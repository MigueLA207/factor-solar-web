"""Identificadores, parámetros acotados, exposición local, caché atómica y errores de análisis."""

import threading
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import almacen
from app import app
from nucleo import extraccion, pipeline, reglas, sensor_csv

cliente = TestClient(app, base_url="http://localhost")
cliente_sin_excepciones = TestClient(app, base_url="http://localhost", raise_server_exceptions=False)

MALOS = [".", "..", "C:x", "C:\\Windows", "../etc", "an-../../x", "an-0123456789/", "", " ", "an-XYZ", "AN-0123456789",
         "an-0123456789a", "an-012345678", "..\\..", "ejemplo-../x", "ejemplo-"]


@pytest.mark.parametrize("malo", MALOS)
def test_ids_malos_no_tocan_el_disco(malo, monkeypatch):
    def no_debe_leer_disco(*_a, **_k):
        raise AssertionError("se accedió al disco con un id no válido")
    # Cualquier acceso a las carpetas de datos explotaría: el id se valida antes.
    for nombre in ("ANALISIS", "SENSORES", "EJEMPLOS"):
        monkeypatch.setattr(almacen.reglas, nombre, _Explosivo(no_debe_leer_disco))
    assert almacen.id_analisis_valido(malo) is False
    assert almacen.estado_analisis(malo) is None and almacen.zip_analisis(malo) is None
    assert almacen.id_sensor_valido(malo) is False
    assert almacen.leer_meta(malo) is None and almacen.cargar_sensor(malo) is None
    with pytest.raises(ValueError):
        almacen.guardar_sensor(malo, pd.DataFrame(), {})


class _Explosivo:
    def __init__(self, funcion):
        self._funcion = funcion

    def __truediv__(self, _otro):
        return self._funcion()

    def glob(self, *_a):
        return self._funcion()


def test_ids_validos():
    assert almacen.id_analisis_valido(almacen.nuevo_id("an"))
    assert almacen.id_sensor_valido(almacen.nuevo_id("sim")) and almacen.id_sensor_valido(almacen.nuevo_id("csv"))
    assert almacen.id_sensor_valido("ejemplo-rionegro")
    assert not almacen.id_sensor_valido("ejemplo-no_existe")


@pytest.mark.parametrize("malo", ["..", "C:x", "an-1", "%2e%2e", "an-0123456789%2f.."])
def test_api_rechaza_ids_malos(malo):
    assert cliente.get(f"/api/analisis/{malo}").status_code == 404
    assert cliente.get(f"/api/analisis/{malo}/descargar").status_code == 404
    r = cliente.post("/api/analisis", json={"lat": 6.1, "lon": -75.4, "anio": 2024, "sensor_id": malo})
    assert r.status_code in (404, 422) and "mensaje" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Parámetros acotados
# ---------------------------------------------------------------------------

BASE = {"lat": 6.1471, "lon": -75.3773, "anio": 2024}


@pytest.mark.parametrize("cambio, texto", [
    ({"parametros": {"a": 5}}, "parametros.a: debe ser menor o igual que 2"),
    ({"parametros": {"b": -0.1}}, "parametros.b: debe ser mayor o igual que 0"),
    ({"parametros": {"ruido_ventana_min": 0}}, "ruido_ventana_min"),
    ({"parametros": {"ruido_ventana_min": 61}}, "ruido_ventana_min"),
    ({"parametros": {"defectos": {"huecos_cortos": 10_001}}}, "parametros.defectos.huecos_cortos"),
    ({"parametros": {"defectos": {"huecos_cortos": -1}}}, "parametros.defectos.huecos_cortos"),
    ({"parametros": {"defectos": {"no_existe": 1}}}, "no es un parámetro admitido"),
    ({"parametros": {"factor_min": 0.9, "factor_max": 0.8}}, "factor_min no puede ser mayor que factor_max"),
    ({"parametros": {"ruido_sigma": 99}}, "ruido_sigma"),
    ({"parametros": {"inventado": 1}}, "no es un parámetro admitido"),
    ({"anio": 1999}, "anio: debe ser mayor o igual que"),
    ({"semilla": -1}, "semilla"),
    ({"nombre": "x" * 500}, "admite como máximo 120"),
    ({"lat": 123}, "lat: debe ser menor o igual que 90"),
])
def test_parametros_fuera_de_rango_dan_422_en_espanol(cambio, texto, monkeypatch):
    monkeypatch.setattr(extraccion, "obtener_openmeteo", lambda *a: pytest.fail("no debe consultar la API"))
    r = cliente.post("/api/sensor/simular", json={**BASE, **cambio})
    assert r.status_code == 422, r.text
    detalle = r.json()["detail"]
    assert detalle["mensaje"].startswith("Datos del pedido inválidos") and texto in detalle["mensaje"]


def test_parametros_validos_pasan_al_simulador(monkeypatch):
    visto = {}

    def falso(lat, lon, anio, semilla=2026, parametros=None, nombre=None, sensor_id=None):
        visto["parametros"] = parametros
        raise ValueError("se detiene aquí")
    monkeypatch.setattr("app.simular_y_guardar", falso)
    r = cliente.post("/api/sensor/simular", json={**BASE, "parametros": {"a": 1.1, "defectos": {"huecos_cortos": 0}}})
    assert r.status_code == 400 and visto["parametros"] == {"a": 1.1, "defectos": {"huecos_cortos": 0}}


# ---------------------------------------------------------------------------
# Exposición local
# ---------------------------------------------------------------------------

def test_host_ajeno_se_rechaza():
    ajeno = TestClient(app, base_url="http://evil.example")
    assert ajeno.get("/api/salud").status_code == 400
    assert cliente.get("/api/salud").status_code == 200
    assert TestClient(app, base_url="http://127.0.0.1:8000").get("/api/salud").status_code == 200


@pytest.mark.parametrize("origen, esperado", [
    ("http://evil.example", 403), ("https://localhost", 403), ("http://localhost:9999", 403), ("null", 403),
    ("http://localhost", 200),                    # mismo origen (Host: localhost)
    ("http://localhost:5173", 200), ("http://127.0.0.1:5175", 200),
])
def test_origen_en_post(origen, esperado):
    r = cliente.post("/api/analisis", json={"lat": 6.1, "lon": -75.4, "anio": 2024, "sensor_id": "sim-0000000000"},
                     headers={"Origin": origen})
    assert (r.status_code == 403) == (esperado == 403)
    if esperado == 403:
        assert "otro sitio web" in r.json()["detail"]["mensaje"]


def test_limite_de_subida_30_mb():
    from app import MAX_CSV_BYTES
    assert MAX_CSV_BYTES == 30 * 1024 * 1024
    r = cliente.post("/api/sensor/subir", files={"archivo": ("g.csv", b"x" * (MAX_CSV_BYTES + 1), "text/csv")})
    assert r.status_code == 413 and "30 MB" in r.json()["detail"]["mensaje"]


def test_subida_no_bloquea_el_servidor():
    import inspect

    from app import sensor_subir
    assert not inspect.iscoroutinefunction(sensor_subir)       # se corre en el hilo de FastAPI


def test_error_inesperado_da_500_en_espanol_sin_traza(monkeypatch):
    def explota():
        raise RuntimeError("secreto interno C:\\ruta\\privada")
    monkeypatch.setattr(almacen, "listar_ejemplos", explota)
    r = cliente_sin_excepciones.get("/api/ejemplos")
    assert r.status_code == 500
    cuerpo = r.text
    assert "error inesperado" in cuerpo and "Traceback" not in cuerpo
    assert "secreto" not in cuerpo and "privada" not in cuerpo


# ---------------------------------------------------------------------------
# CSV: fechas ambiguas
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fecha", ["03/04/2024 13:00", "3/4/2024 13:00:00", "2024/04/03 13:00"])
def test_csv_con_fechas_con_barras_se_rechaza(fecha):
    horas = pd.date_range("2024-01-01 00:00", "2024-12-31 23:00", freq="h")
    texto = pd.DataFrame({"ts_utc": [fecha] * len(horas), "irr_sitio": 1.0}).to_csv(index=False).encode()
    with pytest.raises(sensor_csv.ErrorCSV) as error:
        sensor_csv.validar_csv(texto)
    assert "ambiguas" in str(error.value) and "AAAA-MM-DD" in str(error.value)


def test_csv_acepta_iso_con_t_y_con_zona():
    horas = pd.date_range("2024-01-01 00:00", "2024-12-31 23:00", freq="h")
    for formato in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%SZ"):
        tabla = pd.DataFrame({"ts_utc": horas.strftime(formato), "irr_sitio": 600.0})
        datos, reporte = sensor_csv.validar_csv(tabla.to_csv(index=False).encode())
        assert reporte["valido"] and datos["ts_utc"].iloc[0] == pd.Timestamp("2024-01-01 00:00")


# ---------------------------------------------------------------------------
# Caché atómica y validada
# ---------------------------------------------------------------------------

@pytest.fixture
def caja_de_cache(tmp_path, monkeypatch, crudos_ae4):
    monkeypatch.setattr(reglas, "CACHE", tmp_path)
    llamadas = []

    def falso(fuente, url, parametros, marca, espera_base_s=None):
        llamadas.append(fuente)
        time.sleep(0.05)
        return crudos_ae4["era5"] if "Open-Meteo" in fuente else crudos_ae4["nasa"]
    monkeypatch.setattr(extraccion, "descargar_con_reintentos", falso)
    return tmp_path, llamadas


@pytest.mark.parametrize("fuente", ["era5", "nasa"])
@pytest.mark.parametrize("dano", ["truncado", "vacio", "basura"])
def test_cache_corrupta_se_borra_y_se_vuelve_a_pedir(caja_de_cache, fuente, dano):
    tmp, llamadas = caja_de_cache
    obtener = extraccion.obtener_openmeteo if fuente == "era5" else extraccion.obtener_nasa
    texto, origen = obtener(6.1471, -75.3773, 2024)
    assert origen == "API en vivo" and len(llamadas) == 1
    archivo = next(tmp.iterdir())
    assert not list(tmp.glob("*.tmp"))
    assert obtener(6.1471, -75.3773, 2024)[1] == "caché local" and len(llamadas) == 1
    archivo.write_text({"truncado": texto[: len(texto) // 3], "vacio": "", "basura": "\x00\x01 no es una respuesta"}[dano],
                       encoding="utf-8")
    texto2, origen2 = obtener(6.1471, -75.3773, 2024)
    assert origen2 == "API en vivo" and len(llamadas) == 2 and texto2 == texto
    assert archivo.read_text(encoding="utf-8") == texto and not list(tmp.glob("*.tmp"))


def test_respuesta_nueva_invalida_no_se_guarda(tmp_path, monkeypatch):
    monkeypatch.setattr(reglas, "CACHE", tmp_path)
    monkeypatch.setattr(extraccion, "descargar_con_reintentos", lambda *a, **k: "ALLSKY_SFC_SW_DWN pero no es JSON")
    with pytest.raises(extraccion.ErrorFuente):
        extraccion.obtener_nasa(1.0, 2.0, 2024)
    assert list(tmp_path.iterdir()) == []


def test_escritura_atomica_no_deja_archivo_a_medias(tmp_path, monkeypatch):
    destino = tmp_path / "x.csv"
    destino.write_text("viejo", encoding="utf-8")

    def falla(*_a):
        raise OSError("falla")
    monkeypatch.setattr(extraccion.os, "replace", falla)
    with pytest.raises(OSError):
        extraccion._escribir_atomico(destino, "nuevo")
    assert destino.read_text(encoding="utf-8") == "viejo" and list(tmp_path.glob("*.tmp")) == []


def test_dos_analisis_del_mismo_punto_descargan_una_sola_vez(caja_de_cache):
    _tmp, llamadas = caja_de_cache
    resultados = []
    hilos = [threading.Thread(target=lambda: resultados.append(extraccion.obtener_openmeteo(1.5, 2.5, 2024)))
             for _ in range(6)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert len(llamadas) == 1 and len(resultados) == 6 and len({r[0] for r in resultados}) == 1


# ---------------------------------------------------------------------------
# Errores entre etapas y memoria acotada
# ---------------------------------------------------------------------------

def _esperar_fin(analisis_id):
    for _ in range(200):
        estado = almacen.estado_analisis(analisis_id)
        if estado is None or estado["estado"] != "en_curso":
            return estado
        time.sleep(0.05)
    pytest.fail("no terminó")


@pytest.mark.parametrize("hasta", ["era5", "factores", "resumen"])
def test_excepcion_entre_etapas_deja_una_etapa_en_error(monkeypatch, hasta):
    # Falla DESPUÉS de marcar `hasta` como lista y ANTES de empezar la siguiente: no debe quedar todo en verde.
    orden = [e[1] for e in pipeline.ETAPAS]

    def falso(lat, lon, anio, sensor, regimen, avance, nombre=None):
        for paso in orden[: orden.index(hasta) + 1]:
            avance(paso, "listo", "ok")
        raise RuntimeError("falló entre etapas")
    monkeypatch.setattr(almacen.pipeline, "ejecutar_analisis", falso)
    estado = _esperar_fin(almacen.iniciar_analisis(6.1, -75.4, 2024, None))
    assert estado["estado"] == "error" and estado["resultado"] is None
    errores = [e for e in estado["etapas"] if e["estado"] == "error"]
    assert len(errores) == 1 and "falló entre etapas" in errores[0]["detalle"]
    esperada = orden[orden.index(hasta) + 1] if hasta != "resumen" else orden[-1]
    assert errores[0]["paso"] == esperada


def test_falla_al_guardar_marca_la_ultima_etapa(monkeypatch):
    def todo_listo(lat, lon, anio, sensor, regimen, avance, nombre=None):
        for _fase, paso, _titulo in pipeline.ETAPAS:
            avance(paso, "listo", "ok")
        return {"x": 1}, {}
    monkeypatch.setattr(almacen.pipeline, "ejecutar_analisis", todo_listo)

    def disco_lleno(*_a):
        raise OSError("disco lleno")
    monkeypatch.setattr(almacen, "_guardar_resultado", disco_lleno)
    estado = _esperar_fin(almacen.iniciar_analisis(6.1, -75.4, 2024, None))
    assert estado["estado"] == "error" and estado["etapas"][-1]["estado"] == "error"


def test_polling_no_devuelve_resultado_hasta_estar_listo(monkeypatch):
    liberar = threading.Event()

    def lento(lat, lon, anio, sensor, regimen, avance, nombre=None):
        avance("era5", "en_curso", "")
        liberar.wait(5)
        return {"dato": 1}, {}
    monkeypatch.setattr(almacen.pipeline, "ejecutar_analisis", lento)
    monkeypatch.setattr(almacen, "_guardar_resultado", lambda *a: None)
    analisis_id = almacen.iniciar_analisis(6.1, -75.4, 2024, None)
    en_curso = almacen.estado_analisis(analisis_id)
    assert en_curso["estado"] == "en_curso" and en_curso["resultado"] is None
    liberar.set()
    assert _esperar_fin(analisis_id)["resultado"]["dato"] == 1


def test_memoria_de_analisis_acotada(monkeypatch):
    monkeypatch.setattr(almacen, "MAX_ANALISIS_EN_MEMORIA", 3)
    monkeypatch.setattr(almacen.pipeline, "ejecutar_analisis", lambda *a, **k: ({"x": 1}, {}))
    monkeypatch.setattr(almacen, "_guardar_resultado", lambda *a: None)
    ids = []
    for _ in range(8):
        ids.append(almacen.iniciar_analisis(6.1, -75.4, 2024, None))
        _esperar_fin(ids[-1])
    time.sleep(0.2)
    terminados = [i for i in ids if i in almacen._analisis]
    assert len(terminados) <= 3 and ids[-1] in terminados
