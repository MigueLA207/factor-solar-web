# Las frases para personas usan coma decimal y espacio fino de miles, como la interfaz.
from nucleo import formato
from nucleo.formato import ESPACIO_FINO as F


def test_decimales_con_coma():
    assert formato.dec(0.9467, 3) == "0,947"
    assert formato.dec(0.12) == "0,12"


def test_signo_y_porcentaje():
    assert formato.pct(7.7612, 2, signo=True) == "+7,76 %"
    assert formato.pct(-3.26, 1, signo=True) == "-3,3 %"


def test_miles_con_espacio_fino():
    assert formato.miles(4846) == f"4{F}846"
    assert formato.miles(527040) == f"527{F}040"
    assert formato.dec(1234.5, 1) == f"1{F}234,5"


def test_coordenadas_separadas_por_punto_y_coma():
    assert formato.coord(6.147148, -75.377316) == "6,1471; -75,3773"

