"""Mantenedores: Empresas (MEMPRESA.PRG), Plan de Cuentas (MCUENTAS.PRG),
Centros de Costo (MCCOSTO.PRG), Proveedores (MPROVEE.PRG) y Usuarios (MUSUA.PRG)."""
from __future__ import annotations

import datetime as _dt

from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QInputDialog, QLineEdit,
                               QSpinBox, QVBoxLayout)

from .. import reports, util
from ..db import ErrorDatos
from .catalogo import Catalogo
from .comunes import CodigoCuentaEdit, MontoEdit, RutEdit, Sesion, error, info


class _Formulario(QDialog):
    """Diálogo base con QFormLayout y botones Acepta / Cancela."""

    def __init__(self, parent, titulo: str):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumWidth(480)
        self.lay = QVBoxLayout(self)
        self.form = QFormLayout()
        self.lay.addLayout(self.form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Acepta")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancela")
        bb.accepted.connect(self._aceptar)
        bb.rejected.connect(self.reject)
        self.lay.addWidget(bb)

    @staticmethod
    def campo(largo: int, mayus: bool = True, valor: str = "") -> QLineEdit:
        e = QLineEdit(valor or "")
        e.setMaxLength(largo)
        if mayus:   # PICTURE "@K!"
            def a_mayusculas(t, e=e):
                if t != t.upper():
                    pos = e.cursorPosition()
                    e.setText(t.upper())
                    e.setCursorPosition(pos)
            e.textEdited.connect(a_mayusculas)
        return e

    def _aceptar(self):
        try:
            self.guardar()
        except ErrorDatos as e:
            error(self, str(e))
            return
        self.accept()

    def guardar(self):  # pragma: no cover - se sobreescribe
        raise NotImplementedError


# ===========================================================================
# EMPRESAS
# ===========================================================================
class FormEmpresa(_Formulario):
    def __init__(self, parent, sesion: Sesion, empresa_id: int | None = None):
        super().__init__(parent, " MANTENCIÓN  DATOS EMPRESAS ")
        self.s, self.empresa_id = sesion, empresa_id
        e = dict(sesion.db.empresa(empresa_id)) if empresa_id else {}
        self.rut = RutEdit()
        self.rut.setText(util.formato_rut(e.get("rut", "")))
        self.rut.setReadOnly(empresa_id is not None)
        self.razon = self.campo(40, valor=e.get("razon_social"))
        self.giro = self.campo(30, valor=e.get("giro"))
        self.direccion = self.campo(40, valor=e.get("direccion"))
        self.ciudad = self.campo(20, valor=e.get("ciudad"))
        self.replegal = self.campo(40, valor=e.get("rep_legal"))
        self.sucursal = self.campo(40, valor=e.get("sucursal"))
        self.honorarios = MontoEdit(valor=e.get("honorarios", 0))
        self.directorio = self.campo(8, valor=e.get("directorio"))
        self.directorio.setReadOnly(empresa_id is not None)
        self.directorio.setToolTip("Código corto de la empresa (en el sistema antiguo era su carpeta).")
        for etiqueta, w in [("R.U.T.", self.rut), ("Razón Social", self.razon), ("Giro", self.giro),
                            ("Dirección", self.direccion), ("Ciudad", self.ciudad),
                            ("Rep. Legal", self.replegal), ("Sucursal", self.sucursal),
                            ("Honorarios", self.honorarios), ("Directorio", self.directorio)]:
            self.form.addRow(etiqueta, w)
        self.ano = None
        if empresa_id is None:
            self.ano = QSpinBox()
            self.ano.setRange(1981, 2200)
            self.ano.setValue(_dt.date.today().year)
            self.form.addRow("Año de trabajo inicial", self.ano)

    def guardar(self):
        datos = dict(rut=self.rut.rut(), razon_social=self.razon.text(), giro=self.giro.text(),
                     direccion=self.direccion.text(), ciudad=self.ciudad.text(), rep_legal=self.replegal.text(),
                     sucursal=self.sucursal.text(), honorarios=self.honorarios.valor(),
                     directorio=self.directorio.text())
        if not datos["razon_social"].strip():
            raise ErrorDatos("Debe ingresar la razón social.")
        self.empresa_id = self.s.db.guardar_empresa(datos, self.empresa_id,
                                                    self.ano.value() if self.ano else None)


