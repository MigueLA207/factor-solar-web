"""Cifras en textos para personas: coma decimal y espacio fino de miles, igual que la interfaz.

Solo se usa en frases (detalles de las etapas, conclusiones, avisos, supuestos). Los valores numéricos
del JSON y las columnas de los CSV siguen con punto decimal para que las máquinas los lean.
"""

ESPACIO_FINO = " "  # separador de miles: no se confunde con la coma decimal


def dec(x, n=2, signo=False):
    """1234.5 -> '1 234,50'; con signo=True, 7.76 -> '+7,76'."""
    texto = f"{x:{'+' if signo else ''},.{n}f}"
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ESPACIO_FINO)


def miles(n):
    """Entero con espacio fino de miles: 4846 -> '4 846'."""
    return dec(int(n), 0)


def pct(x, n=1, signo=False):
    return f"{dec(x, n, signo)} %"


def coord(lat, lon):
    """Par de coordenadas legible; el punto y coma separa porque la coma ya es decimal."""
    return f"{dec(lat, 4)}; {dec(lon, 4)}"
