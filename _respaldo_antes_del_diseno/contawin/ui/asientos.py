"""Asientos contables (ASIENTOS.PRG): mantención de comprobantes, detalle de
cuentas y documentos de compra (DLG_ASIENTOS, DLG_DETALLE, DOCCOMPRA)."""
from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import Qt
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QKeySequence, QRegularExpressionValidator, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout)

from .. import reports, util
from ..db import ErrorDatos
from . import impresion
from .catalogo import Catalogo
from .comunes import (Buscador, FechaEdit, MontoEdit, Sesion, Tabla, confirmar, error, icono)
from .mantenedores import nuevo_proveedor


def _mayusculas(e: QLineEdit):
    def f(t):
        if t != t.upper():
            pos = e.cursorPosition()
            e.setText(t.upper())
            e.setCursorPosition(pos)
    e.textEdited.connect(f)


# ===========================================================================
# Documento de compra (IngDetCompra / DOCCOMPRA)
# ===========================================================================
class DocumentoCompraDialog(QDialog):
    def __init__(self, parent, sesion: Sesion, codigo: str, debe: int, haber: int,
                 doc: dict | None, cdcosto: str, fecha_asiento: _dt.date):
        super().__init__(parent)
        self.s = sesion
        self.setWindowTitle(" INGRESO DETALLE DOCUMENTO DE COMPRAS")
        self.setMinimumWidth(620)
        doc = dict(doc or {})
        total = debe if debe else haber
        lay = QVBoxLayout(self)

        g1 = QGroupBox()
        f1 = QGridLayout(g1)
        nombre = sesion.db.nombre_cuenta(sesion.empresa_id, codigo)
        for col, (et, val) in enumerate([("Cuenta", f"{util.formato_codigo(codigo)}  {nombre}"),
                                         ("Debe", util.fmt_monto(debe)), ("Haber", util.fmt_monto(haber))]):
            f1.addWidget(QLabel(et), 0, col * 2)
            e = QLineEdit(val)
            e.setReadOnly(True)
            f1.addWidget(e, 0, col * 2 + 1)
        lay.addWidget(g1)

        form = QFormLayout()
        self.tipo = QComboBox()
        for i, (_, nom) in enumerate(util.TIPOS_DOCUMENTO, 1):
            self.tipo.addItem(f"{i:2d}.- {nom}", i)
        self.tipo.setCurrentIndex(max(0, int(doc.get("tdocum") or 1) - 1))
        self.numero = QLineEdit(str(doc.get("numero_doc") or ""))
        self.numero.setValidator(QRegularExpressionValidator(QRegularExpression(r"[0-9]{1,12}"), self))
        self.fecha = FechaEdit(fecha=doc.get("fecha_doc") or fecha_asiento)

        fila_prov = QHBoxLayout()
        self.proveedor = Buscador()
        self._cargar_proveedores()
        self.proveedor.set_codigo(doc.get("rut_prov"))
        b_nuevo = QPushButton(icono(self, "SP_FileIcon"), "Nuevo…")
        b_nuevo.setToolTip("Crear un proveedor nuevo")
        b_nuevo.clicked.connect(self._nuevo_proveedor)
        fila_prov.addWidget(self.proveedor, 1)
        fila_prov.addWidget(b_nuevo)

        self.neto = MontoEdit(valor=doc.get("neto", 0))
        self.iva = MontoEdit(valor=doc.get("iva", 0))
        self.total = MontoEdit(valor=total)
        self.total.setReadOnly(True)
        fila_montos = QHBoxLayout()
        for et, w in [("Neto", self.neto), ("I.V.A.", self.iva), ("Total", self.total)]:
            fila_montos.addWidget(QLabel(et))
            fila_montos.addWidget(w)
        b_calc = QPushButton("Calcular IVA")
        b_calc.clicked.connect(self._calcular)
        fila_montos.addWidget(b_calc)

        self.detalle = QLineEdit(doc.get("detalle", ""))
        self.detalle.setMaxLength(40)
        _mayusculas(self.detalle)
        fila_pago = QHBoxLayout()
        self.pagado = QCheckBox("Pagado el")
        self.fecha_pago = FechaEdit(fecha=doc.get("fecha_pago") or fecha_asiento)
        self.pagado.setChecked(bool(doc.get("fecha_pago")))
        self.fecha_pago.setEnabled(self.pagado.isChecked())
        self.pagado.toggled.connect(self.fecha_pago.setEnabled)
        fila_pago.addWidget(self.pagado)
        fila_pago.addWidget(self.fecha_pago)
        fila_pago.addStretch()

        form.addRow("T. Documento", self.tipo)
        form.addRow("N° Documento", self.numero)
        form.addRow("Fecha documento", self.fecha)
        form.addRow("Proveedor", fila_prov)
        form.addRow("", fila_montos)
        form.addRow("Detalle", self.detalle)
        form.addRow("Fecha de pago", fila_pago)
        lay.addLayout(form)
        self.cdcosto = cdcosto

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Acepta")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancela")
        bb.accepted.connect(self._aceptar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        if not doc.get("neto") and not doc.get("iva"):
            self._calcular()
        self.tipo.currentIndexChanged.connect(lambda _: self._calcular())
        self.documento: dict | None = None

    def _cargar_proveedores(self):
        self.proveedor.set_items([(p["rut"], p["nombre"]) for p in
                                  self.s.db.proveedores(self.s.empresa_id, "nombre")], util.formato_rut)

    def _nuevo_proveedor(self):
        rut = nuevo_proveedor(self, self.s)
        if rut:
            self._cargar_proveedores()
            self.proveedor.set_codigo(rut)

    def _calcular(self):
        total = self.total.valor()
        if self.tipo.currentData() in util.DOCS_AFECTOS:
            neto = int(round(total / (1 + util.TASA_IVA)))
            self.neto.set_valor(neto)
            self.iva.set_valor(total - neto)
        else:
            self.neto.set_valor(total)
            self.iva.set_valor(0)

    def _aceptar(self):
        num = int(self.numero.text() or 0)
        if num == 0:
            error(self, "Debe ingresar el número de documento.")
            self.numero.setFocus()
            return
        rut = self.proveedor.codigo()
        if not rut:
            error(self, "Seleccione un proveedor existente (o créelo con el botón Nuevo).")
            self.proveedor.setFocus()
            return
        if not self.detalle.text().strip():
            error(self, "Debe ingresar el detalle.")
            self.detalle.setFocus()
            return
        self.documento = dict(
            tdocum=self.tipo.currentData(), numero_doc=num, fecha_doc=self.fecha.fecha(), rut_prov=rut,
            neto=self.neto.valor(), iva=self.iva.valor(), adicional=0, total=self.total.valor(),
            cdcosto=self.cdcosto, detalle=self.detalle.text().strip().upper(),
            fecha_pago=self.fecha_pago.fecha() if self.pagado.isChecked() else None)
        self.accept()


# ===========================================================================
# Línea de detalle (GetDetalle / DLG_DETALLE)
# ===========================================================================
class LineaDialog(QDialog):
    def __init__(self, parent, sesion: Sesion, cuentas: list, linea: dict | None,
                 cdcosto: str, fecha_asiento: _dt.date, sugerencia: tuple[int, int] = (0, 0)):
        super().__init__(parent)
        self.s, self.cdcosto, self.fecha_asiento = sesion, cdcosto, fecha_asiento
        self.cuentas = {c["codigo"]: c for c in cuentas}
        self.linea_original = linea or {}
        self.setWindowTitle(" INGRESO DETALLE ASIENTO ")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.cuenta = Buscador()
        self.cuenta.set_items([(c["codigo"], c["nombre"]) for c in cuentas], util.formato_codigo)
        self.cuenta.set_codigo(self.linea_original.get("codigo"))
        self.debe = MontoEdit(valor=self.linea_original.get("debe", sugerencia[0]))
        self.haber = MontoEdit(valor=self.linea_original.get("haber", sugerencia[1]))
        self.aviso_doc = QLabel("")
        self.aviso_doc.setStyleSheet("color:#1f3864")
        self.cuenta.currentIndexChanged.connect(lambda _: self._aviso())
        form.addRow("Cuenta", self.cuenta)
        form.addRow("", self.aviso_doc)
        form.addRow("Debe", self.debe)
        form.addRow("Haber", self.haber)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Acepta")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancela")
        bb.accepted.connect(self._aceptar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._aviso()
        self.linea: dict | None = None
        self.cuenta.setFocus()

    def _aviso(self):
        c = self.cuentas.get(self.cuenta.codigo() or "")
        self.aviso_doc.setText("Esta cuenta pide documento de compra." if c and c["cdocum"] else "")

    def _aceptar(self):
        codigo = self.cuenta.codigo()
        c = self.cuentas.get(codigo or "")
        if not c:
            error(self, "Seleccione una cuenta del plan de cuentas.")
            self.cuenta.setFocus()
            return
        debe, haber = self.debe.valor(), self.haber.valor()
        if debe < 0 or haber < 0:
            error(self, "Los montos no pueden ser negativos.")
            return
        if debe == 0 and haber == 0:
            error(self, "Debe ingresar un monto en el Debe o en el Haber.")
            self.debe.setFocus()
            return
        if debe and haber:
            error(self, "Ingrese el monto en el Debe o en el Haber, no en ambos.")
            return
        documento = None
        if c["cdocum"]:
            dlg = DocumentoCompraDialog(self, self.s, codigo, debe, haber, self.linea_original.get("documento"),
                                        self.cdcosto, self.fecha_asiento)
            if not dlg.exec():
                return
            documento = dlg.documento
        self.linea = dict(codigo=codigo, debe=debe, haber=haber, documento=documento)
        self.accept()


# ===========================================================================
# Editor de asiento (GetAsientos / DLG_ASIENTOS)
# ===========================================================================
class AsientoEditor(QDialog):
    def __init__(self, parent, sesion: Sesion, asiento_id: int | None = None):
        super().__init__(parent)
        self.s, self.asiento_id = sesion, asiento_id
        db = sesion.db
        self.cuentas = db.cuentas(sesion.empresa_id)
        self.nombres = {c["codigo"]: c["nombre"] for c in self.cuentas}
        a = dict(db.asiento(asiento_id)) if asiento_id else {}
        self.lineas: list[dict] = db.detalle_asiento(asiento_id) if asiento_id else []
        self.modificado = False
        self.setWindowTitle(" MODIFICA ASIENTO " if asiento_id else " INGRESO ASIENTO ")
        self.resize(900, 600)

        lay = QVBoxLayout(self)
        cab = QGroupBox()
        g = QGridLayout(cab)
        num = a.get("numero") or db.siguiente_numero(sesion.periodo_id)
        self.lbl_numero = QLabel(f"<span style='font-size:16pt;font-weight:bold'>N° {util.fmt_monto(num)}</span>"
                                 + ("" if asiento_id else "  <i>(nuevo)</i>"))
        self.tipo = QComboBox()
        for t, nom in util.TIPOS_ASIENTO.items():
            self.tipo.addItem(f"{t} - {nom}", t)
        self.tipo.setCurrentIndex(max(0, self.tipo.findData(a.get("tipo") or "T")))
        self.fecha = FechaEdit(fecha=a.get("fecha") or self._fecha_sugerida())
        self.glosa = QLineEdit(a.get("glosa", ""))
        self.glosa.setMaxLength(60)
        _mayusculas(self.glosa)
        self.ccosto = Buscador(permitir_vacio=True, texto_vacio="(sin centro de costo)")
        self.ccosto.set_items([(c["codigo"], c["nombre"]) for c in db.ccostos(sesion.empresa_id)])
        self.ccosto.set_codigo(a.get("cdcosto", ""))
        g.addWidget(self.lbl_numero, 0, 0, 1, 2)
        g.addWidget(QLabel("Tipo"), 0, 2)
        g.addWidget(self.tipo, 0, 3)
        g.addWidget(QLabel("Fecha"), 0, 4)
        g.addWidget(self.fecha, 0, 5)
        g.addWidget(QLabel("Glosa"), 1, 0)
        g.addWidget(self.glosa, 1, 1, 1, 5)
        g.addWidget(QLabel("C. de Costo"), 2, 0)
        g.addWidget(self.ccosto, 2, 1, 1, 5)
        lay.addWidget(cab)
        for w in (self.tipo, self.ccosto):
            w.currentIndexChanged.connect(self._marcar)
        self.glosa.textEdited.connect(self._marcar)
        self.fecha.dateChanged.connect(self._marcar)

        self.tabla = Tabla([("Código", 90, "C"), ("Nombre Cuenta", 0, "L"), ("D e b e", 130, "R"),
                            ("H a b e r", 130, "R"), ("Documento", 190, "L")], self)
        self.tabla.doubleClicked.connect(lambda _: self.modificar_linea())
        lay.addWidget(self.tabla, 1)

        fila = QHBoxLayout()
        for texto, ic, acc in [("Nueva línea", "SP_FileIcon", self.nueva_linea),
                               ("Modifica línea", "SP_FileDialogDetailedView", self.modificar_linea),
                               ("Borra línea", "SP_TrashIcon", self.borrar_linea)]:
            b = QPushButton(icono(self, ic), texto)
            b.clicked.connect(acc)
            fila.addWidget(b)
        fila.addStretch()
        self.tot_debe = QLineEdit()
        self.tot_haber = QLineEdit()
        for w in (self.tot_debe, self.tot_haber):
            w.setReadOnly(True)
            w.setAlignment(Qt.AlignmentFlag.AlignRight)
            w.setFixedWidth(130)
        self.lbl_dif = QLabel()
        fila.addWidget(QLabel("Totales"))
        fila.addWidget(self.tot_debe)
        fila.addWidget(self.tot_haber)
        fila.addWidget(self.lbl_dif)
        lay.addLayout(fila)

        bot = QHBoxLayout()
        bot.addStretch()
        for texto, ic, acc in [("&Guardar", "SP_DialogSaveButton", self.guardar),
                               ("Guardar e &imprimir", "SP_FileDialogContentsView", self.guardar_imprimir),
                               ("&Salir", "SP_DialogCloseButton", self.reject)]:
            b = QPushButton(icono(self, ic), texto)
            b.clicked.connect(acc)
            bot.addWidget(b)
        lay.addLayout(bot)

        for tecla, accion in [(Qt.Key.Key_Insert, self.nueva_linea), (Qt.Key.Key_Delete, self.borrar_linea),
                              (Qt.Key.Key_Return, self.modificar_linea)]:
            atajo = QShortcut(QKeySequence(tecla), self.tabla)
            atajo.setContext(Qt.ShortcutContext.WidgetShortcut)
            atajo.activated.connect(accion)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.guardar)
        self._refrescar()
        self.modificado = False
        (self.glosa if not asiento_id else self.tabla).setFocus()

    def _fecha_sugerida(self) -> _dt.date:
        hoy = _dt.date.today()
        ano = self.s.ano or hoy.year
        if hoy.year == ano:
            return hoy
        ultimo = self.s.db.q1("SELECT MAX(fecha) f FROM asiento WHERE periodo_id=?", (self.s.periodo_id,))
        return util.from_iso(ultimo["f"]) if ultimo and ultimo["f"] else _dt.date(ano, 1, 1)

    def _marcar(self, *_):
        self.modificado = True

    def _totales(self) -> tuple[int, int]:
        return sum(l["debe"] for l in self.lineas), sum(l["haber"] for l in self.lineas)

    def _refrescar(self, seleccionar: int | None = None):
        filas = []
        for l in self.lineas:
            d = l.get("documento")
            doc = (f"{util.sigla_documento(d['tdocum'])} N° {util.fmt_monto(d['numero_doc'])}" if d else "")
            filas.append([util.formato_codigo(l["codigo"]), self.nombres.get(l["codigo"], "(no existe)"),
                          util.fmt_monto(l["debe"], True), util.fmt_monto(l["haber"], True), doc])
        self.tabla.cargar(filas, list(range(len(filas))))
        if seleccionar is not None and 0 <= seleccionar < len(filas):
            self.tabla.selectRow(seleccionar)
        td, th = self._totales()
        self.tot_debe.setText(util.fmt_monto(td))
        self.tot_haber.setText(util.fmt_monto(th))
        if td == th:
            self.lbl_dif.setObjectName("totalOk")
            self.lbl_dif.setText("✔ Cuadrado" if td else "")
        else:
            self.lbl_dif.setObjectName("totalMal")
            self.lbl_dif.setText(f"Diferencia: {util.fmt_monto(td - th)}")
        self.lbl_dif.style().unpolish(self.lbl_dif)
        self.lbl_dif.style().polish(self.lbl_dif)

    def _cdcosto(self) -> str:
        return self.ccosto.codigo() or ""

    def nueva_linea(self):
        td, th = self._totales()
        sugerencia = (th - td, 0) if th > td else (0, td - th)   # propone el monto que falta para cuadrar
        dlg = LineaDialog(self, self.s, self.cuentas, None, self._cdcosto(), self.fecha.fecha(), sugerencia)
        if dlg.exec() and dlg.linea:
            self.lineas.append(dlg.linea)
            self.modificado = True
            self._refrescar(len(self.lineas) - 1)

    def modificar_linea(self):
        i = self.tabla.dato_actual()
        if i is None:
            return
        dlg = LineaDialog(self, self.s, self.cuentas, self.lineas[i], self._cdcosto(), self.fecha.fecha())
        if dlg.exec() and dlg.linea:
            self.lineas[i] = dlg.linea
            self.modificado = True
            self._refrescar(i)

    def borrar_linea(self):
        i = self.tabla.dato_actual()
        if i is None:
            return
        l = self.lineas[i]
        if confirmar(self, f"¿Borrar la línea {util.formato_codigo(l['codigo'])} "
                           f"{self.nombres.get(l['codigo'], '')}?"):
            del self.lineas[i]
            self.modificado = True
            self._refrescar(min(i, len(self.lineas) - 1))

    def _grabar(self) -> bool:
        fecha = self.fecha.fecha()
        if self.s.ano and fecha.year != self.s.ano:
            if not confirmar(self, f"La fecha {util.fmt_fecha(fecha)} no corresponde al año de trabajo "
                                   f"({self.s.ano}).\n¿Grabar de todas formas?"):
                return False
        cab = dict(tipo=self.tipo.currentData(), fecha=fecha, glosa=self.glosa.text(), cdcosto=self._cdcosto())
        # el centro de costo de la cabecera se propaga a los documentos de compra (como el original)
        for l in self.lineas:
            if l.get("documento"):
                l["documento"]["cdcosto"] = cab["cdcosto"]
        try:
            self.asiento_id = self.s.db.guardar_asiento(self.s.periodo_id, cab, self.lineas, self.asiento_id)
        except ErrorDatos as e:
            error(self, str(e))
            return False
        self.modificado = False
        return True

    def guardar(self):
        if self._grabar():
            self.accept()

    def guardar_imprimir(self):
        if self._grabar():
            impresion.vista_previa(self, reports.comprobante(self.s.db, self.s.empresa_id, self.asiento_id))
            self.accept()

    def reject(self):
        if self.modificado and not confirmar(self, "Hay cambios sin guardar. ¿Salir sin grabar?"):
            return
        super().reject()


