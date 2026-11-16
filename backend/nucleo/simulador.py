"""
Simulador de un sensor en sitio para CUALQUIER punto: piranómetro horizontal (irr_sitio, W/m²) y
sensor de temperatura en la parte trasera del módulo (t_modulo, °C), un registro por minuto, en UTC.

EL SENSOR ES SIMULADO. Todo lo que sigue son SUPUESTOS DE SIMULACIÓN, no mediciones:

1. Base = ERA5 de ese punto interpolado a minutos conservando el promedio horario (igual que la AE4).
2. Factor verdadero por hora según la nubosidad local: índice de claridad
   kt = GHI_ERA5 / GHI_extraterrestre (geometría solar del punto) y
   factor = a - b·(1 - kt), recortado a [factor_min, factor_max]. Con a = 1,00 y b = 0,25 un cielo
   despejado (kt ≈ 0,75) da ≈ 0,94 y uno nublado (kt ≈ 0,35) ≈ 0,84: ERA5 sobrestima más con nubes.
3. Ruido de nubes multiplicativo de media 1 (normal suavizada a 7 min, σ = 0,12, recortada a ±3σ),
   con semilla fija: el mismo pedido produce el mismo sensor.
4. t_modulo = t_aire_ERA5 + k·G + ruido (k = 0,03 °C por W/m², ruido σ = 0,3 °C).
5. Defectos realistas inyectados con la semilla (cantidades conocidas): huecos, un corte largo, NaN,
   picos, negativos nocturnos pequeños, temperaturas imposibles y filas duplicadas.

El factor verdadero por hora se guarda para mostrar "factor recuperado vs verdadero".
"""

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from . import reglas, sol, transformacion

UN_MINUTO = pd.Timedelta(minutes=1)


@dataclass
class ParametrosSimulacion:
    a: float = 1.00                 # factor con cielo perfectamente despejado (kt = 1)
    b: float = 0.25                 # cuánto baja el factor por cada unidad de (1 - kt)
    factor_min: float = 0.70
    factor_max: float = 1.00
    ruido_sigma: float = 0.12
    ruido_ventana_min: int = 7
    k_calentamiento: float = 0.03   # °C por W/m² (tipo NOCT: ~25 °C sobre el aire a 800 W/m²)
    ruido_t_c: float = 0.3
    defectos: dict = field(default_factory=lambda: {
        "huecos_cortos": 40,           # huecos de 1 a 5 minutos
        "huecos_medios": 3,            # huecos de 10 a 40 minutos
        "corte_largo_min": 6 * 60,     # un corte de 6 horas
        "nan_irradiancia": 300,
        "nan_temperatura": 200,
        "picos_irradiancia": 25,       # 2000 a 3000 W/m²
        "negativos_nocturnos": 5000,   # -1 a -5 W/m²
        "temperatura_fuera_rango": 15,
        "timestamps_duplicados": 120,
    })

    @classmethod
    def desde(cls, datos):
        base = cls()
        if not datos:
            return base
        for clave, valor in datos.items():
            if clave == "defectos" and isinstance(valor, dict):
                base.defectos.update({k: int(v) for k, v in valor.items() if k in base.defectos})
            elif hasattr(base, clave) and clave != "defectos":
                setattr(base, clave, type(getattr(base, clave))(valor))
        return base


def supuestos(parametros, semilla):
    p = parametros
    return [
        "El sensor es SIMULADO: no es una medición. Sirve para validar el método, no para cotizar.",
        "Base del sensor = ERA5 de este mismo punto interpolado a minutos, conservando el promedio horario.",
        f"Factor verdadero por hora = {p.a:.2f} - {p.b:.2f}·(1 - kt), recortado a [{p.factor_min:.2f}, "
        f"{p.factor_max:.2f}]; kt = GHI_ERA5 / GHI extraterrestre (supuesto: ERA5 sobrestima más con nubes).",
        f"Ruido de nubes multiplicativo de media 1 (σ = {p.ruido_sigma}, suavizado a {p.ruido_ventana_min} min), "
        f"semilla {semilla}.",
        f"Temperatura del módulo = aire ERA5 + {p.k_calentamiento} °C por W/m² + ruido (σ = {p.ruido_t_c} °C).",
        "Defectos inyectados a propósito (huecos, NaN, picos, negativos nocturnos, duplicados) para que la "
        "etapa de calidad tenga trabajo; sus cantidades se conocen.",
    ]


# ---------------------------------------------------------------------------
# Señal limpia (copiado de ae4/pipeline/generar_sensor.py)
# ---------------------------------------------------------------------------

def interpolar_era5_a_minutos(era5, minutos):
    # ERA5 en la hora H es el promedio de (H-1, H]: el valor se ubica en H - 30 min y se interpola.
    posicion_minutos = (minutos - minutos[0]) / UN_MINUTO
    mitad_de_hora = era5["ts_utc"] - pd.Timedelta(minutes=30)
    posicion_era5 = (mitad_de_hora - minutos[0]) / UN_MINUTO
    return np.interp(posicion_minutos, posicion_era5, era5["irr_era5"].fillna(0))


