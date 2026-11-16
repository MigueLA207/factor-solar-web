import numpy as np
import pandas as pd
import pytest

from nucleo import sensor_csv


def _csv(tabla):
    return tabla.to_csv(index=False, date_format="%Y-%m-%d %H:%M:%S").encode("utf-8")


def test_csv_horario_valido():
    horas = pd.date_range("2024-01-01 00:00", "2024-12-31 23:00", freq="h")
    tabla = pd.DataFrame({"ts_utc": horas, "irr_sitio": np.linspace(0, 900, len(horas)).round(1)})
    datos, reporte = sensor_csv.validar_csv(_csv(tabla))
    assert reporte["valido"] and reporte["frecuencia"] == "hora" and reporte["anio"] == 2024
    assert reporte["tiene_temperatura"] is False and datos["t_modulo"].isna().all()
    assert reporte["cobertura_pct"] == 100.0


def test_csv_por_minuto_con_punto_y_coma_y_coma_decimal():
    minutos = pd.date_range("2023-03-01 00:00", "2023-04-30 23:59", freq="min")
    tabla = pd.DataFrame({"ts_utc": minutos.strftime("%Y-%m-%d %H:%M:%S"),
                          "irr_sitio": ["12,5"] * len(minutos), "t_modulo": ["20,1"] * len(minutos)})
    texto = tabla.to_csv(index=False, sep=";").encode("utf-8")
    datos, reporte = sensor_csv.validar_csv(texto)
    assert reporte["frecuencia"] == "minuto" and reporte["anio"] == 2023
    assert datos["irr_sitio"].iloc[0] == 12.5
    assert any("cubre" in a for a in reporte["advertencias"])     # ~16 % del año: aviso, no error


def test_csv_con_zona_horaria_se_convierte_a_utc():
    horas = pd.date_range("2024-01-01 00:00", "2024-12-31 23:00", freq="h", tz="America/Bogota")
    tabla = pd.DataFrame({"ts_utc": horas.strftime("%Y-%m-%dT%H:%M:%S%z"), "irr_sitio": 1.0})
    datos, reporte = sensor_csv.validar_csv(tabla.to_csv(index=False).encode())
    assert datos["ts_utc"].iloc[0] == pd.Timestamp("2024-01-01 05:00")
    assert any("zona horaria" in a for a in reporte["advertencias"])


@pytest.mark.parametrize("tabla, texto", [
    (pd.DataFrame({"fecha": ["2024-01-01 00:00:00"], "irr_sitio": [1]}), "Faltan columnas"),
    (pd.DataFrame({"ts_utc": pd.date_range("2024-01-01", periods=500, freq="10min"), "irr_sitio": 1.0}),
     "frecuencia"),
    (pd.DataFrame({"ts_utc": pd.date_range("2024-01-01", periods=100, freq="h"), "irr_sitio": 1.0}), "cubre solo"),
    (pd.DataFrame({"ts_utc": pd.date_range("2010-01-01", periods=8760, freq="h"), "irr_sitio": 1.0}),
     "fuera del rango"),
])
def test_csv_invalidos(tabla, texto):
    with pytest.raises(sensor_csv.ErrorCSV) as error:
        sensor_csv.validar_csv(_csv(tabla))
    assert texto in str(error.value)
