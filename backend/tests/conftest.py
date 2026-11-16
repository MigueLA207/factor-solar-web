import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore", message=".*doesn't match a supported version.*")

import pytest  # noqa: E402

from nucleo import extraccion, reglas  # noqa: E402

R = reglas.REFERENCIA


@pytest.fixture(scope="session")
def crudos_ae4():
    # Respuestas crudas de ERA5 y NASA que usó la AE4 (Rionegro 2024), copiadas sin tocar.
    return {"era5": (R / "ae4_openmeteo_era5_2024_CRUDO.csv").read_text(encoding="utf-8"),
            "nasa": (R / "ae4_nasapower_2024_CRUDO.json").read_text(encoding="utf-8")}


@pytest.fixture(scope="session")
def era5_ae4(crudos_ae4):
    return extraccion.leer_openmeteo(crudos_ae4["era5"])


def crudos_cache(lat, lon, anio):
    # Respuestas REALES ya guardadas en datos/cache (no se versionan: si faltan, la prueba se salta).
    era5 = extraccion.ruta_cache("openmeteo_era5", lat, lon, anio, "csv")
    nasa = extraccion.ruta_cache("nasapower", lat, lon, anio, "json")
    if not (era5.exists() and nasa.exists()):
        pytest.skip(f"falta la caché real de ({lat}, {lon}, {anio})")
    return {"era5": era5.read_text(encoding="utf-8"), "nasa": nasa.read_text(encoding="utf-8")}


def sensor_horario_desde_era5(crudos, anio, factor=0.9, **cambios):
    # Sensor por hora "subido por el usuario" = ERA5 × factor (conocido), para probar el pipeline de punta a punta.
    import pandas as pd

    from nucleo import pipeline
    era5 = extraccion.leer_openmeteo(crudos["era5"])
    crudo = pd.DataFrame({"ts_utc": era5["ts_utc"], "irr_sitio": (era5["irr_era5"] * factor).round(2),
                          "t_modulo": float("nan")})
    for clave, valor in cambios.items():
        crudo = valor(crudo) if clave == "tabla" else crudo
    return pipeline.Sensor(crudo=crudo, frecuencia="hora", simulado=False, tiene_temperatura=False)
