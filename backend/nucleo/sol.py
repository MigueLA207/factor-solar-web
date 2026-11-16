"""
Geometría solar y convenciones de hora, parametrizadas por el sitio.

- elevacion_solar: fórmula aproximada de la NOAA (copiada de la AE4, con lat/lon como argumentos).
- marcar_horas_diurnas: misma regla de la AE4 (sol sobre el horizonte al inicio, mitad o final).
- irradiancia_extraterrestre_horaria: GHI fuera de la atmósfera promediada en (H-1, H].
- desfase_nasa_h: cuántas horas sumar a la hora LST de NASA POWER para llevarla a la
  convención de Open-Meteo (UTC, etiqueta al final de la hora).
"""

import math

import numpy as np
import pandas as pd

CONSTANTE_SOLAR = 1361.0  # W/m²


def _anio_fraccional(marcas):
    hora = marcas.hour.to_numpy() + marcas.minute.to_numpy() / 60
    dia = marcas.dayofyear.to_numpy()
    return hora, dia, 2 * np.pi / 365 * (dia - 1 + (hora - 12) / 24)


def coseno_cenit(marcas_utc, lat, lon):
    # Coseno del ángulo cenital solar (fórmula NOAA), sin recortar a 0.
    marcas = pd.DatetimeIndex(marcas_utc)
    hora, _, g = _anio_fraccional(marcas)
    ecuacion_tiempo = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                                - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    declinacion = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g)
                   - 0.006758 * np.cos(2 * g) + 0.000907 * np.sin(2 * g)
                   - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    minutos_solares = hora * 60 + ecuacion_tiempo + 4 * lon
    angulo_horario = np.radians(minutos_solares / 4 - 180)
    latitud = np.radians(lat)
    coseno = (np.sin(latitud) * np.sin(declinacion)
              + np.cos(latitud) * np.cos(declinacion) * np.cos(angulo_horario))
    return np.clip(coseno, -1, 1)


def elevacion_solar(marcas_utc, lat, lon):
    # Ángulo del sol sobre el horizonte, en grados.
    return 90 - np.degrees(np.arccos(coseno_cenit(marcas_utc, lat, lon)))


def marcar_horas_diurnas(horas_utc, lat, lon):
    # Una hora (H-1, H] es diurna si el sol está sobre el horizonte al inicio, a la mitad o al final.
    horas = pd.DatetimeIndex(horas_utc)
    al_inicio = elevacion_solar(horas - pd.Timedelta(minutes=60), lat, lon)
    a_la_mitad = elevacion_solar(horas - pd.Timedelta(minutes=30), lat, lon)
    al_final = elevacion_solar(horas, lat, lon)
    return (al_inicio > 0) | (a_la_mitad > 0) | (al_final > 0)


def irradiancia_extraterrestre_horaria(horas_utc, lat, lon, muestras=12):
    # GHI extraterrestre promedio de (H-1, H] en W/m², con 12 muestras de 5 min por hora.
    horas = pd.DatetimeIndex(horas_utc)
    total = np.zeros(len(horas))
    for k in range(muestras):
        instante = horas - pd.Timedelta(minutes=60 * (k + 0.5) / muestras)
        dia = instante.dayofyear.to_numpy()
        excentricidad = 1 + 0.033 * np.cos(2 * np.pi * dia / 365)
        total += CONSTANTE_SOLAR * excentricidad * np.clip(coseno_cenit(instante, lat, lon), 0, None)
    return total / muestras


def offset_lst_h(lon):
    # Desfase de la hora solar local (LST) de NASA POWER respecto a UTC: round(lon / 15).
    # Se redondea "hacia arriba en .5" (no redondeo bancario) para que sea determinista.
    return int(math.floor(lon / 15 + 0.5))


def desfase_nasa_h(lon):
    # Horas que se suman a la etiqueta LST de NASA para pasarla a UTC con etiqueta al final:
    #   UTC = LST - offset, y +1 h porque NASA etiqueta la hora por su inicio y Open-Meteo por su final.
    # Rionegro (lon -75,38): offset -5 -> +6 h, el mismo valor fijo que usaba la AE4.
    return 1 - offset_lst_h(lon)


def hora_local_aprox(marcas_utc, lon):
    # Hora "local" aproximada por longitud (UTC + round(lon/15)); sirve para el día típico.
    return (pd.DatetimeIndex(marcas_utc) + pd.Timedelta(hours=offset_lst_h(lon))).hour
