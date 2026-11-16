"""
Constantes del núcleo. Copia adaptada de ae4/pipeline/config.py: aquí NO hay
coordenadas ni año fijos; el sitio llega como parámetro (lat, lon, anio).
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas (todo vive bajo factor-solar-web/datos/)
# ---------------------------------------------------------------------------
BACKEND = Path(__file__).resolve().parents[1]
RAIZ = BACKEND.parent
DATOS = RAIZ / "datos"
CACHE = DATOS / "cache"            # respuestas crudas de las API, tal como llegan
EJEMPLOS = DATOS / "ejemplos"      # sensores simulados listos para probar
SENSORES = DATOS / "sensores"      # sensores simulados o subidos en esta instalación
ANALISIS = DATOS / "analisis"      # tablas de cada análisis (para el ZIP)
REFERENCIA = DATOS / "referencia"  # copia de los datos crudos de la AE4 (prueba cruzada)

# ---------------------------------------------------------------------------
# Años admitidos
# ---------------------------------------------------------------------------
ANIO_MIN = 2015
ANIO_MAX = 2025
ANIO_POR_DEFECTO = 2025            # el año completo más reciente con ERA5 y NASA publicados

# ---------------------------------------------------------------------------
# APIs
# ---------------------------------------------------------------------------
URL_OPENMETEO = "https://archive-api.open-meteo.com/v1/archive"
# Hay que pedir ERA5 de forma explícita; sin "models" la API devuelve "Best Match",
# que mezcla modelos y no se puede repetir.
MODELO_OPENMETEO = "era5"
URL_NASA = "https://power.larc.nasa.gov/api/temporal/hourly/point"
URL_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
NASA_VALOR_FALTANTE = -999.0

REINTENTOS = 3
ESPERA_BASE_S = 2                  # backoff: 2 s y 4 s entre los 3 intentos
TIMEOUT_S = 240

# ---------------------------------------------------------------------------
# Reglas de calidad (mismas de la AE4; T_MIN se amplía porque el sitio es cualquiera)
# ---------------------------------------------------------------------------
IRR_MIN = 0.0
IRR_MAX = 1500.0                   # sobre 1500 W/m² en superficie es físicamente imposible
IRR_NEGATIVO_TOLERADO = -10.0      # offset térmico nocturno del piranómetro
# AE4 usaba -10 °C (Rionegro, 2.100 m). Para cualquier sitio del mundo se baja a -40 °C;
# 85 °C sigue siendo el límite típico de operación de un módulo.
T_MIN = -40.0
T_MAX = 85.0
HUECO_MAX_INTERPOLABLE_MIN = 5
MIN_FRACCION_MINUTOS_HORA = 0.80   # una hora vale si tiene al menos 48 de 60 minutos
ELEVACION_NOCHE_PROFUNDA = -15.0
PCT_ALERTA_FILAS_ELIMINADAS = 10.0
DESFASE_MAX_H = 8

# ---------------------------------------------------------------------------
# Régimen bimodal andino (opcional, solo si el usuario lo pide)
# ---------------------------------------------------------------------------
FASES_BIMODAL_POR_MES = {
    12: "seca_1", 1: "seca_1", 2: "seca_1",
    3: "lluvias_1", 4: "lluvias_1", 5: "lluvias_1",
    6: "seca_2", 7: "seca_2", 8: "seca_2", 9: "seca_2",
    10: "lluvias_2", 11: "lluvias_2",
}
ORDEN_FASES_BIMODAL = ["seca_1", "lluvias_1", "seca_2", "lluvias_2"]
ETIQUETAS_FASES_BIMODAL = {
    "seca_1": "Seca 1 (dic–feb)",
    "lluvias_1": "Lluvias 1 (mar–may)",
    "seca_2": "Seca 2 (jun–sep)",
    "lluvias_2": "Lluvias 2 (oct–nov)",
}

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def validar_sitio(lat, lon, anio):
    # Devuelve un mensaje en español si el sitio o el año no son válidos; None si todo bien.
    if not (-90 <= lat <= 90):
        return "La latitud debe estar entre -90 y 90 grados."
    if not (-180 <= lon <= 180):
        return "La longitud debe estar entre -180 y 180 grados."
    if not (ANIO_MIN <= anio <= ANIO_MAX):
        return f"El año debe estar entre {ANIO_MIN} y {ANIO_MAX} (años completos con ERA5 y NASA)."
    return None
