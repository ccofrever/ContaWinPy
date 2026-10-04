"""Inicio de sesión (ChkPass / diálogo INICIAL) y selección de empresa y año
(Sel_Empresa / DLG_SelEmpresa, SLaEmpresa / DLG_SELANOS)."""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QPushButton, QVBoxLayout)

from .. import util
from ..db import ErrorDatos
from .comunes import Sesion, Tabla, error, icono


class LoginDialog(QDialog):
    def __init__(self, sesion: Sesion, titulo: str):
        super().__init__()
        self.s = sesion
        self.intentos = 0
        self.setWindowTitle("SELECCIÓN DE USUARIO")
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{titulo}</h3>"))
        form = QFormLayout()
        self.usuario = QLineEdit()
        self.usuario.setMaxLength(10)
        self.nombre = QLabel("")
        self.clave = QLineEdit()
        self.clave.setEchoMode(QLineEdit.EchoMode.Password)
        self.usuario.editingFinished.connect(self._mostrar_nombre)
        form.addRow("Usuario", self.usuario)
        form.addRow("", self.nombre)
        form.addRow("Clave", self.clave)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Ingresar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Salir")
        bb.accepted.connect(self._aceptar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _mostrar_nombre(self):
        u = self.s.db.usuario(self.usuario.text())
        self.nombre.setText(u["nombre"] if u else "")

    def _aceptar(self):
        u = self.s.db.login(self.usuario.text(), self.clave.text())
        if not u:
            self.intentos += 1
            error(self, "Error en Clave\n\nAcceso No Autorizado")
            self.clave.clear()
            self.clave.setFocus()
            if self.intentos >= 3:
                self.reject()
            return
        self.s.usuario = dict(u)
        self.accept()


class SeleccionEmpresaDialog(QDialog):
    """Selecciona empresa y luego año de trabajo."""

    def __init__(self, parent, sesion: Sesion):
        super().__init__(parent)
        self.s = sesion
        self.setWindowTitle("Selecciona Empresa a Trabajar")
        self.resize(760, 480)
        lay = QVBoxLayout(self)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Buscar:"))
        self.buscar = QLineEdit()
        self.buscar.setClearButtonEnabled(True)
        fila.addWidget(self.buscar, 1)
        lay.addLayout(fila)
        self.tabla = Tabla([("R.U.T.", 110, "R"), ("RAZÓN SOCIAL", 0, "L"), ("GIRO", 200, "L")], self)
        empresas = sesion.db.empresas()
        self.tabla.cargar([[util.formato_rut(e["rut"]), e["razon_social"], e["giro"]] for e in empresas],
                          [e["id"] for e in empresas])
        self.buscar.textChanged.connect(self.tabla.filtrar)
        self.tabla.doubleClicked.connect(lambda _: self._aceptar())
        if sesion.empresa_id and not self.tabla.seleccionar_dato(sesion.empresa_id):
            self.tabla.selectRow(0)
        elif not sesion.empresa_id and empresas:
            self.tabla.selectRow(0)
        lay.addWidget(self.tabla, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Seleccionar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancela")
        bb.accepted.connect(self._aceptar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.empresa_id = None
        self.periodo_id = None

    def _aceptar(self):
        eid = self.tabla.dato_actual()
        if eid is None:
            return
        dlg = SeleccionAnoDialog(self, self.s, eid)
        if dlg.exec() and dlg.periodo_id:
            self.empresa_id, self.periodo_id = eid, dlg.periodo_id
            self.accept()


class SeleccionAnoDialog(QDialog):
    def __init__(self, parent, sesion: Sesion, empresa_id: int):
        super().__init__(parent)
        self.s, self.empresa_id = sesion, empresa_id
        e = sesion.db.empresa(empresa_id)
        self.setWindowTitle("Selecciona Año a Trabajar")
        self.resize(360, 360)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<b>{e['razon_social']}</b>"))
        self.tabla = Tabla([("Años", 0, "C")], self)
        self.tabla.doubleClicked.connect(lambda _: self._aceptar())
        lay.addWidget(self.tabla, 1)
        fila = QHBoxLayout()
        nuevo = QPushButton(icono(self, "SP_FileIcon"), "Crear nuevo año…")
        nuevo.clicked.connect(self._nuevo)
        fila.addWidget(nuevo)
        fila.addStretch()
        lay.addLayout(fila)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Seleccionar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancela")
        bb.accepted.connect(self._aceptar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.periodo_id = None
        self._cargar()

    def _cargar(self, seleccionar=None):
        per = self.s.db.periodos(self.empresa_id)
        self.tabla.cargar([[str(p["ano"])] for p in per], [p["id"] for p in per])
        if per:
            if not (seleccionar and self.tabla.seleccionar_dato(seleccionar)):
                self.tabla.selectRow(len(per) - 1)       # el año más reciente

    def _nuevo(self):
        import datetime as _dt
        ano, ok = QInputDialog.getInt(self, "Crear nuevo año", "Año de trabajo:", _dt.date.today().year, 1981, 2200)
        if not ok:
            return
        try:
            pid = self.s.db.crear_periodo(self.empresa_id, ano)
        except ErrorDatos as e:
            error(self, str(e))
            return
        self._cargar(pid)

    def _aceptar(self):
        pid = self.tabla.dato_actual()
        if pid is None:
            error(self, "La empresa no tiene años de trabajo. Cree uno con el botón 'Crear nuevo año'.")
            return
        self.periodo_id = pid
        self.accept()