def conservar_promedio_horario(irr_minuto, era5, minutos):
    # Reescala cada hora para que el promedio de sus minutos sea igual al valor ERA5.
    tabla = pd.DataFrame({"ts_utc": minutos, "irr": irr_minuto})
    tabla["hora"] = tabla["ts_utc"].dt.ceil("h")
    promedio_interpolado = tabla.groupby("hora")["irr"].transform("mean")
    valor_era5 = tabla["hora"].map(era5.set_index("ts_utc")["irr_era5"])
    escala = valor_era5 / promedio_interpolado
    escala = escala.where(promedio_interpolado > 0, 0).fillna(1)
    return (tabla["irr"] * escala).to_numpy()


def simular_ruido_nubes(generador, n, sigma, ventana):
    normal = generador.standard_normal(n + ventana - 1)
    suavizada = np.convolve(normal, np.ones(ventana) / ventana, mode="valid") * np.sqrt(ventana)
    return 1 + sigma * np.clip(suavizada, -3, 3)


def simular_temperatura_modulo(era5, minutos, irr, generador, p):
    posicion_minutos = (minutos - minutos[0]) / UN_MINUTO
    posicion_era5 = (era5["ts_utc"] - minutos[0]) / UN_MINUTO
    t_aire = np.interp(posicion_minutos, posicion_era5, era5["t_aire_era5"].interpolate().bfill().ffill())
    return t_aire + p.k_calentamiento * irr + generador.normal(0, p.ruido_t_c, len(minutos))


# ---------------------------------------------------------------------------
# Factor verdadero según la nubosidad (nuevo respecto a la AE4)
# ---------------------------------------------------------------------------

def factor_verdadero_horario(era5, lat, lon, p):
    # kt por hora; si el sol está muy bajo (G0 < 20 W/m²) se usa el kt del día para no dividir por ~0.
    horas = pd.DatetimeIndex(era5["ts_utc"])
    g0 = sol.irradiancia_extraterrestre_horaria(horas, lat, lon)
    ghi = era5["irr_era5"].fillna(0).to_numpy()
    tabla = pd.DataFrame({"ts_utc": horas, "g0": g0, "ghi": ghi})
    tabla["dia"] = (horas - pd.Timedelta(minutes=30)).normalize()
    por_dia = tabla.groupby("dia")[["ghi", "g0"]].transform("sum")
    kt_dia = np.where(por_dia["g0"] > 0, por_dia["ghi"] / por_dia["g0"].where(por_dia["g0"] > 0, 1), 0.5)
    kt = np.where(g0 >= 20, ghi / np.where(g0 > 0, g0, 1), kt_dia)
    kt = np.clip(kt, 0, 1)
    factor = np.clip(p.a - p.b * (1 - kt), p.factor_min, p.factor_max)
    return pd.DataFrame({"ts_utc": horas, "kt": np.round(kt, 4), "factor_verdadero": np.round(factor, 5)})


def simular_senal_limpia(era5, anio, lat, lon, generador, p):
    minutos = transformacion.calendario_minutos(anio)
    irr_cielo = conservar_promedio_horario(interpolar_era5_a_minutos(era5, minutos), era5, minutos)
    verdadero = factor_verdadero_horario(era5, lat, lon, p)
    hora_de_minuto = pd.Series(minutos).dt.ceil("h")
    factor = hora_de_minuto.map(verdadero.set_index("ts_utc")["factor_verdadero"])
    factor = factor.fillna(p.a - p.b * 0.5).to_numpy()   # 23:59 del 31-dic cae en la hora del año siguiente
    irr = irr_cielo * factor * simular_ruido_nubes(generador, len(minutos), p.ruido_sigma, p.ruido_ventana_min)
    irr = np.clip(irr, 0, None)
    t_modulo = simular_temperatura_modulo(era5, minutos, irr, generador, p)
    limpio = pd.DataFrame({"ts_utc": minutos, "irr_sitio": np.round(irr, 1), "t_modulo": np.round(t_modulo, 1)})
    return limpio, verdadero


# ---------------------------------------------------------------------------
# Defectos (copiado de la AE4, con las cantidades como parámetro)
# ---------------------------------------------------------------------------

def elegir_minutos_faltantes(generador, n, d):
    faltan = np.zeros(n, dtype=bool)
    inicio_corte = int(generador.integers(0, n - d["corte_largo_min"]))
    faltan[inicio_corte: inicio_corte + d["corte_largo_min"]] = True
    for cantidad, minimo, maximo in [(d["huecos_medios"], 10, 40), (d["huecos_cortos"], 1, 5)]:
        for _ in range(cantidad):
            inicio = int(generador.integers(0, n - maximo))
            largo = int(generador.integers(minimo, maximo + 1))
            faltan[inicio: inicio + largo] = True
    return faltan, inicio_corte


