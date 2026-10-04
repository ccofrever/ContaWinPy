"""Controles y utilidades comunes de la interfaz."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from PySide6.QtCore import QDate, QRegularExpression, Qt
from PySide6.QtGui import QColor, QRegularExpressionValidator
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QCompleter, QDateEdit, QHeaderView, QLineEdit,
                               QMessageBox, QStyle, QTableWidget, QTableWidgetItem, QWidget)

from .. import util
from ..db import Database

# Colores tomados del original (CLR_TSNBLUE, CLR_AZUL, fondo RGB(0,100,100))
COLOR_FONDO = QColor(0, 100, 100)
COLOR_SELECCION = QColor(128, 128, 192)
COLOR_ALTERNO = QColor(230, 236, 246)
ESTILO = """
QDialog, QMainWindow { background: #f3f5f8; }
QTableWidget { gridline-color: #c9d2e0; alternate-background-color: #e6ecf6; background: white;
               selection-background-color: #8080c0; selection-color: white; }
QHeaderView::section { background: #d7deea; padding: 4px; border: 0; border-right: 1px solid #b9c3d3;
                       font-weight: bold; }
QPushButton { padding: 5px 12px; }
QLineEdit[readOnly="true"] { background: #eef0f3; color: #333; }
QLabel#totalOk { color: #1b6e20; font-weight: bold; }
QLabel#totalMal { color: #b00020; font-weight: bold; }
"""


@dataclass
class Sesion:
    """Estado de trabajo: reemplaza las variables PRIVATE/PUBLIC del original
    (Rut_Usar, La_Empresa, cp_NomEmp, Dir_Works, cp_Ano, ElUsuario...)."""
    db: Database
    usuario: dict | None = None
    empresa: dict | None = None
    periodo: dict | None = None

    @property
    def empresa_id(self) -> int | None:
        return self.empresa["id"] if self.empresa else None

    @property
    def periodo_id(self) -> int | None:
        return self.periodo["id"] if self.periodo else None

    @property
    def ano(self) -> int | None:
        return self.periodo["ano"] if self.periodo else None

    @property
    def es_admin(self) -> bool:
        return bool(self.usuario and self.usuario.get("es_admin"))

    def refrescar_empresa(self):
        if self.empresa:
            e = self.db.empresa(self.empresa["id"])
            self.empresa = dict(e) if e else None
            if not e:
                self.periodo = None


# ---------------------------------------------------------------------------
# Mensajes (Alert / MsgYesNo / MsgStop)
# ---------------------------------------------------------------------------
def info(parent, texto: str, titulo: str = "Atención"):
    QMessageBox.information(parent, titulo, texto)


def error(parent, texto: str, titulo: str = "Error"):
    QMessageBox.warning(parent, titulo, texto)


def confirmar(parent, texto: str, titulo: str = "Pregunta") -> bool:
    r = QMessageBox.question(parent, titulo, texto,
                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                             QMessageBox.StandardButton.No)
    return r == QMessageBox.StandardButton.Yes


def icono(widget: QWidget, nombre: str):
    return widget.style().standardIcon(getattr(QStyle.StandardPixmap, nombre))


# ---------------------------------------------------------------------------
# Campos de entrada
# ---------------------------------------------------------------------------
class MontoEdit(QLineEdit):
    """Ingreso de montos enteros con separador de miles (PICTURE "@RE 999,999,999,999")."""

    def __init__(self, parent=None, valor: int = 0):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setValidator(QRegularExpressionValidator(QRegularExpression(r"-?[0-9.]{0,17}"), self))
        self.setMaxLength(18)
        self.set_valor(valor)
        self.editingFinished.connect(self._formatear)

    def _formatear(self):
        self.set_valor(self.valor())

    def valor(self) -> int:
        return util.parse_monto(self.text())

    def set_valor(self, v):
        self.setText(util.fmt_monto(v))


class RutEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setValidator(QRegularExpressionValidator(QRegularExpression(r"[0-9kK.\- ]{0,13}"), self))
        self.setPlaceholderText("12.345.678-9")
        self.editingFinished.connect(lambda: self.setText(util.formato_rut(self.text())) if self.text() else None)

    def rut(self) -> str:
        return util.limpiar_rut(self.text())


class CodigoCuentaEdit(QLineEdit):
    """PICTURE "@R 99.99.99" """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setInputMask("99.99.99;_")

    def codigo(self) -> str:
        return util.limpiar_codigo(self.text())

    def set_codigo(self, c: str):
        self.setText(util.formato_codigo(c))


class FechaEdit(QDateEdit):
    """Fecha dd/mm/aaaa con calendario desplegable (reemplaza CALENDARIO())."""

    def __init__(self, parent=None, fecha=None):
        super().__init__(parent)
        self.setDisplayFormat("dd/MM/yyyy")
        self.setCalendarPopup(True)
        self.set_fecha(fecha or _dt.date.today())

    def fecha(self) -> _dt.date:
        q = self.date()
        return _dt.date(q.year(), q.month(), q.day())

    def set_fecha(self, f):
        f = util.from_iso(f) if not isinstance(f, _dt.date) else f
        f = f or _dt.date.today()
        self.setDate(QDate(f.year, f.month, f.day))


class Buscador(QComboBox):
    """Combo con búsqueda por texto (reemplaza Brw_Cuenta / Brw_CCosto / BrowseExiste)."""

    def __init__(self, parent=None, permitir_vacio: bool = False, texto_vacio: str = ""):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(20)
        comp = self.completer()
        comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.permitir_vacio = permitir_vacio
        self.texto_vacio = texto_vacio
        self.setMinimumWidth(320)

    def set_items(self, items: list[tuple[str, str]], formato=lambda c: c):
        actual = self.codigo()
        self.blockSignals(True)
        self.clear()
        if self.permitir_vacio:
            self.addItem(self.texto_vacio, "")
        for cod, nombre in items:
            self.addItem(f"{formato(cod)}   {nombre}", cod)
        self.blockSignals(False)
        if actual:
            self.set_codigo(actual)
        elif self.permitir_vacio:
            self.setCurrentIndex(0)
        else:
            self.setCurrentIndex(-1)
            self.setEditText("")

    def codigo(self) -> str | None:
        texto = self.currentText().strip()
        if not texto:
            return "" if self.permitir_vacio else None
        i = self.findText(self.currentText(), Qt.MatchFlag.MatchExactly)
        if i >= 0:
            return self.itemData(i)
        # se escribió solo el código (con o sin puntos/guión)
        primero = texto.split()[0]
        for i in range(self.count()):
            d = self.itemData(i) or ""
            if d and (d.upper() == primero.upper() or util.limpiar_codigo(d) == util.limpiar_codigo(primero)
                      or util.limpiar_rut(d) == util.limpiar_rut(primero)):
                return d
        return None

    def set_codigo(self, cod: str | None):
        i = self.findData(cod or "")
        if i >= 0:
            self.setCurrentIndex(i)
        elif self.permitir_vacio:
            self.setCurrentIndex(0)
        else:
            self.setCurrentIndex(-1)
            self.setEditText("")


# ---------------------------------------------------------------------------
# Tabla
# ---------------------------------------------------------------------------
class Tabla(QTableWidget):
    """Grilla de solo lectura, una fila seleccionada (reemplaza TSBrowse)."""

    def __init__(self, columnas: list[tuple[str, int, str]], parent=None):
        """columnas: (titulo, ancho px, alineación 'L'|'R'|'C'); ancho 0 = estira."""
        super().__init__(0, len(columnas), parent)
        self.columnas = columnas
        self.setHorizontalHeaderLabels([c[0] for c in columnas])
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(24)
        h = self.horizontalHeader()
        for i, (_, ancho, _) in enumerate(columnas):
            if ancho:
                self.setColumnWidth(i, ancho)
            else:
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        h.setHighlightSections(False)

    def cargar(self, filas: list[list], datos: list | None = None, estilos: list[str] | None = None):
        self.setRowCount(0)
        self.setRowCount(len(filas))
        for r, fila in enumerate(filas):
            for c, v in enumerate(fila):
                it = QTableWidgetItem("" if v is None else str(v))
                al = self.columnas[c][2]
                if al == "R":
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                elif al == "C":
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if estilos and estilos[r]:
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                    if estilos[r] == "grupo":
                        it.setBackground(QColor(215, 222, 234))
                if c == 0 and datos is not None:
                    it.setData(Qt.ItemDataRole.UserRole, datos[r])
                self.setItem(r, c, it)

    def dato_actual(self):
        r = self.currentRow()
        if r < 0:
            return None
        it = self.item(r, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def seleccionar_dato(self, dato):
        for r in range(self.rowCount()):
            it = self.item(r, 0)
            if it and it.data(Qt.ItemDataRole.UserRole) == dato:
                self.selectRow(r)
                self.scrollToItem(it)
                return True
        return False

    def filtrar(self, texto: str):
        t = texto.strip().lower()
        for r in range(self.rowCount()):
            visible = not t or any(t in (self.item(r, c).text().lower() if self.item(r, c) else "")
                                   for c in range(self.columnCount()))
            self.setRowHidden(r, not visible)
