"""
Prueba cruzada: con el sensor simulado de la AE4 y las mismas respuestas crudas de ERA5 y NASA,
el núcleo duplicado debe dar los factores anuales de la AE4: ERA5 0,9103 y NASA 0,9809 (±0,0005).
"""

import pandas as pd

from nucleo import pipeline, reglas

R = reglas.REFERENCIA


def test_reproduce_los_factores_de_la_ae4(crudos_ae4):
    crudo = pd.read_csv(R / "ae4_sensor_rionegro_2024_CRUDO.csv.gz",
                        dtype={"irr_sitio": "float64", "t_modulo": "float64"})
    crudo["ts_utc"] = pd.to_datetime(crudo["ts_utc"], format="%Y-%m-%d %H:%M:%S")
    sensor = pipeline.Sensor(crudo=crudo, supuestos=["sensor simulado de la AE4"])
    resultado, _ = pipeline.ejecutar_analisis(6.147148, -75.377316, 2024, sensor,
                                              regimen="bimodal_andino", crudos=crudos_ae4)
    era5 = resultado["factores"]["era5"]["anual"]
    nasa = resultado["factores"]["nasa"]["anual"]
    assert abs(era5["factor"] - 0.9103) <= 0.0005
    assert abs(nasa["factor"] - 0.9809) <= 0.0005
    assert era5["n_horas"] == 4846
    assert resultado["desfase"]["desfase_nasa_aplicado_h"] == 6
    assert resultado["desfase"]["mejor_desfase_h"] == {"ERA5 vs NASA": 0, "sensor vs ERA5": 0}
    assert resultado["consistencia"]["era5_vs_nasa"]["correlacion"] == 0.9467
    assert resultado["consistencia"]["era5_vs_nasa"]["diferencia_total_pct"] == 7.76
    # La frase para personas va con coma decimal, igual que la interfaz.
    conclusion = resultado["consistencia"]["era5_vs_nasa"]["conclusion"]
    assert "Correlación 0,947" in conclusion and "+7,76 %" in conclusion
    fases = {f["periodo"]: f["factor"] for f in resultado["fases_bimodal"]["era5"]}
    assert fases == {"seca_1": 0.9493, "lluvias_1": 0.8789, "seca_2": 0.9283, "lluvias_2": 0.8476}