def mantener_empresas(parent, sesion: Sesion):
    db = sesion.db

    def cargar(orden):
        return [(e["id"], [util.formato_rut(e["rut"]), e["razon_social"], e["giro"], e["directorio"]])
                for e in db.empresas(orden)]

    def nuevo():
        f = FormEmpresa(parent, sesion)
        if f.exec():
            info(parent, f"Fue creada la empresa con el año {f.ano.value()}.\n"
                         "Selecciónela en Ingresos > Selecciona Empresa para trabajar.")
            return f.empresa_id
        return None

    def modificar(eid):
        f = FormEmpresa(parent, sesion, eid)
        if f.exec():
            sesion.refrescar_empresa()
            return eid
        return None

    def describir(eid):
        e = db.empresa(eid)
        r = db.resumen_empresa(eid)
        return (f"{e['razon_social']}  ({util.formato_rut(e['rut'])})\n\n"
                f"Se eliminarán también sus {r['periodos']} años y {r['asientos']} asientos.")

    def borrar(eid):
        e = db.empresa(eid)
        texto, ok = QInputDialog.getText(parent, "Confirmar eliminación",
                                         f"Para confirmar escriba el RUT de la empresa ({util.formato_rut(e['rut'])}):")
        if not ok or util.limpiar_rut(texto) != e["rut"]:
            raise ErrorDatos("Eliminación cancelada.")
        db.borrar_empresa(eid)
        if sesion.empresa_id == eid:
            sesion.empresa = sesion.periodo = None

    Catalogo(parent, "Datos de Empresas",
             [("R.U.T.", 110, "R"), ("RAZÓN SOCIAL", 0, "L"), ("GIRO", 220, "L"), ("DIRECTORIO", 90, "L")],
             cargar, [("Razón Social", "razon_social"), ("R.U.T.", "rut")],
             nuevo, modificar, borrar, describir, lambda: reports.listado_empresas(db)).exec()


# ===========================================================================
# PLAN DE CUENTAS
# ===========================================================================
class FormCuenta(_Formulario):
    def __init__(self, parent, sesion: Sesion, codigo: str | None = None):
        super().__init__(parent, " MANTENCIÓN PLAN DE CUENTAS ")
        self.s, self.nuevo = sesion, codigo is None
        c = dict(sesion.db.cuenta(sesion.empresa_id, codigo)) if codigo else {}
        self.codigo = CodigoCuentaEdit()
        self.codigo.set_codigo(c.get("codigo", ""))
        self.codigo.setReadOnly(not self.nuevo)
        self.nombre = self.campo(30, valor=c.get("nombre"))
        self.cdocum = QCheckBox("Pide documento de compra al usarla en un asiento")
        self.cdocum.setChecked(bool(c.get("cdocum")))
        self.form.addRow("Código", self.codigo)
        self.form.addRow("Nombre", self.nombre)
        self.form.addRow("", self.cdocum)

    def guardar(self):
        if not self.nombre.text().strip():
            raise ErrorDatos("Debe ingresar el nombre de la cuenta.")
        self.s.db.guardar_cuenta(self.s.empresa_id, self.codigo.codigo(), self.nombre.text(),
                                 self.cdocum.isChecked(), self.nuevo)
        self.cod_guardado = self.codigo.codigo()


