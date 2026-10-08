"""Funciones utilitarias (equivalentes a FUNCIONS.PRG).

- RUT chileno: validación (ValRut), formato (Ver_Rut / lcVer_Rut)
- Códigos de cuenta: formato 99.99.99 (VerCodigos)
- Montos: formato con separador de miles "." (Transform + StrTran)
- Fechas: conversión entre date, ISO (SQLite) y dd/mm/aaaa (SET DATE FRENCH)
"""
from __future__ import annotations

import datetime as _dt
import re

# ---------------------------------------------------------------------------
# Tipos de documento de compra (aTDocumen / aTdocL en CONTAB.PRG)
# El índice guardado en COMPRAS.TDOCUM es 1..18
# ---------------------------------------------------------------------------
TIPOS_DOCUMENTO = [
    ("BOL", "Boleta"),
    ("BOLE", "Boleta Exenta"),
    ("BOLH", "Boleta Honorarios"),
    ("BHE", "Boleta Honorarios Exenta"),
    ("FAC", "Factura"),
    ("FACE", "Factura Exenta"),
    ("ODE", "Otro Documento Exento"),
    ("BOLEC", "Boleta Electrónica"),
    ("BOLEX", "Boleta Exenta Electrónica"),
    ("BOLHE", "Boleta Honorario Electrónica"),
    ("FACEL", "Factura Electrónica"),
    ("FACEX", "Factura Electrónica Exenta"),
    ("FIN", "Finiquito"),
    ("BPST", "Bol. Honorarios P. Servicios 3ros"),
    ("BPSTE", "B. Honorarios P.Serv. 3ros Electrónica"),
    ("NOTACRE", "Nota de Crédito"),
    ("PLANILLA", "Planilla Saneamiento Previsional"),
    ("NOTADEB", "Nota de Débito"),
]
# Documentos afectos a IVA (para el cálculo automático de neto / IVA)
DOCS_AFECTOS = {5, 11, 16, 18}   # Factura, Factura Electrónica, N. Crédito, N. Débito
TASA_IVA = 0.19

TIPOS_ASIENTO = {"I": "Ingreso", "E": "Egreso", "T": "Traspaso"}


def sigla_documento(n: int | None) -> str:
    if n and 1 <= n <= len(TIPOS_DOCUMENTO):
        return TIPOS_DOCUMENTO[n - 1][0]
    return ""


def nombre_documento(n: int | None) -> str:
    if n and 1 <= n <= len(TIPOS_DOCUMENTO):
        return TIPOS_DOCUMENTO[n - 1][1]
    return ""


def nombre_tipo_asiento(t: str | None) -> str:
    return TIPOS_ASIENTO.get((t or "").upper(), "")


# ---------------------------------------------------------------------------
# RUT
# ---------------------------------------------------------------------------
def limpiar_rut(rut: str | None) -> str:
    """Deja el RUT como en el DBF original: dígitos + dígito verificador, sin
    puntos ni guión, en mayúsculas (ej. '761272179', '96792430K')."""
    if not rut:
        return ""
    return re.sub(r"[^0-9Kk]", "", str(rut)).upper()


def digito_verificador(cuerpo: str) -> str:
    suma, factor = 0, 2
    for c in reversed(cuerpo):
        suma += int(c) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    return {11: "0", 10: "K"}.get(resto, str(resto))


def validar_rut(rut: str | None) -> bool:
    r = limpiar_rut(rut)
    if len(r) < 2:
        return False
    cuerpo, dv = r[:-1], r[-1]
    if not cuerpo.isdigit():
        return False
    return digito_verificador(cuerpo) == dv


def formato_rut(rut: str | None) -> str:
    """Ver_Rut: 761272179 -> 76.127.217-9"""
    r = limpiar_rut(rut)
    if len(r) < 2:
        return r
    cuerpo, dv = r[:-1], r[-1]
    try:
        cuerpo = f"{int(cuerpo):,}".replace(",", ".")
    except ValueError:
        pass
    return f"{cuerpo}-{dv}"


def formato_rut_simple(rut: str | None) -> str:
    """lcVer_Rut: 761272179 -> 76127217-9"""
    r = limpiar_rut(rut)
    if len(r) < 2:
        return r
    return f"{r[:-1]}-{r[-1]}"


# ---------------------------------------------------------------------------
# Códigos de cuenta
# ---------------------------------------------------------------------------
def formato_codigo(codigo: str | None) -> str:
    """VerCodigos: '100001' -> '10.00.01'"""
    c = (codigo or "").strip()
    if len(c) <= 2:
        return c
    return ".".join(c[i:i + 2] for i in range(0, len(c), 2))


