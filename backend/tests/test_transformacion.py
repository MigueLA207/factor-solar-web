import numpy as np
import pandas as pd

from nucleo import transformacion


def test_hora_h_promedia_los_minutos_de_h_menos_1_a_h():
    minutos = transformacion.calendario_minutos(2024)
    sensor = pd.DataFrame({"ts_utc": minutos, "irr_sitio": 0.0, "t_modulo": 20.0})
    # Minutos 00:01..01:00 valen 100; el 00:00 y el 01:01 valen 999 (no deben entrar en la hora 01:00).
    en_hora = (sensor.ts_utc > "2024-01-01 00:00") & (sensor.ts_utc <= "2024-01-01 01:00")
    sensor.loc[en_hora, "irr_sitio"] = 100.0
    sensor.loc[sensor.ts_utc == "2024-01-01 00:00", "irr_sitio"] = 999.0
    sensor.loc[sensor.ts_utc == "2024-01-01 01:01", "irr_sitio"] = 999.0
    horario = transformacion.agregar_sensor_a_hora(sensor, 2024).set_index("ts_utc")
    assert len(horario) == 8784
    assert horario.loc["2024-01-01 01:00", "irr_sitio"] == 100.0
    # La hora 00:00 es (23:00, 00:00]: solo tiene el minuto 00:00 -> menos de 48 minutos -> vacía.
    assert horario.loc["2024-01-01 00:00", "minutos_validos"] == 1
    assert np.isnan(horario.loc["2024-01-01 00:00", "irr_sitio"])


def test_hora_con_menos_de_48_minutos_queda_vacia():
    minutos = transformacion.calendario_minutos(2024)
    sensor = pd.DataFrame({"ts_utc": minutos, "irr_sitio": 50.0, "t_modulo": 20.0})
    en_hora = (sensor.ts_utc > "2024-05-01 11:00") & (sensor.ts_utc <= "2024-05-01 12:00")
    sensor.loc[sensor.index[en_hora][:13], "irr_sitio"] = np.nan          # quedan 47 minutos válidos
    en_otra = (sensor.ts_utc > "2024-05-01 12:00") & (sensor.ts_utc <= "2024-05-01 13:00")
    sensor.loc[sensor.index[en_otra][:12], "irr_sitio"] = np.nan          # quedan 48
    horario = transformacion.agregar_sensor_a_hora(sensor, 2024).set_index("ts_utc")
    assert np.isnan(horario.loc["2024-05-01 12:00", "irr_sitio"])
    assert horario.loc["2024-05-01 13:00", "irr_sitio"] == 50.0


def test_chequeo_de_desfase_detecta_una_hora_corrida(era5_ae4):
    integrado = pd.DataFrame({"irr_era5": era5_ae4["irr_era5"], "irr_nasa": era5_ae4["irr_era5"],
                              "irr_sitio": era5_ae4["irr_era5"].shift(1)})
    _tabla, mejores, avisos = transformacion.chequear_desfase(integrado)
    assert mejores["ERA5 vs NASA"] == 0
    assert mejores["sensor vs ERA5"] != 0 and len(avisos) == 1
