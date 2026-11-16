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
