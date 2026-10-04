"""Asiento de apertura: textos de apoyo.

La lógica está en db.py (saldos_cierre, lineas_apertura, traspasar_apertura,
crear_periodo_con_apertura): el asiento de apertura de un año es el resultado del
balance del año anterior. Las cuentas de balance (1 y 2) se traspasan con su saldo y el
resultado del ejercicio (cuentas 3 y 4) va a una cuenta de patrimonio elegida por el usuario.
"""
from __future__ import annotations

from . import util


def resumen_resultado(resultado: int) -> str:
    """resultado = debe - haber de las cuentas 3 y 4 (> 0 pérdida, < 0 utilidad)."""
    if resultado < 0:
        return f"Utilidad del ejercicio: {util.fmt_pesos(-resultado)} (va al Haber de la cuenta elegida)"
    if resultado > 0:
        return f"Pérdida del ejercicio: {util.fmt_pesos(resultado)} (va al Debe de la cuenta elegida)"
    return "El ejercicio no tiene resultado (cuentas 3 y 4 en cero)."
