"""Configuración (equivale a CONTAW.ini del original).

Archivo contawin.ini junto al programa:

    [main]
    titulo = Sistema de Contabilidad
    tema   = claro                  ; claro, oscuro o automatico (según Windows)

    [datos]
    base = datos\\contawin.db        ; ruta relativa a la carpeta del programa o absoluta
    dbf  =                          ; última carpeta ContaWin importada (se recuerda sola)
"""
from __future__ import annotations

import configparser
import os
import sys

from . import APP_NAME


def carpeta_programa() -> str:
    if getattr(sys, "frozen", False):          # ejecutable generado con PyInstaller
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


RUTA_INI = os.path.join(carpeta_programa(), "contawin.ini")


class Config:
    def __init__(self, ruta: str = RUTA_INI):
        self.ruta = ruta
        self.cp = configparser.ConfigParser()
        if os.path.exists(ruta):
            self.cp.read(ruta, encoding="utf-8")
        for sec in ("main", "datos"):
            if not self.cp.has_section(sec):
                self.cp.add_section(sec)
        if not os.path.exists(ruta):
            self.cp.set("main", "titulo", APP_NAME)
            self.cp.set("datos", "base", os.path.join("datos", "contawin.db"))
            self.cp.set("datos", "dbf", "")
            self.guardar()

    def guardar(self):
        try:
            with open(self.ruta, "w", encoding="utf-8") as f:
                self.cp.write(f)
        except OSError:
            pass

    @property
    def titulo(self) -> str:
        return self.cp.get("main", "titulo", fallback=APP_NAME) or APP_NAME

    @property
    def tema(self) -> str:
        return self.cp.get("main", "tema", fallback="claro") or "claro"

    @tema.setter
    def tema(self, valor: str):
        self.cp.set("main", "tema", valor or "claro")
        self.guardar()

    @property
    def ruta_base(self) -> str:
        r = self.cp.get("datos", "base", fallback="") or os.path.join("datos", "contawin.db")
        if not os.path.isabs(r):
            r = os.path.join(carpeta_programa(), r)
        return r

    @property
    def carpeta_dbf(self) -> str:
        return self.cp.get("datos", "dbf", fallback="")

    @carpeta_dbf.setter
    def carpeta_dbf(self, valor: str):
        self.cp.set("datos", "dbf", valor or "")
        self.guardar()
