import pandas as pd
import pytest

from nucleo import pipeline, simulador


def _analizar(era5, crudos, parametros=None, semilla=7):
    sim = simulador.simular_sensor(era5, 2024, 6.147148, -75.377316, semilla=semilla, parametros=parametros)
    sensor = pipeline.Sensor(crudo=sim["crudo"], verdadero=sim["verdadero"],
                             inyectados={k: v for k, v in sim["defectos"].items() if k != "descripcion_huecos"},
                             supuestos=sim["supuestos"])
    resultado, _ = pipeline.ejecutar_analisis(6.147148, -75.377316, 2024, sensor, crudos=crudos)
    return sim, resultado


@pytest.mark.parametrize("parametros", [None, {"a": 0.98, "b": 0.40}])
def test_el_pipeline_recupera_el_factor_verdadero(era5_ae4, crudos_ae4, parametros):
    sim, resultado = _analizar(era5_ae4, crudos_ae4, parametros)
    anual = resultado["factores"]["era5"]["anual"]
    assert abs(anual["factor"] - anual["factor_verdadero"]) < 0.005
    assert abs(anual["factor_verdadero"] - sim["factor_verdadero_anual"]) < 0.005
    assert resultado["simulado"] is True and resultado["supuestos"]
    for mes in resultado["factores"]["era5"]["mensual"]:
        assert abs(mes["factor"] - mes["factor_verdadero"]) < 0.01


def test_factor_depende_de_la_nubosidad(era5_ae4):
    sim = simulador.simular_sensor(era5_ae4, 2024, 6.147148, -75.377316, semilla=1)
    v = sim["verdadero"]
    dia = v[v["kt"] > 0]
    assert v["factor_verdadero"].between(0.70, 1.00).all()
    # Horas más despejadas -> factor más alto.
    assert dia.loc[dia["kt"] > 0.6, "factor_verdadero"].mean() > dia.loc[dia["kt"] < 0.3, "factor_verdadero"].mean()
    assert 0.80 <= sim["factor_verdadero_anual"] <= 0.98


def test_la_calidad_detecta_los_defectos_inyectados(era5_ae4, crudos_ae4):
    _sim, resultado = _analizar(era5_ae4, crudos_ae4)
    calidad = pd.DataFrame(resultado["calidad"])
    sensor = calidad[(calidad["fuente"] == "sensor") & calidad["inyectados"].notna()]
    assert len(sensor) >= 6
    assert (sensor["problemas_antes"] == sensor["inyectados"]).all()


def test_misma_semilla_mismo_sensor(era5_ae4):
    a = simulador.simular_sensor(era5_ae4, 2024, 6.147148, -75.377316, semilla=3)["crudo"]
    b = simulador.simular_sensor(era5_ae4, 2024, 6.147148, -75.377316, semilla=3)["crudo"]
    pd.testing.assert_frame_equal(a, b)