def elegir_filas_con_defectos(sensor, faltan, generador, d):
    presentes = np.flatnonzero(~faltan)
    nocturnas = presentes[sensor["irr_sitio"].to_numpy()[presentes] == 0]
    n_negativos = min(d["negativos_nocturnos"], len(nocturnas))
    filas = {"negativos_nocturnos": generador.choice(nocturnas, n_negativos, replace=False)}
    resto = np.setdiff1d(presentes, filas["negativos_nocturnos"])
    nombres = ["nan_irradiancia", "nan_temperatura", "picos_irradiancia",
               "temperatura_fuera_rango", "timestamps_duplicados"]
    cantidades = [d[nombre] for nombre in nombres]
    elegidas = generador.choice(resto, sum(cantidades), replace=False)
    for nombre, parte in zip(nombres, np.split(elegidas, np.cumsum(cantidades)[:-1])):
        filas[nombre] = parte
    return filas


def aplicar_defectos(sensor, faltan, filas, generador):
    con_defectos = sensor.copy()
    irr = con_defectos.columns.get_loc("irr_sitio")
    temp = con_defectos.columns.get_loc("t_modulo")
    negativos = filas["negativos_nocturnos"]
    con_defectos.iloc[negativos, irr] = np.round(generador.uniform(-5, -1, len(negativos)), 1)
    con_defectos.iloc[filas["nan_irradiancia"], irr] = np.nan
    con_defectos.iloc[filas["nan_temperatura"], temp] = np.nan
    picos = filas["picos_irradiancia"]
    con_defectos.iloc[picos, irr] = np.round(generador.uniform(2000, 3000, len(picos)), 1)
    malas = filas["temperatura_fuera_rango"]
    # Fuera del rango válido para cualquier sitio (-40 a 85 °C).
    frio = generador.uniform(-60, -45, len(malas))
    calor = generador.uniform(90, 127, len(malas))
    con_defectos.iloc[malas, temp] = np.round(np.where(generador.random(len(malas)) < 0.5, frio, calor), 1)
    copias = con_defectos.iloc[filas["timestamps_duplicados"]]
    con_defectos = pd.concat([con_defectos[~faltan], copias])
    return con_defectos.sort_values("ts_utc", kind="stable").reset_index(drop=True)


def tabla_de_defectos(faltan, filas, inicio_corte, minutos, d):
    corte = f"{minutos[inicio_corte]:%Y-%m-%d %H:%M}"
    return {
        "minutos_faltantes": int(faltan.sum()),
        "timestamps_duplicados": len(filas["timestamps_duplicados"]),
        "nan_irradiancia": len(filas["nan_irradiancia"]),
        "nan_temperatura": len(filas["nan_temperatura"]),
        "picos_irradiancia": len(filas["picos_irradiancia"]),
        "negativos_nocturnos": len(filas["negativos_nocturnos"]),
        "temperatura_fuera_rango": len(filas["temperatura_fuera_rango"]),
        "descripcion_huecos": (f"{d['huecos_cortos']} huecos de 1-5 min, {d['huecos_medios']} de 10-40 min "
                               f"y un corte de {d['corte_largo_min'] // 60} h desde {corte} UTC"),
    }


def factor_verdadero_anual(verdadero, era5, lat, lon):
    # Factor verdadero anual = promedio del factor horario ponderado por la energía ERA5 de las horas diurnas.
    tabla = verdadero.merge(era5[["ts_utc", "irr_era5"]], on="ts_utc")
    tabla = tabla[sol.marcar_horas_diurnas(tabla["ts_utc"], lat, lon) & tabla["irr_era5"].notna()]
    return float((tabla["factor_verdadero"] * tabla["irr_era5"]).sum() / tabla["irr_era5"].sum())


def simular_sensor(era5, anio, lat, lon, semilla=2026, parametros=None):
    """Simula un año del sensor en (lat, lon). Devuelve dict con crudo, verdadero, defectos y supuestos."""
    p = parametros if isinstance(parametros, ParametrosSimulacion) else ParametrosSimulacion.desde(parametros)
    generador = np.random.default_rng(semilla)
    limpio, verdadero = simular_senal_limpia(era5, anio, lat, lon, generador, p)
    faltan, inicio_corte = elegir_minutos_faltantes(generador, len(limpio), p.defectos)
    filas = elegir_filas_con_defectos(limpio, faltan, generador, p.defectos)
    crudo = aplicar_defectos(limpio, faltan, filas, generador)
    return {
        "crudo": crudo,
        "verdadero": verdadero,
        "defectos": tabla_de_defectos(faltan, filas, inicio_corte, limpio["ts_utc"], p.defectos),
        "parametros": asdict(p),
        "semilla": semilla,
        "supuestos": supuestos(p, semilla),
        "factor_verdadero_anual": round(factor_verdadero_anual(verdadero, era5, lat, lon), 4),
    }
