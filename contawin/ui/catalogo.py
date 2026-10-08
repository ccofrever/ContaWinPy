"""Ventana genérica de mantención (diálogo "BROWSE" del original):
grilla + orden + búsqueda + Nuevo / Modificar / Borrar / Excel / Imprimir / Salir."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from ..db import ErrorDatos
from . import impresion, tema
from .comunes import Tabla, confirmar, error


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
                 tamano: tuple[int, int] = (820, 560), al_final: bool = False):
        """cargar(orden) -> [(clave, [valores visibles])]
        extras: botones adicionales (texto, icono, función(clave_seleccionada))
        al_final: al abrir, marca el último registro (p. ej. el último comprobante ingresado)"""
        super().__init__(parent)
        self.al_final = al_final
        self.setWindowTitle(titulo)
        self.resize(*tamano)
        self._cargar, self._nuevo, self._modificar = cargar, nuevo, modificar
        self._borrar, self._describir, self._informe = borrar, describir, informe
        self.ordenes = ordenes

        lay = tema.margenes(QVBoxLayout(self))
        partes = titulo.split(" - ", 1)
        lay.addWidget(tema.etiqueta(partes[0], "titulo"))
        if len(partes) > 1:
            lay.addWidget(tema.etiqueta(partes[1], "secundario"))
        arriba = QHBoxLayout()
        arriba.setSpacing(tema.ESPACIO[2])
        self.ed_buscar = QLineEdit()
        self.ed_buscar.setPlaceholderText("Buscar (escribe para filtrar)")
        self.ed_buscar.setClearButtonEnabled(True)
        self.ed_buscar.addAction(tema.icono("buscar"), QLineEdit.ActionPosition.LeadingPosition)
        self.ed_buscar.textChanged.connect(lambda t: self.tabla.filtrar(t))
        arriba.addWidget(self.ed_buscar, 1)
        arriba.addSpacing(tema.ESPACIO[4])
        arriba.addWidget(tema.etiqueta("Ordenar por", "etiqueta"))
        self.cb_orden = QComboBox()
        for etiqueta, _ in ordenes:
            self.cb_orden.addItem(etiqueta)
        self.cb_orden.currentIndexChanged.connect(lambda _: self.refrescar())
        self.cb_orden.setMinimumWidth(160)
        arriba.addWidget(self.cb_orden)
        lay.addLayout(arriba)

        self.tabla = Tabla(columnas, self)
        self.tabla.doubleClicked.connect(lambda _: self.accion_modificar())
        lay.addWidget(self.tabla, 1)

        bot = QHBoxLayout()
        bot.setSpacing(tema.ESPACIO[2])
        botones = []
        if nuevo:
            botones.append(("&Nuevo", "mas", self.accion_nuevo, "Insert"))
        if modificar:
            botones.append(("&Modificar", "editar", self.accion_modificar, "Enter o doble clic"))
        if borrar:
            botones.append(("&Borrar", "borrar", self.accion_borrar, "Supr"))
        if informe:
            botones.append(("&Excel", "excel", self.accion_excel, "Exportar el listado a Excel"))
            botones.append(("&Imprimir", "imprimir", self.accion_imprimir, "Vista previa e impresión"))
        for texto, ic, fn in extras or []:
            botones.append((texto, ic, lambda _=False, fn=fn: self._extra(fn), ""))
        for i, (texto, ic, acc, ayuda) in enumerate(botones):
            b = tema.boton(texto, ic, "primario" if (i == 0 and nuevo) else "secundario")
            b.setAutoDefault(False)
            if ayuda:
                b.setToolTip(ayuda)
            b.clicked.connect(acc)
            bot.addWidget(b)
        bot.addStretch()
        salir = tema.boton("&Cerrar", "cerrar")
        salir.setAutoDefault(False)
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
                fila = self.tabla.rowCount() - 1 if self.al_final else 0
                self.tabla.selectRow(fila)
                self.tabla.scrollToItem(self.tabla.item(fila, 0))

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
        self.tabla.setFocus()

    def accion_modificar(self):
        clave = self.tabla.dato_actual()
        if clave is None or not self._modificar:
            return
        if self._modificar(clave) is not None:
            self.refrescar(clave)
        self.tabla.setFocus()

    def accion_borrar(self):
        clave = self.tabla.dato_actual()
        if clave is None or not self._borrar:
            return
        desc = self._describir(clave) if self._describir else str(clave)
        if not confirmar(self, f"¿Borrar este registro?\n\n{desc}", "Borrar registro"):
            return
        anterior = self._clave_vecina(-1)
        if anterior is None:
            anterior = self._clave_vecina(+1)      # era el primero: queda en el siguiente
        try:
            self._borrar(clave)
        except ErrorDatos as e:
            error(self, str(e))
            return
        self.refrescar(anterior)
        self.tabla.setFocus()

    def _clave_vecina(self, paso: int):
        """Clave de la fila visible anterior (paso=-1) o siguiente (+1) a la seleccionada."""
        r = self.tabla.currentRow() + paso
        while 0 <= r < self.tabla.rowCount():
            if not self.tabla.isRowHidden(r):
                it = self.tabla.item(r, 0)
                return it.data(Qt.ItemDataRole.UserRole) if it else None
            r += paso
        return None

    def accion_excel(self):
        inf = self._informe()
        if not inf.filas:
            error(self, "No hay datos para mostrar.", "Atención")
            return
        impresion.guardar_excel(self, inf)

    def accion_imprimir(self):
        inf = self._informe()
        if not inf.filas:
            error(self, "No hay datos para mostrar.", "Atención")
            return
        impresion.vista_previa(self, inf)
