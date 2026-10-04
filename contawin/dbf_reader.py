"""Lector mínimo de archivos DBF (dBase III / FoxPro / Clipper DBFCDX).

No depende de librerías externas. ContaWin para Windows (FiveWin) graba
los textos en ANSI de Windows (cp1252); los datos de la versión DOS usan cp850. Solo lectura: se usa para importar los
datos del ContaWin original. Los índices .CDX se ignoran (no hacen falta).
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass


@dataclass
class Campo:
    nombre: str
    tipo: str
    largo: int
    decimales: int


class DBF:
    def __init__(self, ruta: str, encoding: str = "cp1252"):
        self.ruta = ruta
        self.encoding = encoding
        with open(ruta, "rb") as f:
            self._data = f.read()
        d = self._data
        if len(d) < 32:
            raise ValueError(f"Archivo DBF inválido: {ruta}")
        self.n_registros = struct.unpack("<I", d[4:8])[0]
        self.largo_header, self.largo_registro = struct.unpack("<HH", d[8:12])
        self.campos: list[Campo] = []
        pos = 32
        while pos + 32 <= len(d) and d[pos] != 0x0D:
            bloque = d[pos:pos + 32]
            nombre = bloque[:11].split(b"\0")[0].decode("ascii", "replace").strip().upper()
            self.campos.append(Campo(nombre, chr(bloque[11]), bloque[16], bloque[17]))
            pos += 32

    @property
    def nombres(self) -> list[str]:
        return [c.nombre for c in self.campos]

    def _convertir(self, campo: Campo, raw: bytes):
        t = campo.tipo
        if t in ("C", "V"):
            return raw.decode(self.encoding, "replace").rstrip(" \x00")
        if t in ("N", "F"):
            s = raw.decode("ascii", "replace").strip().replace(",", ".")
            if not s or "*" in s:
                return 0
            try:
                v = float(s)
            except ValueError:
                return 0
            return v if campo.decimales else int(round(v))
        if t == "D":
            s = raw.decode("ascii", "replace").strip()
            return s if (len(s) == 8 and s.isdigit() and s != "00000000") else ""
        if t == "L":
            return raw[:1] in (b"T", b"t", b"Y", b"y")
        if t == "I":
            return struct.unpack("<i", raw[:4])[0]
        return raw.decode(self.encoding, "replace").strip()

    def registros(self, incluir_borrados: bool = False):
        """Itera los registros como dict. Por defecto omite los marcados como
        borrados (equivale a SET DELETED ON del programa original)."""
        d = self._data
        for i in range(self.n_registros):
            ini = self.largo_header + i * self.largo_registro
            reg = d[ini:ini + self.largo_registro]
            if len(reg) < self.largo_registro:
                break
            borrado = reg[:1] == b"*"
            if borrado and not incluir_borrados:
                continue
            o = 1
            fila = {}
            for c in self.campos:
                fila[c.nombre] = self._convertir(c, reg[o:o + c.largo])
                o += c.largo
            if incluir_borrados:
                fila["_BORRADO"] = borrado
            yield fila

    def __iter__(self):
        return self.registros()


def buscar_archivo(carpeta: str, nombre: str) -> str | None:
    """Busca un archivo sin distinguir mayúsculas/minúsculas
    (en el original conviven COMPRAS.DBF, compras.dbf, DetAsien.dbf, ...)."""
    if not carpeta or not os.path.isdir(carpeta):
        return None
    objetivo = nombre.lower()
    for f in os.listdir(carpeta):
        if f.lower() == objetivo:
            return os.path.join(carpeta, f)
    return None


def buscar_carpeta(base: str, nombre: str) -> str | None:
    if not base or not os.path.isdir(base):
        return None
    objetivo = nombre.strip().lower()
    for f in os.listdir(base):
        p = os.path.join(base, f)
        if f.lower() == objetivo and os.path.isdir(p):
            return p
    return None


def leer(carpeta: str, nombre: str, encoding: str = "cp1252") -> list[dict]:
    ruta = buscar_archivo(carpeta, nombre)
    if not ruta:
        return []
    return list(DBF(ruta, encoding))
