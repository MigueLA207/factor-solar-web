import numpy as np
import pandas as pd
import pytest

from nucleo import sol, transformacion


@pytest.mark.parametrize("lon, esperado", [
    (-75.377316, 6),    # Rionegro: el +6 fijo de la AE4
    (-3.7038, 1),       # Madrid: offset 0
    (139.69, -8),       # Tokio: offset +9
    (-155.58, 11),      # Hawái: offset -10
    (-70.6693, 6),      # Santiago de Chile: offset -5
    (180.0, -11),
    (-180.0, 13),
])
def test_desfase_nasa_por_longitud(lon, esperado):
    assert sol.desfase_nasa_h(lon) == esperado


def test_elegir_desfase_recupera_el_desfase_real(era5_ae4):
    # NASA sintética = ERA5 expresada en una "LST" con un desfase distinto al de la regla (+7 en vez de +6).
    real = 7
    nasa = pd.DataFrame({"ts_lst": era5_ae4["ts_utc"] - pd.Timedelta(hours=real),
                         "irr_nasa": era5_ae4["irr_era5"] * 0.95, "t_aire_nasa": 20.0})
    elegido, info = transformacion.elegir_desfase_nasa(era5_ae4, nasa, -75.377316)
    assert elegido == real
    assert info["por_longitud_h"] == 6 and info["coincide_con_regla"] is False


def test_elegir_desfase_confirma_la_regla_con_nasa_real(era5_ae4, crudos_ae4):
    from nucleo import calidad, extraccion
    nasa, _, _ = calidad.limpiar_nasa(extraccion.leer_nasa(crudos_ae4["nasa"]), 6.147148, -75.377316)
    elegido, info = transformacion.elegir_desfase_nasa(era5_ae4, nasa, -75.377316)
    assert elegido == 6 and info["coincide_con_regla"] is True


def test_elevacion_mediodia_y_medianoche():
    # Rionegro, 21 de marzo: sol casi cenital al mediodía solar (~17:00 UTC) y bajo el horizonte a medianoche.
    marcas = pd.to_datetime(["2024-03-21 17:00", "2024-03-21 05:00"])
    e = sol.elevacion_solar(marcas, 6.147, -75.377)
    assert e[0] > 80 and e[1] < -60


def test_extraterrestre_hemisferio_sur():
    # Santiago (-33°): más irradiancia extraterrestre diaria en enero que en junio.
    enero = pd.date_range("2024-01-15 01:00", periods=24, freq="h")
    junio = pd.date_range("2024-06-15 01:00", periods=24, freq="h")
    g_ene = sol.irradiancia_extraterrestre_horaria(enero, -33.45, -70.67).sum()
    g_jun = sol.irradiancia_extraterrestre_horaria(junio, -33.45, -70.67).sum()
    assert g_ene > 1.8 * g_jun and np.isfinite(g_ene)