def limpiar_codigo(codigo: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", codigo or "").upper()[:6]


# ---------------------------------------------------------------------------
# Montos
# ---------------------------------------------------------------------------
def fmt_monto(valor, vacio_si_cero: bool = False) -> str:
    """Transform(n, '999,999,999,999') con StrTran(',', '.')"""
    try:
        n = int(round(float(valor or 0)))
    except (TypeError, ValueError):
        n = 0
    if vacio_si_cero and n == 0:
        return ""
    s = f"{abs(n):,}".replace(",", ".")
    return f"-{s}" if n < 0 else s


def fmt_pesos(valor) -> str:
    """Monto con signo peso y separador de miles: «$ 1.250.300», «−$ 45.000» (sistema de diseño)."""
    try:
        n = int(round(float(valor or 0)))
    except (TypeError, ValueError):
        n = 0
    s = f"$ {abs(n):,}".replace(",", ".")
    return f"\u2212{s}" if n < 0 else s


def parse_monto(texto) -> int:
    if texto is None:
        return 0
    if isinstance(texto, (int, float)):
        return int(round(texto))
    t = str(texto).strip().replace(".", "").replace(" ", "").replace(",", ".")
    if not t or t in ("-", "+"):
        return 0
    try:
        return int(round(float(t)))
    except ValueError:
        return 0


def es_cuenta_resultado(codigo: str | None) -> bool:
    """Grupos 1 (activo) y 2 (pasivo y patrimonio) son cuentas de balance; cualquier otro grupo
    (3 y 4 del plan original, 5 «resultado» de otros planes, etc.) es cuenta de resultado: va a
    Pérdida/Ganancia en el balance y se cierra contra el resultado al abrir el año siguiente."""
    return (codigo or "")[:1] not in ("1", "2")


def orden_linea(linea: dict) -> tuple:
    """Orden de las líneas de un comprobante: primero las del Debe y luego las del Haber,
    cada grupo por código de cuenta."""
    return (0 if int(linea.get("debe") or 0) else 1, linea.get("codigo") or "")


def mascara_monto(texto: str) -> str:
    """Máscara numérica en vivo: deja sólo dígitos (y un «-» inicial) con punto de miles."""
    neg = texto.strip().startswith("-")
    digitos = "".join(ch for ch in texto if ch.isdigit())
    if not digitos:
        return "-" if neg else ""
    s = f"{int(digitos):,}".replace(",", ".")
    return f"-{s}" if neg else s


def redondear_pesos(v) -> int:
    """Redondeo a pesos, mitad hacia arriba (no el redondeo bancario de round())."""
    from decimal import ROUND_HALF_UP, Decimal
    return int(Decimal(str(v)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def fmt_decimal(v, decimales: int = 2) -> str:
    """1234.5 -> '1.234,50' (formato chileno)."""
    s = f"{abs(v):,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-{s}" if v < 0 else s


_RE_MILES = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?$")


def _numero(token: str) -> str:
    """Número escrito a la chilena -> número Python: '1.000.000' -> '1000000'; '1,19' -> '1.19';
    '1.19' (sin grupos de 3) se toma como decimal."""
    if _RE_MILES.match(token):
        token = token.replace(".", "")
    return token.replace(",", ".")


def evaluar_expresion(texto: str) -> float:
    """Evalúa una operación de la calculadora (+ - * / paréntesis y %) sin usar eval().
    Lanza ValueError con un mensaje para el usuario si la operación no es válida."""
    import ast
    import operator as op
    t = (texto or "").strip().replace("×", "*").replace("÷", "/").replace("−", "-").replace("x", "*")
    if not t:
        raise ValueError("Escribe una operación.")
    if not re.fullmatch(r"[0-9.,+\-*/()% ]+", t):
        raise ValueError("Sólo se permiten números y + − × ÷ ( ) %.")
    t = re.sub(r"[0-9][0-9.,]*", lambda m: _numero(m.group(0)), t)
    t = re.sub(r"%", "/100", t)
    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
           ast.USub: op.neg, ast.UAdd: op.pos}

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            return ops[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in ops:
            return ops[type(n.op)](ev(n.operand))
        raise ValueError("Operación incompleta.")
    try:
        return float(ev(ast.parse(t, mode="eval")))
    except ZeroDivisionError:
        raise ValueError("No se puede dividir por cero.") from None
    except (SyntaxError, TypeError):
        raise ValueError("Operación incompleta.") from None


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------
def to_iso(d) -> str | None:
    if d is None or d == "":
        return None
    if isinstance(d, _dt.datetime):
        d = d.date()
    if isinstance(d, _dt.date):
        return d.isoformat()
    s = str(d).strip()
    if not s:
        return None
    if re.fullmatch(r"\d{8}", s):  # DTOS / DBF
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{int(m[3]):04d}-{int(m[2]):02d}-{int(m[1]):02d}"
    return None


def from_iso(s) -> _dt.date | None:
    s = to_iso(s)
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(s)
    except ValueError:
        return None


def fmt_fecha(d) -> str:
    """DToC con SET DATE FRENCH / SET CENTURY ON -> dd/mm/aaaa"""
    f = from_iso(d) if not isinstance(d, _dt.date) else d
    return f.strftime("%d/%m/%Y") if f else ""


MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def fecha_texto(d) -> str:
    """Fec_Tex: 04 de Octubre de 2026"""
    f = from_iso(d) if not isinstance(d, _dt.date) else d
    if not f:
        return ""
    return f"{f.day:02d} de {MESES[f.month - 1]} de {f.year}"