# ===========================================================================
# Lista de asientos (Asientos() / diálogo BROWSE)
# ===========================================================================
def mantener_asientos(parent, sesion: Sesion):
    db = sesion.db

    def cargar(orden):
        return [(a["id"], [util.fmt_monto(a["numero"]), a["tipo"], util.fmt_fecha(a["fecha"]), a["glosa"],
                           util.fmt_monto(a["debe"]), util.fmt_monto(a["haber"])])
                for a in db.asientos(sesion.periodo_id, orden)]

    def nuevo():
        dlg = AsientoEditor(parent, sesion)
        return dlg.asiento_id if dlg.exec() else None

    def modificar(aid):
        return aid if AsientoEditor(parent, sesion, aid).exec() else None

    def describir(aid):
        a = db.asiento(aid)
        lineas = db.detalle_asiento(aid)
        det = "\n".join(f"   {util.formato_codigo(l['codigo'])}  {db.nombre_cuenta(sesion.empresa_id, l['codigo'])[:28]:28}"
                        f"  D {util.fmt_monto(l['debe']):>12}  H {util.fmt_monto(l['haber']):>12}" for l in lineas)
        return (f"Asiento N° {a['numero']}  ({util.nombre_tipo_asiento(a['tipo'])})  {util.fmt_fecha(a['fecha'])}\n"
                f"{a['glosa']}\n\n{det}\n\nSe eliminarán también sus documentos de compra.")

    def imprimir(aid):
        impresion.vista_previa(parent, reports.comprobante(db, sesion.empresa_id, aid))

    titulo = (f"Mantención Comprobantes de Contabilidad - {sesion.empresa['razon_social']} - Año {sesion.ano}")
    Catalogo(parent, titulo,
             [("Núm.", 70, "R"), ("Tipo", 45, "C"), ("Fecha", 95, "C"), ("Glosa", 0, "L"),
              ("Debe", 120, "R"), ("Haber", 120, "R")],
             cargar, [("Número", "numero"), ("Fecha", "fecha"), ("Tipo", "tipo")],
             nuevo, modificar, db.borrar_asiento, describir,
             extras=[("Imprime &comprobante", "SP_FileDialogContentsView", imprimir)],
             tamano=(980, 620)).exec()