def mantener_cuentas(parent, sesion: Sesion):
    db, eid = sesion.db, sesion.empresa_id

    def cargar(orden):
        return [(c["codigo"], [util.formato_codigo(c["codigo"]), c["nombre"], "Sí" if c["cdocum"] else ""])
                for c in db.cuentas(eid, orden)]

    def nuevo():
        f = FormCuenta(parent, sesion)
        return f.cod_guardado if f.exec() else None

    def modificar(cod):
        return cod if FormCuenta(parent, sesion, cod).exec() else None

    Catalogo(parent, f"Plan de Cuentas - {sesion.empresa['razon_social']}",
             [("CÓDIGO", 90, "C"), ("NOMBRE", 0, "L"), ("DOC. COMPRA", 100, "C")],
             cargar, [("Código", "codigo"), ("Nombre", "nombre")], nuevo, modificar,
             lambda cod: db.borrar_cuenta(eid, cod),
             lambda cod: f"Código: {util.formato_codigo(cod)}  {db.nombre_cuenta(eid, cod)}",
             lambda: reports.listado_cuentas(db, eid)).exec()


# ===========================================================================
# CENTROS DE COSTO
# ===========================================================================
class FormCCosto(_Formulario):
    def __init__(self, parent, sesion: Sesion, codigo: str | None = None):
        super().__init__(parent, " MANTENCIÓN C. de Costo ")
        self.s, self.nuevo = sesion, codigo is None
        c = dict(sesion.db.ccosto(sesion.empresa_id, codigo)) if codigo else {}
        self.codigo = self.campo(6, valor=c.get("codigo"))
        self.codigo.setReadOnly(not self.nuevo)
        self.nombre = self.campo(30, valor=c.get("nombre"))
        self.form.addRow("Código", self.codigo)
        self.form.addRow("Nombre", self.nombre)

    def guardar(self):
        self.s.db.guardar_ccosto(self.s.empresa_id, self.codigo.text(), self.nombre.text(), self.nuevo)
        self.cod_guardado = self.codigo.text().strip().upper()


def mantener_ccostos(parent, sesion: Sesion):
    db, eid = sesion.db, sesion.empresa_id

    def cargar(orden):
        return [(c["codigo"], [c["codigo"], c["nombre"]]) for c in db.ccostos(eid, orden)]

    def nuevo():
        f = FormCCosto(parent, sesion)
        return f.cod_guardado if f.exec() else None

    def modificar(cod):
        return cod if FormCCosto(parent, sesion, cod).exec() else None

    Catalogo(parent, f"Centros de Costo - {sesion.empresa['razon_social']}",
             [("CÓDIGO", 90, "L"), ("NOMBRE", 0, "L")],
             cargar, [("Código", "codigo"), ("Nombre", "nombre")], nuevo, modificar,
             lambda cod: db.borrar_ccosto(eid, cod),
             lambda cod: f"Código: {cod}  {db.nombre_ccosto(eid, cod)}",
             lambda: reports.listado_ccostos(db, eid)).exec()


# ===========================================================================
# PROVEEDORES
# ===========================================================================
class FormProveedor(_Formulario):
    def __init__(self, parent, sesion: Sesion, rut: str | None = None):
        super().__init__(parent, " MANTENCIÓN PROVEEDORES ")
        self.s, self.nuevo = sesion, rut is None
        p = dict(sesion.db.proveedor(sesion.empresa_id, rut)) if rut else {}
        self.rut = RutEdit()
        self.rut.setText(util.formato_rut(p.get("rut", "")))
        self.rut.setReadOnly(not self.nuevo)
        self.nombre = self.campo(50, valor=p.get("nombre"))
        self.direccion = self.campo(40, False, p.get("direccion"))
        self.ciudad = self.campo(30, False, p.get("ciudad"))
        self.giro = self.campo(45, False, p.get("giro"))
        self.email = self.campo(30, False, p.get("email"))
        self.telefono = self.campo(20, False, p.get("telefono"))
        for etiqueta, w in [("R.U.T.", self.rut), ("Nombre / Razón social", self.nombre),
                            ("Dirección", self.direccion), ("Ciudad", self.ciudad), ("Giro", self.giro),
                            ("E-mail", self.email), ("Teléfono", self.telefono)]:
            self.form.addRow(etiqueta, w)

    def guardar(self):
        if not self.nombre.text().strip():
            raise ErrorDatos("Debe ingresar el nombre del proveedor.")
        datos = dict(rut=self.rut.rut(), nombre=self.nombre.text(), direccion=self.direccion.text(),
                     ciudad=self.ciudad.text(), giro=self.giro.text(), email=self.email.text(),
                     telefono=self.telefono.text())
        self.s.db.guardar_proveedor(self.s.empresa_id, datos, self.nuevo)
        self.rut_guardado = util.limpiar_rut(datos["rut"])


