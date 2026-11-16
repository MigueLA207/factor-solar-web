"""La regla de hora de NASA sale de la longitud de la celda que NASA devolvió, y el pipeline usa el corrimiento ELEGIDO."""

import json

import pandas as pd
import pytest

from conftest import crudos_cache, sensor_horario_desde_era5
from nucleo import calidad, extraccion, pipeline, sol, transformacion

# (lat, lon, año, corrimiento que de verdad maximiza la correlación con ERA5, qué da la regla round(lon/15))
SITIOS = {
    "Turín": (45.07, 7.69, 2023, 1, 0),
    "Tokio": (35.68, 139.69, 2023, -8, -8),
    "Sídney": (-33.87, 151.21, 2023, -9, -9),
    "Hawái": (19.9, -155.58, 2023, 11, 11),
    "Delhi": (28.61, 77.21, 2023, -4, -4),
    "Santiago": (-33.4489, -70.6693, 2024, 6, 6),
    "Berna": (46.95, 7.44, 2023, 1, 1),
    "Rionegro": (6.1471, -75.3773, 2024, 6, 6),
}


@pytest.mark.parametrize("nombre", SITIOS)
def test_regla_sobre_la_longitud_de_la_celda_y_corrimiento_elegido(nombre):
    lat, lon, anio, esperado, regla = SITIOS[nombre]
    crudos = crudos_cache(lat, lon, anio)
    cabecera = extraccion.leer_cabecera_nasa(crudos["nasa"])
    assert cabecera["lon"] is not None
    assert sol.desfase_nasa_h(cabecera["lon"]) == regla
    era5 = extraccion.leer_openmeteo(crudos["era5"])
    nasa, _, _ = calidad.limpiar_nasa(extraccion.leer_nasa(crudos["nasa"]), lat, cabecera["lon"])
    elegido, info = transformacion.elegir_desfase_nasa(era5, nasa, cabecera["lon"])
    assert elegido == esperado and info["por_longitud_h"] == regla
    assert info["coincide_con_regla"] is (esperado == regla)
    assert set(info["correlacion_por_candidato"]) == {f"{regla - 1:+d}", f"{regla:+d}", f"{regla + 1:+d}"}


def test_turin_la_regla_falla_por_una_hora_y_el_pipeline_usa_el_elegido():
    # Turín (lon 7,69) cae justo después del borde de franja: round(lon/15) da offset +1, NASA usó +0.
    lat, lon, anio, esperado, regla = SITIOS["Turín"]
    crudos = crudos_cache(lat, lon, anio)
    resultado, _ = pipeline.ejecutar_analisis(lat, lon, anio, sensor_horario_desde_era5(crudos, anio), crudos=crudos)
    desfase = resultado["desfase"]
    assert desfase["desfase_nasa_aplicado_h"] == esperado == 1
    assert desfase["verificacion_desfase_nasa"]["por_longitud_h"] == regla == 0
    assert desfase["verificacion_desfase_nasa"]["coincide_con_regla"] is False
    assert any("La regla de longitud daba" in a for a in resultado["advertencias"])
    # La fila de calidad de la hora y la etiqueta del paso usan el corrimiento elegido, no el de la regla.
    fila_hora = next(f for f in resultado["calidad"] if "hora solar local" in f["regla"])
    assert "UTC+0" in fila_hora["regla"] and "+1 h" in fila_hora["accion"]
    assert resultado["sitio"]["offset_hora_solar_local_h"] == 0
    # El chequeo ERA5–NASA se declara no independiente.
    assert desfase["era5_nasa_independiente"] is False
    assert "alineación de la hora" not in resultado["consistencia"]["era5_vs_nasa"]["conclusion"]


@pytest.mark.parametrize("nombre", ["Sídney", "Tokio", "Hawái"])
def test_longitud_lejana_y_hemisferio_sur_recortan_el_anio_por_el_pipeline(nombre):
    lat, lon, anio, esperado, _ = SITIOS[nombre]
    crudos = crudos_cache(lat, lon, anio)
    resultado, tablas = pipeline.ejecutar_analisis(lat, lon, anio, sensor_horario_desde_era5(crudos, anio), crudos=crudos)
    assert resultado["desfase"]["desfase_nasa_aplicado_h"] == esperado
    assert resultado["desfase"]["horas_nasa_fuera_del_anio"] > 0          # el día extra de cada lado se recorta
    integrado = tablas["integrado_horario.csv"]
    assert len(integrado) == 8760 and integrado["ts_utc"].iloc[0] == pd.Timestamp(f"{anio}-01-01 00:00")
    assert integrado["irr_nasa"].notna().sum() > 8000                      # el año UTC queda completo, sin huecos de borde
    assert abs(resultado["factores"]["era5"]["anual"]["factor"] - 0.9) < 0.002
    assert resultado["desfase"]["mejor_desfase_h"] == {"ERA5 vs NASA": 0, "sensor vs ERA5": 0}


def test_la_regla_usa_la_longitud_de_la_celda_de_la_cabecera_no_la_pedida(crudos_ae4):
    # Misma respuesta de NASA pero con otra longitud de celda en la cabecera: la regla debe seguir a la cabecera.
    datos = json.loads(crudos_ae4["nasa"])
    datos["geometry"]["coordinates"][0] = -120.0            # offset -8 -> +9 h
    crudos = {"era5": crudos_ae4["era5"], "nasa": json.dumps(datos)}
    era5 = extraccion.leer_openmeteo(crudos["era5"])
    sensor = pipeline.Sensor(crudo=pd.DataFrame({"ts_utc": era5["ts_utc"], "irr_sitio": era5["irr_era5"] * 0.9,
                                                 "t_modulo": float("nan")}), frecuencia="hora", simulado=False)
    resultado, _ = pipeline.ejecutar_analisis(6.147148, -75.377316, 2024, sensor, crudos=crudos)
    assert resultado["desfase"]["verificacion_desfase_nasa"]["por_longitud_h"] == 9
    assert resultado["desfase"]["longitud_regla_nasa"] == -120.0
