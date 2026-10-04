"""Inicio de sesión (ChkPass / diálogo INICIAL) y selección de empresa y año
(Sel_Empresa / DLG_SelEmpresa, SLaEmpresa / DLG_SELANOS)."""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QInputDialog, QLineEdit, QVBoxLayout)

from .. import util
from ..db import ErrorDatos
from . import tema
from .comunes import Sesion, Tabla, error


class LoginDialog(QDialog):
    """Inicio de sesión: tarjeta centrada con usuario, confirmación del nombre, clave
    con mostrar/ocultar, Ingresar (primario) y Salir (patrón del sistema de diseño)."""

    def __init__(self, sesion: Sesion, titulo: str):
        super().__init__()
        self.s = sesion
        self.intentos = 0
        self.setWindowTitle("Selección de usuario")
        self.setMinimumWidth(440)
        fondo = tema.margenes(QVBoxLayout(self), 8)
        card = tema.tarjeta(self)
        fondo.addWidget(card)
        lay = tema.margenes(QVBoxLayout(card), 6)

        lay.addWidget(tema.etiqueta("ContaWin", "titulo"))
        lay.addWidget(tema.etiqueta(f"{titulo} · Ingresa con tu usuario y clave", "ayuda"))
        lay.addSpacing(tema.ESPACIO[2])

        lay.addWidget(tema.etiqueta("Usuario", "etiqueta"))
        self.usuario = QLineEdit()
        self.usuario.setMaxLength(10)
        self.usuario.setPlaceholderText("Ej.: CAC")
        lay.addWidget(self.usuario)
        self.nombre = tema.etiqueta("", "ayuda")       # confirmación: CAC -> Claudio Cofré V.
        lay.addWidget(self.nombre)

        lay.addWidget(tema.etiqueta("Clave", "etiqueta"))
        self.clave = QLineEdit()
        self.clave.setEchoMode(QLineEdit.EchoMode.Password)
        self.a_ver = QAction(tema.icono("ojo"), "Mostrar clave", self)
        self.a_ver.setToolTip("Mostrar u ocultar la clave")
        self.a_ver.triggered.connect(self._mostrar_ocultar)
        self.clave.addAction(self.a_ver, QLineEdit.ActionPosition.TrailingPosition)
        lay.addWidget(self.clave)
        self.lbl_error = tema.etiqueta("", "ayuda")
        tema.marcar(self.lbl_error, estado="error")
        lay.addWidget(self.lbl_error)

        lay.addSpacing(tema.ESPACIO[2])
        self.b_ingresar = tema.boton("Ingresar", variante="primario")
        self.b_salir = tema.boton("Salir")
        for b in (self.b_ingresar, self.b_salir):
            b.setAutoDefault(False)        # Enter avanza entre campos; en la clave, ingresa
            lay.addWidget(b)
        self.b_ingresar.clicked.connect(self._aceptar)
        self.b_salir.clicked.connect(self.reject)

        self.usuario.editingFinished.connect(self._mostrar_nombre)
        self.usuario.returnPressed.connect(self.clave.setFocus)
        self.clave.returnPressed.connect(self._aceptar)
        self.usuario.setFocus()

    def _mostrar_ocultar(self):
        oculta = self.clave.echoMode() == QLineEdit.EchoMode.Password
        self.clave.setEchoMode(QLineEdit.EchoMode.Normal if oculta else QLineEdit.EchoMode.Password)
        self.a_ver.setIcon(tema.icono("ojo_cerrado" if oculta else "ojo"))
        self.a_ver.setText("Ocultar clave" if oculta else "Mostrar clave")

    def _mostrar_nombre(self):
        texto = self.usuario.text().strip()
        u = self.s.db.usuario(texto) if texto else None
        if u:
            self.nombre.setText(f"✓ {u['nombre']}")
            tema.marcar(self.nombre, estado="")
        else:
            self.nombre.setText("No existe ese usuario." if texto else "")
            tema.marcar(self.nombre, estado="error" if texto else "")

    def _aceptar(self):
        u = self.s.db.login(self.usuario.text(), self.clave.text())
        if not u:
            self.intentos += 1
            restantes = 3 - self.intentos
            self.lbl_error.setText("Usuario o clave incorrectos. "
                                   + (f"Te quedan {restantes} intentos." if restantes > 1 else "Te queda 1 intento."
                                      if restantes > 0 else "Acceso no autorizado."))
            tema.marcar(self.clave, error=True)
            self.clave.clear()
            self.clave.setFocus()
            if self.intentos >= 3:
                error(self, "Acceso no autorizado.\n\nSe superó el número de intentos.")
                self.reject()
            return
        tema.marcar(self.clave, error=False)
        self.s.usuario = dict(u)
        self.accept()


class SeleccionEmpresaDialog(QDialog):
    """Selecciona empresa y luego año de trabajo."""

    def __init__(self, parent, sesion: Sesion):
        super().__init__(parent)
        self.s = sesion
        self.setWindowTitle("Seleccionar empresa")
        self.resize(780, 520)
        lay = tema.margenes(QVBoxLayout(self))
        lay.addWidget(tema.etiqueta("Selecciona la empresa", "titulo"))
        lay.addWidget(tema.etiqueta("Luego elegirás el año de trabajo. Doble clic o Enter para continuar.", "ayuda"))
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar por RUT, razón social o giro")
        self.buscar.setClearButtonEnabled(True)
        self.buscar.addAction(tema.icono("buscar"), QLineEdit.ActionPosition.LeadingPosition)
        lay.addWidget(self.buscar)
        self.tabla = Tabla([("RUT", 120, "R"), ("Razón social", 0, "L"), ("Giro", 220, "L")], self)
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
        bb = tema.botones_dialogo("Continuar", "Cancelar")
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
        self.setWindowTitle("Seleccionar año de trabajo")
        self.resize(400, 440)
        lay = tema.margenes(QVBoxLayout(self))
        lay.addWidget(tema.etiqueta("Año de trabajo", "titulo"))
        lay.addWidget(tema.etiqueta(e["razon_social"], "secundario"))
        self.tabla = Tabla([("Año", 0, "C")], self)
        self.tabla.doubleClicked.connect(lambda _: self._aceptar())
        lay.addWidget(self.tabla, 1)
        fila = QHBoxLayout()
        nuevo = tema.boton("Crear nuevo año…", "mas")
        nuevo.clicked.connect(self._nuevo)
        fila.addWidget(nuevo)
        fila.addStretch()
        lay.addLayout(fila)
        bb = tema.botones_dialogo("Seleccionar", "Cancelar")
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
        # si hay año anterior con saldos, se ofrece el asiento de apertura (balance del año anterior)
        from .apertura import crear_ano
        try:
            pid = crear_ano(self, self.s.db, self.empresa_id, ano)
        except ErrorDatos as e:
            error(self, str(e))
            return
        if pid:
            self._cargar(pid)

    def _aceptar(self):
        pid = self.tabla.dato_actual()
        if pid is None:
            error(self, "La empresa no tiene años de trabajo. Crea uno con el botón «Crear nuevo año…».")
            return
        self.periodo_id = pid
        self.accept()
