import pandas as pd

from nucleo import kpi


def test_factor_es_cociente_de_sumas_no_promedio_de_cocientes():
    integrado = pd.DataFrame({
        "mes": [1, 1, 1, 1], "es_diurna": [True, True, True, False],
        "irr_sitio": [90.0, 400.0, None, 5.0], "irr_era5": [100.0, 500.0, 300.0, 10.0],
        "irr_nasa": [100.0, 400.0, 300.0, 10.0],
    })
    factores = kpi.calcular_factores(integrado)
    # Solo cuentan las horas diurnas con sensor y fuente: (90 + 400) / (100 + 500).
    assert factores["era5"]["anual"]["factor"] == round(490 / 600, 4)
    assert factores["era5"]["anual"]["n_horas"] == 2
    assert factores["nasa"]["anual"]["factor"] == round(490 / 500, 4)
    # El promedio de cocientes daría (0,9 + 0,8) / 2 = 0,85: no es lo que se calcula.
    assert factores["era5"]["anual"]["factor"] != 0.85
    assert factores["era5"]["mensual"][0]["factor"] == round(490 / 600, 4)
    assert factores["era5"]["mensual"][1]["factor"] is None


def test_factor_verdadero_ponderado_por_energia_era5():
    integrado = pd.DataFrame({"mes": [1, 1], "es_diurna": [True, True], "irr_sitio": [80.0, 270.0],
                              "irr_era5": [100.0, 300.0], "irr_nasa": [100.0, 300.0],
                              "factor_verdadero": [0.8, 0.9]})
    anual = kpi.calcular_factores(integrado)["era5"]["anual"]
    assert anual["factor_verdadero"] == round((0.8 * 100 + 0.9 * 300) / 400, 4)
