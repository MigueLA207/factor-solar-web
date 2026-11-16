"""El CSV subido se rechaza si sus valores no pueden ser irradiancia en W/m² de un piranómetro."""
import pytest

from nucleo.sensor_csv import ErrorCSV, validar_csv


def horas_de_enero(valor_mediodia, columna_extra=""):
    filas = []
    for d in range(1, 29):
        for h in range(24):
            v = valor_mediodia if 11 <= h <= 22 else 0
            filas.append(f"2024-01-{d:02d} {h:02d}:00:00,{v}{columna_extra}")
    return filas


def csv(filas, encabezado="ts_utc,irr_sitio"):
    return (encabezado + "\n" + "\n".join(filas)).encode()


def test_rechaza_todo_en_cero():
    with pytest.raises(ErrorCSV, match="nunca pasa de"):
        validar_csv(csv(horas_de_enero(0)))


def test_rechaza_kw_por_m2():
    with pytest.raises(ErrorCSV, match="kW/m²"):
        validar_csv(csv(horas_de_enero(0.8)))


def test_rechaza_valores_imposibles():
    filas = [f"2024-01-{d:02d} {h:02d}:00:00,9999" for d in range(1, 29) for h in range(24)]
    with pytest.raises(ErrorCSV, match="físicamente posible"):
        validar_csv(csv(filas))


def test_rechaza_mayoria_no_numerica():
    filas = [f"2024-01-{d:02d} {h:02d}:00:00,{'abc' if h % 3 else 500}" for d in range(1, 29) for h in range(24)]
    with pytest.raises(ErrorCSV, match="son números"):
        validar_csv(csv(filas))


def test_acepta_irradiancia_razonable():
    tabla, reporte = validar_csv(csv(horas_de_enero(700)))
    assert reporte["valido"] and reporte["frecuencia"] == "hora"


def test_ignora_temperatura_imposible_sin_bloquear():
    tabla, reporte = validar_csv(csv(horas_de_enero(700, ",500"), "ts_utc,irr_sitio,t_modulo"))
    assert tabla["t_modulo"].isna().all()
    assert any("se ignora la temperatura" in a for a in reporte["advertencias"])
