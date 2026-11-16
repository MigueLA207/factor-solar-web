"""Extremo a extremo por la API. Usa la caché de datos/cache/ (si falta, consulta las API en vivo)."""

import time

import pytest
from fastapi.testclient import TestClient

import almacen
from app import app

cliente = TestClient(app)


def _esperar(analisis_id, limite_s=300):
    inicio = time.time()
    while time.time() - inicio < limite_s:
        estado = cliente.get(f"/api/analisis/{analisis_id}").json()
        if estado["estado"] != "en_curso":
            return estado
        time.sleep(0.5)
    pytest.fail("el análisis no terminó a tiempo")


def test_salud_y_ejemplos():
    assert cliente.get("/api/salud").json()["estado"] == "ok"
    ejemplos = cliente.get("/api/ejemplos").json()["ejemplos"]
    assert {e["slug"] for e in ejemplos} >= {"rionegro", "barranquilla", "bogota", "madrid", "santiago"}
    assert all(e["simulado"] for e in ejemplos)


def test_analisis_de_ejemplo_rionegro_2024():
    pedido = {"lat": 6.147148, "lon": -75.377316, "anio": 2024, "sensor_id": "ejemplo-rionegro",
              "regimen": "bimodal_andino"}
    analisis_id = cliente.post("/api/analisis", json=pedido).json()["analisis_id"]
    estado = _esperar(analisis_id)
    assert estado["estado"] == "listo", estado.get("error")
    assert estado["etapas"][0]["fase"] == "E" and all(e["estado"] == "listo" for e in estado["etapas"])
    r = estado["resultado"]
    assert r["simulado"] is True and r["etiqueta_sensor"] == "SIMULADO"
    anual = r["factores"]["era5"]["anual"]
    assert abs(anual["factor"] - anual["factor_verdadero"]) < 0.005
    assert r["desfase"]["ok"] and "fases_bimodal" in r
    assert len(r["dia_tipico"]) == 24 and len(r["energia_mensual"]) == 12
    zip_ = cliente.get(f"/api/analisis/{analisis_id}/descargar")
    assert zip_.status_code == 200 and zip_.content[:2] == b"PK"


def test_subir_csv_horario_y_analizar():
    # CSV horario armado desde el sensor de ejemplo de Madrid (agregado a hora con la convención correcta).
    sensor, _meta = almacen.cargar_sensor("ejemplo-madrid")
    serie = sensor.crudo.drop_duplicates("ts_utc").set_index("ts_utc")["irr_sitio"].clip(0, 1500)
    horario = serie.resample("h", closed="right", label="right").mean().loc["2024"].round(1).reset_index()
    texto = horario.to_csv(index=False, date_format="%Y-%m-%d %H:%M:%S").encode()
    respuesta = cliente.post("/api/sensor/subir", files={"archivo": ("madrid_horario.csv", texto, "text/csv")})
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["validacion"]["frecuencia"] == "hora" and cuerpo["resumen"]["simulado"] is False
    pedido = {"lat": 40.4168, "lon": -3.7038, "anio": 2024, "sensor_id": cuerpo["sensor_id"]}
    estado = _esperar(cliente.post("/api/analisis", json=pedido).json()["analisis_id"])
    assert estado["estado"] == "listo", estado.get("error")
    r = estado["resultado"]
    assert r["simulado"] is False and r["factores"]["verdadero_anual"] is None
    assert 0.85 < r["factores"]["era5"]["anual"]["factor"] < 0.97
    assert r["desfase"]["mejor_desfase_h"]["sensor vs ERA5"] == 0


def test_errores_claros():
    r = cliente.post("/api/analisis", json={"lat": 6.1, "lon": -75.4, "anio": 2024, "sensor_id": "no-existe"})
    assert r.status_code == 404 and "No existe" in r.json()["detail"]["mensaje"]
    r = cliente.post("/api/analisis", json={"lat": 6.1, "lon": -75.4, "anio": 2030, "sensor_id": "ejemplo-rionegro"})
    assert r.status_code == 400 and "año" in r.json()["detail"]["mensaje"]
    r = cliente.post("/api/sensor/subir", files={"archivo": ("x.csv", b"a,b\n1,2\n", "text/csv")})
    assert r.status_code == 422 and "Faltan columnas" in r.json()["detail"]["mensaje"]
