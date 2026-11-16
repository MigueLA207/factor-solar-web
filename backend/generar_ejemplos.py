"""
Genera los sensores SIMULADOS de ejemplo en datos/ejemplos/ (CSV por minuto comprimido + factor
verdadero por hora + metadatos JSON). Usa ERA5 en vivo una vez; después queda en datos/cache/.

    cd backend && python generar_ejemplos.py
"""

import json
import sys

from app import simular_y_guardar
from nucleo import reglas

ANIO = 2024
SEMILLA = 2026

EJEMPLOS = [
    {"slug": "rionegro", "nombre": "Rionegro (Antioquia, CO)", "lugar": "Rionegro, Antioquia, Colombia",
     "lat": 6.147148, "lon": -75.377316, "clima": "andino de montaña, régimen bimodal de lluvias",
     "descripcion": "Altiplano del Oriente antioqueño (2.100 m). Nubosidad frecuente; el mismo sitio de la AE4."},
    {"slug": "barranquilla", "nombre": "Barranquilla (Atlántico, CO)", "lugar": "Barranquilla, Atlántico, Colombia",
     "lat": 10.9639, "lon": -74.7964, "clima": "tropical seco del Caribe",
     "descripcion": "Costa Caribe, mucho sol en la temporada seca (dic–abr)."},
    {"slug": "bogota", "nombre": "Bogotá (CO)", "lugar": "Bogotá D.C., Colombia",
     "lat": 4.7110, "lon": -74.0721, "clima": "andino de altiplano, frío y nublado",
     "descripcion": "Sabana de Bogotá (2.600 m), cielos frecuentemente cubiertos."},
    {"slug": "madrid", "nombre": "Madrid (ES)", "lugar": "Madrid, España",
     "lat": 40.4168, "lon": -3.7038, "clima": "mediterráneo continental, estaciones marcadas",
     "descripcion": "Latitud media del hemisferio norte: días largos en verano y cortos en invierno."},
    {"slug": "santiago", "nombre": "Santiago (CL)", "lugar": "Santiago, Región Metropolitana, Chile",
     "lat": -33.4489, "lon": -70.6693, "clima": "mediterráneo del hemisferio sur",
     "descripcion": "Hemisferio sur: el verano (más sol) cae en diciembre–febrero."},
]


def generar(ejemplo):
    sensor_id = f"ejemplo-{ejemplo['slug']}"
    meta, sim = simular_y_guardar(ejemplo["lat"], ejemplo["lon"], ANIO, SEMILLA, None, ejemplo["nombre"],
                                  sensor_id=sensor_id)
    meta.update({k: ejemplo[k] for k in ("slug", "lugar", "clima", "descripcion")})
    reglas.EJEMPLOS.mkdir(parents=True, exist_ok=True)
    sim["crudo"].to_csv(reglas.EJEMPLOS / f"{ejemplo['slug']}.csv.gz", index=False,
                        date_format="%Y-%m-%d %H:%M:%S", compression="gzip")
    sim["verdadero"].to_csv(reglas.EJEMPLOS / f"{ejemplo['slug']}_verdadero.csv.gz", index=False,
                            date_format="%Y-%m-%d %H:%M:%S", compression="gzip")
    (reglas.EJEMPLOS / f"{ejemplo['slug']}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                                            encoding="utf-8")
    return meta


def main():
    elegidos = sys.argv[1:]
    for ejemplo in EJEMPLOS:
        if elegidos and ejemplo["slug"] not in elegidos:
            continue
        meta = generar(ejemplo)
        print(f"{ejemplo['slug']:<13} filas {meta['filas']:>7}  factor verdadero anual "
              f"{meta['factor_verdadero_anual']:.4f}  (SIMULADO)")


if __name__ == "__main__":
    main()
