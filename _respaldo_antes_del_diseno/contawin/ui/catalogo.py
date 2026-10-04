"""Ventana genérica de mantención (diálogo "BROWSE" del original):
grilla + orden + búsqueda + Nuevo / Modificar / Borrar / Excel / Imprimir / Salir."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout)

from ..db import ErrorDatos
from . import impresion
from .comunes import Tabla, confirmar, error, icono


class Catalogo(QDialog):
    def __init__(self, parent, titulo: str, columnas: list[tuple[str, int, str]],
                 cargar: Callable[[str], list[tuple[object, list]]],
                 ordenes: list[tuple[str, str]],
                 nuevo: Callable[[], object] | None = None,
                 modificar: Callable[[object], object] | None = None,
                 borrar: Callable[[object], None] | None = None,
                 describir: Callable[[object], str] | None = None,
                 informe: Callable[[], object] | None = None,
                 extras: list[tuple[str, str, Callable[[object], None]]] | None = None,
                 tamano: tuple[int, int] = (820, 560)):
        """cargar(orden) -> [(clave, [valores visibles])]
        extras: botones adicionales (texto, icono, función(clave_seleccionada))"""
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(*tamano)
        self._cargar, self._nuevo, self._modificar = cargar, nuevo, modificar
        self._borrar, self._describir, self._informe = borrar, describir, informe
        self.ordenes = ordenes

        lay = QVBoxLayout(self)
        arriba = QHBoxLayout()
        arriba.addWidget(QLabel("Orden:"))
        self.cb_orden = QComboBox()
        for etiqueta, _ in ordenes:
            self.cb_orden.addItem(etiqueta)
        self.cb_orden.currentIndexChanged.connect(lambda _: self.refrescar())
        arriba.addWidget(self.cb_orden)
        arriba.addSpacing(20)
        arriba.addWidget(QLabel("Buscar:"))
        self.ed_buscar = QLineEdit()
        self.ed_buscar.setPlaceholderText("Escriba para filtrar…")
        self.ed_buscar.setClearButtonEnabled(True)
        self.ed_buscar.textChanged.connect(lambda t: self.tabla.filtrar(t))
        arriba.addWidget(self.ed_buscar, 1)
        lay.addLayout(arriba)

        self.tabla = Tabla(columnas, self)
        self.tabla.doubleClicked.connect(lambda _: self.accion_modificar())
        lay.addWidget(self.tabla, 1)

        bot = QHBoxLayout()
        botones = []
        if nuevo:
            botones.append(("&Nuevo", "SP_FileIcon", self.accion_nuevo))
        if modificar:
            botones.append(("&Modificar", "SP_FileDialogDetailedView", self.accion_modificar))
        if borrar:
            botones.append(("&Borrar", "SP_TrashIcon", self.accion_borrar))
        if informe:
            botones.append(("&Excel", "SP_DialogSaveButton", self.accion_excel))
            botones.append(("&Imprimir", "SP_FileDialogContentsView", self.accion_imprimir))
        for texto, ic, fn in extras or []:
            botones.append((texto, ic, lambda _=False, fn=fn: self._extra(fn)))
        for texto, ic, acc in botones:
            b = QPushButton(icono(self, ic), texto)
            b.clicked.connect(acc)
            bot.addWidget(b)
        bot.addStretch()
        salir = QPushButton(icono(self, "SP_DialogCloseButton"), "&Salir")
        salir.clicked.connect(self.accept)
        bot.addWidget(salir)
        lay.addLayout(bot)

        for tecla, accion in [(Qt.Key.Key_Insert, self.accion_nuevo), (Qt.Key.Key_Delete, self.accion_borrar),
                              (Qt.Key.Key_Return, self.accion_modificar)]:
            atajo = QShortcut(QKeySequence(tecla), self.tabla)
            atajo.setContext(Qt.ShortcutContext.WidgetShortcut)
            atajo.activated.connect(accion)
        self.refrescar()

    def orden_actual(self) -> str:
        i = self.cb_orden.currentIndex()
        return self.ordenes[i][1] if 0 <= i < len(self.ordenes) else ""

    def refrescar(self, seleccionar=None):
        actual = seleccionar if seleccionar is not None else self.tabla.dato_actual()
        filas = self._cargar(self.orden_actual())
        self.tabla.cargar([f[1] for f in filas], [f[0] for f in filas])
        self.tabla.filtrar(self.ed_buscar.text())
        if actual is None or not self.tabla.seleccionar_dato(actual):
            if self.tabla.rowCount():
                self.tabla.selectRow(0)

    def _extra(self, fn):
        clave = self.tabla.dato_actual()
        if clave is not None:
            fn(clave)
            self.refrescar(clave)

    def accion_nuevo(self):
        if not self._nuevo:
            return
        clave = self._nuevo()
        if clave is not None:
            self.refrescar(clave)

    def accion_modificar(self):
        clave = self.tabla.dato_actual()
        if clave is None or not self._modificar:
            return
        if self._modificar(clave) is not None:
            self.refrescar(clave)

    def accion_borrar(self):
        clave = self.tabla.dato_actual()
        if clave is None or not self._borrar:
            return
        desc = self._describir(clave) if self._describir else str(clave)
        if not confirmar(self, f"¿Borrar el registro?\n\n{desc}", "BORRAR"):
            return
        try:
            self._borrar(clave)
        except ErrorDatos as e:
            error(self, str(e))
            return
        self.refrescar()

    def accion_excel(self):
        inf = self._informe()
        if not inf.filas:
            error(self, "No hay datos.", "ATENCIÓN")
            return
        impresion.guardar_excel(self, inf)

    def accion_imprimir(self):
        inf = self._informe()
        if not inf.filas:
            error(self, "No hay datos.", "ATENCIÓN")
            return
        impresion.vista_previa(self, inf)
