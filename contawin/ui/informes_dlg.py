"""Diálogos de parámetros de los informes (DLG_PERINFOR, DLG_PERBALAN, DLG_BALTI,
DLG_LIBROXTIPO, DLG_MAYOR, LIBROCOMPRA)."""
from __future__ import annotations

import datetime as _dt

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QVBoxLayout)

from .. import reports, util
from . import impresion, tema
from .comunes import Buscador, FechaEdit, Sesion, error


class ParametrosDialog(QDialog):
    def __init__(self, parent, sesion: Sesion, titulo: str, desde=True, tipo=False, cuentas=False,
                 ccosto=False, rango=(None, None), formato_balance=False):
        super().__init__(parent)
        self.s = sesion
        self.setWindowTitle(titulo)
        self.setMinimumWidth(480)
        lay = tema.margenes(QVBoxLayout(self))
        lay.addWidget(tema.etiqueta(titulo, "titulo"))
        if sesion.empresa:
            lay.addWidget(tema.etiqueta(f"{sesion.empresa['razon_social']} · Año {sesion.ano}", "secundario"))
        form = tema.formulario(QFormLayout())
        d, h = rango
        ano = sesion.ano or _dt.date.today().year
        d = d or _dt.date(ano, 1, 1)
        h = h or _dt.date(ano, 12, 31)

        self.cb_tipo = None
        if tipo:
            self.cb_tipo = QComboBox()
            for t, nom in util.TIPOS_ASIENTO.items():
                self.cb_tipo.addItem(f"{t} - {nom}", t)
            form.addRow("Tipo de asiento", self.cb_tipo)

        self.f_desde = FechaEdit(fecha=d) if desde else None
        if self.f_desde:
            form.addRow("Desde", self.f_desde)
        self.f_hasta = FechaEdit(fecha=h)
        form.addRow("Hasta", self.f_hasta)

        self.c_desde = self.c_hasta = None
        if cuentas:
            lista = [(c["codigo"], c["nombre"]) for c in sesion.db.cuentas(sesion.empresa_id)]
            self.c_desde, self.c_hasta = Buscador(), Buscador()
            for b in (self.c_desde, self.c_hasta):
                b.set_items(lista, util.formato_codigo)
            if lista:
                self.c_desde.set_codigo(lista[0][0])
                self.c_hasta.set_codigo(lista[-1][0])
            form.addRow("Cuenta desde", self.c_desde)
            form.addRow("Cuenta hasta", self.c_hasta)

        self.cc = self.todos = None
        if ccosto:
            self.todos = QCheckBox("Todos los centros de costo")
            self.todos.setChecked(True)
            self.cc = Buscador(permitir_vacio=True, texto_vacio="(sin centro de costo)")
            self.cc.set_items([(c["codigo"], c["nombre"]) for c in sesion.db.ccostos(sesion.empresa_id)])
            self.cc.setEnabled(False)
            self.todos.toggled.connect(lambda v: self.cc.setEnabled(not v))
            form.addRow("", self.todos)
            form.addRow("Centro de costo", self.cc)

        self.cb_formato = None
        if formato_balance:
            self.cb_formato = QComboBox()
            self.cb_formato.addItem("Borrador · con códigos de cuenta", False)
            self.cb_formato.addItem("Tributario · correlativo en lugar de códigos (para bancos y terceros)", True)
            form.addRow("Formato", self.cb_formato)

        self.f_emision = FechaEdit(fecha=_dt.date.today())
        form.addRow("Fecha de emisión", self.f_emision)
        lay.addLayout(form)
        lay.addSpacing(tema.ESPACIO[2])
        bb = tema.botones_dialogo("Generar informe", "Cancelar")
        bb.accepted.connect(self._aceptar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _aceptar(self):
        if self.f_desde and self.f_hasta.fecha() < self.f_desde.fecha():
            error(self, "La fecha Hasta debe ser mayor o igual a Desde.")
            return
        if self.c_desde and (self.c_desde.codigo() is None or self.c_hasta.codigo() is None):
            error(self, "Selecciona las cuentas desde y hasta.")
            return
        self.accept()

    @property
    def desde(self):
        return self.f_desde.fecha() if self.f_desde else None

    @property
    def hasta(self):
        return self.f_hasta.fecha()

    @property
    def emision(self):
        return self.f_emision.fecha()

    @property
    def tributario(self) -> bool:
        return bool(self.cb_formato and self.cb_formato.currentData())


def _rango_asientos(sesion: Sesion):
    return sesion.db.rango_fechas(sesion.periodo_id)


def libro_diario(parent, sesion: Sesion, por_tipo: bool = False):
    dlg = ParametrosDialog(parent, sesion, "Libro diario por tipo" if por_tipo else "Libro diario",
                           tipo=por_tipo, rango=_rango_asientos(sesion))
    if dlg.exec():
        impresion.mostrar(parent, reports.libro_diario(
            sesion.db, sesion.empresa_id, sesion.periodo_id, dlg.desde, dlg.hasta,
            dlg.cb_tipo.currentData() if por_tipo else None, dlg.emision))


def libro_mayor(parent, sesion: Sesion):
    dlg = ParametrosDialog(parent, sesion, "Movimientos de mayor", cuentas=True, rango=_rango_asientos(sesion))
    if dlg.exec():
        d, h = sorted([dlg.c_desde.codigo(), dlg.c_hasta.codigo()])
        impresion.mostrar(parent, reports.libro_mayor(sesion.db, sesion.empresa_id, sesion.periodo_id,
                                                      dlg.desde, dlg.hasta, d, h, dlg.emision))


def balance_8(parent, sesion: Sesion):
    dlg = ParametrosDialog(parent, sesion, "Balance de 8 columnas", rango=_rango_asientos(sesion),
                           formato_balance=True)
    if dlg.exec():
        impresion.mostrar(parent, reports.balance_8_columnas(sesion.db, sesion.empresa_id, sesion.periodo_id,
                                                             dlg.desde, dlg.hasta, dlg.emision, dlg.tributario))


def balance_tipo_informe(parent, sesion: Sesion):
    dlg = ParametrosDialog(parent, sesion, "Balance tipo informe", desde=False, rango=_rango_asientos(sesion),
                           formato_balance=True)
    if dlg.exec():
        impresion.mostrar(parent, reports.balance_tipo_informe(sesion.db, sesion.empresa_id, sesion.periodo_id,
                                                               dlg.hasta, dlg.emision, dlg.tributario))


def libro_compras(parent, sesion: Sesion):
    dlg = ParametrosDialog(parent, sesion, "Libro de compras", ccosto=True,
                           rango=sesion.db.rango_fechas_compras(sesion.periodo_id))
    if dlg.exec():
        cc = None if dlg.todos.isChecked() else (dlg.cc.codigo() or "")
        impresion.mostrar(parent, reports.libro_compras(sesion.db, sesion.empresa_id, sesion.periodo_id,
                                                        dlg.desde, dlg.hasta, cc, dlg.emision))