def nuevo_proveedor(parent, sesion: Sesion) -> str | None:
    f = FormProveedor(parent, sesion)
    return f.rut_guardado if f.exec() else None


def mantener_proveedores(parent, sesion: Sesion):
    db, eid = sesion.db, sesion.empresa_id

    def cargar(orden):
        return [(p["rut"], [util.formato_rut(p["rut"]), p["nombre"], p["giro"], p["ciudad"]])
                for p in db.proveedores(eid, orden)]

    def modificar(rut):
        return rut if FormProveedor(parent, sesion, rut).exec() else None

    Catalogo(parent, f"Proveedores - {sesion.empresa['razon_social']}",
             [("R.U.T.", 110, "R"), ("RAZÓN SOCIAL", 0, "L"), ("GIRO", 200, "L"), ("CIUDAD", 120, "L")],
             cargar, [("R.U.T.", "rut"), ("Nombre", "nombre")], lambda: nuevo_proveedor(parent, sesion),
             modificar, lambda rut: db.borrar_proveedor(eid, rut),
             lambda rut: f"{util.formato_rut(rut)}  {db.nombre_proveedor(eid, rut)}",
             lambda: reports.listado_proveedores(db, eid)).exec()


# ===========================================================================
# USUARIOS
# ===========================================================================
class FormUsuario(_Formulario):
    def __init__(self, parent, sesion: Sesion, usuario: str | None = None):
        super().__init__(parent, "Usuario del sistema")
        self.s, self.nuevo = sesion, usuario is None
        u = dict(sesion.db.usuario(usuario)) if usuario else {}
        self.usuario = self.campo(10, valor=u.get("usuario"))
        self.usuario.setReadOnly(not self.nuevo)
        self.nombre = self.campo(35, valor=u.get("nombre"))
        self.clave = QLineEdit()
        self.clave.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirma = QLineEdit()
        self.confirma.setEchoMode(QLineEdit.EchoMode.Password)
        if not self.nuevo:
            self.clave.setPlaceholderText("(dejar en blanco para no cambiarla)")
        self.admin = QCheckBox("Administrador (puede mantener usuarios)")
        self.admin.setChecked(bool(u.get("es_admin")))
        for etiqueta, w in [("Usuario", self.usuario), ("Nombre", self.nombre), ("Clave", self.clave),
                            ("Confirma clave", self.confirma), ("", self.admin)]:
            self.form.addRow(etiqueta, w)

    def guardar(self):
        if self.clave.text() != self.confirma.text():
            raise ErrorDatos("Debe ingresar la misma clave en ambos campos.")
        self.s.db.guardar_usuario(self.usuario.text(), self.nombre.text(), self.clave.text() or None,
                                  self.admin.isChecked(), self.nuevo)
        self.usuario_guardado = self.usuario.text().strip().upper()


def mantener_usuarios(parent, sesion: Sesion):
    if not sesion.es_admin:
        error(parent, "Usuario no autorizado.")
        return
    db = sesion.db

    def cargar(_):
        return [(u["usuario"], [u["usuario"], u["nombre"], "Sí" if u["es_admin"] else ""]) for u in db.usuarios()]

    def nuevo():
        f = FormUsuario(parent, sesion)
        return f.usuario_guardado if f.exec() else None

    def borrar(u):
        if u == sesion.usuario["usuario"]:
            raise ErrorDatos("No puede eliminar el usuario con el que está trabajando.")
        db.borrar_usuario(u)

    Catalogo(parent, "Control de Acceso de Usuarios",
             [("USUARIO", 120, "L"), ("NOMBRE", 0, "L"), ("ADMIN.", 70, "C")],
             cargar, [("Usuario", "usuario")], nuevo,
             lambda u: u if FormUsuario(parent, sesion, u).exec() else None,
             borrar, lambda u: f"Usuario {u}").exec()
