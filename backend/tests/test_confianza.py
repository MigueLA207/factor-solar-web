"""Señales de confiabilidad del informe: año parcial, reloj del CSV, unidades, energía de NASA y día típico."""

import numpy as np
import pandas as pd
import pytest

from conftest import crudos_cache, sensor_horario_desde_era5
from nucleo import kpi, pipeline

MADRID = (40.4168, -3.7038, 2024)


def _correr(sensor_fn):
    lat, lon, anio = MADRID
    crudos = crudos_cache(lat, lon, anio)
    sensor = sensor_horario_desde_era5(crudos, anio)
    sensor = sensor_fn(sensor)
    resultado, tablas = pipeline.ejecutar_analisis(lat, lon, anio, sensor, crudos=crudos)
    return resultado, tablas


def test_subida_completa_no_dispara_senales():
    r, _ = _correr(lambda s: s)
    assert r["cobertura"]["anio_completo"] is True and r["cobertura"]["meses_sin_datos"] == []
    assert r["confiabilidad"] == {"factor_no_confiable": False, "motivo_no_confiable": None,
                                  "unidades_sospechosas": False, "motivo_unidades": None}
    assert r["desfase"]["era5_nasa_independiente"] is False and r["desfase"]["sensor_era5_independiente"] is True
    assert not any("Año parcial" in a for a in r["advertencias"])


def test_ano_parcial_marca_los_meses_con_datos():
    def solo_primer_semestre(sensor):
        sensor.crudo = sensor.crudo[sensor.crudo["ts_utc"] < "2024-07-01"].copy()
        return sensor
    r, _ = _correr(solo_primer_semestre)
    assert r["cobertura"]["anio_completo"] is False
    assert r["cobertura"]["meses_con_datos"] == ["ene", "feb", "mar", "abr", "may", "jun"]
    assert r["cobertura"]["meses_sin_datos"] == ["jul", "ago", "sep", "oct", "nov", "dic"]
    assert any("Año parcial" in a and "ene" in a for a in r["advertencias"])


def test_reloj_del_csv_corrido_marca_el_factor_como_no_confiable():
    def corrido(sensor):
        sensor.crudo = sensor.crudo.assign(irr_sitio=sensor.crudo["irr_sitio"].shift(2))     # reloj 2 h atrasado
        return sensor
    r, _ = _correr(corrido)
    assert r["desfase"]["mejor_desfase_h"]["sensor vs ERA5"] == 2
    assert r["confiabilidad"]["factor_no_confiable"] is True
    assert "desfase de hora" in r["confiabilidad"]["motivo_no_confiable"]
    assert any(a.startswith("Factor no confiable") for a in r["advertencias"])


@pytest.mark.parametrize("escala, esperado", [(0.001, True), (0.0004, True), (3.0, True), (1.0, False)])
def test_unidades_sospechosas(escala, esperado):
    # Sensor en kW/m² (÷1000) o con un factor absurdo: advertencia de unidades.
    def escalado(sensor):
        sensor.crudo = sensor.crudo.assign(irr_sitio=sensor.crudo["irr_sitio"] * escala / 0.9)
        return sensor
    r, _ = _correr(escalado)
    assert r["confiabilidad"]["unidades_sospechosas"] is esperado
    assert any("unidades" in a for a in r["advertencias"]) is esperado


def test_simulado_no_recibe_senales_de_csv(crudos_ae4):
    # El sensor simulado se fabrica con ERA5: las señales de "CSV subido" no aplican.
    sensor = pipeline.Sensor(crudo=pd.DataFrame(), simulado=True)
    assert pipeline._confiabilidad(sensor, pd.DataFrame(), {"sensor vs ERA5": 3}, 0.1, []) == {
        "factor_no_confiable": False, "motivo_no_confiable": None, "unidades_sospechosas": False,
        "motivo_unidades": None}


# ---------------------------------------------------------------------------
# kpi
# ---------------------------------------------------------------------------

def _integrado_pequeno():
    horas = pd.date_range("2024-01-01 06:00", periods=6, freq="h")
    return pd.DataFrame({
        "ts_utc": horas, "mes": 1, "es_diurna": True,
        "irr_sitio": [100.0, 200.0, 300.0, 400.0, 500.0, 600.0],
        "irr_era5": [110.0, 220.0, 330.0, 440.0, 550.0, 660.0],
        "irr_nasa": [120.0, np.nan, 340.0, np.nan, np.nan, 700.0],
    })


def test_energia_nasa_suma_solo_donde_hay_dato_y_lleva_sus_horas():
    fila = kpi.calcular_energia_mensual(_integrado_pequeno(), 0.9)[0]
    assert fila["n_horas"] == 6 and fila["nasa_n_horas"] == 3
    assert fila["nasa_kwh_m2"] == round((120 + 340 + 700) / 1000, 2)        # 1,16: sin tratar el vacío como 0
    assert fila["sensor_kwh_m2"] == 2.1 and fila["era5_sin_corregir_kwh_m2"] == 2.31
    sin_nasa = _integrado_pequeno().assign(irr_nasa=np.nan)
    fila2 = kpi.calcular_energia_mensual(sin_nasa, 0.9)[0]
    assert fila2["nasa_kwh_m2"] is None and fila2["nasa_n_horas"] == 0
    assert kpi.calcular_energia_mensual(_integrado_pequeno(), 0.9)[1]["nasa_kwh_m2"] is None   # mes sin horas


def test_dia_tipico_se_ubica_en_el_centro_del_intervalo():
    dia = kpi.calcular_dia_tipico(_integrado_pequeno(), 0.0)           # lon 0: hora local = UTC
    assert len(dia) == 24 and [d["hora_centro"] for d in dia] == [h + 0.5 for h in range(24)]
    por_fin = {d["hora_local"]: d for d in dia}
    # La etiqueta 6 es el intervalo (5:00, 6:00]: su centro es 5,5. La etiqueta 0 es (23:00, 24:00]: centro 23,5.
    assert por_fin[6]["hora_centro"] == 5.5 and por_fin[0]["hora_centro"] == 23.5
    # Solo las horas con las tres fuentes entran al promedio (la etiqueta 7 tiene NASA vacía).
    assert por_fin[6]["sensor"] == 100.0 and por_fin[6]["nasa"] == 120.0
    assert por_fin[7]["sensor"] is None and por_fin[8]["sensor"] == 300.0
