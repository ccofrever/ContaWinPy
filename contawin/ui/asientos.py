"""Asientos contables (ASIENTOS.PRG): mantención de comprobantes, detalle de
cuentas y documentos de compra (DLG_ASIENTOS, DLG_DETALLE, DOCCOMPRA)."""
from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QKeySequence, QRegularExpressionValidator, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QVBoxLayout)

from .. import reports, util
from ..db import ErrorDatos
from . import impresion, tema
from .calculadora import Calculadora
from .catalogo import Catalogo
from .comunes import (Buscador, CodigoCuentaEdit, FechaEdit, MontoEdit, Sesion, Tabla, confirmar,
                      error, info)
from .mantenedores import FormCuenta, nuevo_proveedor


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
        self.setWindowTitle("Documento de compra")
        self.setMinimumWidth(640)
        doc = dict(doc or {})
        total = debe if debe else haber
        lay = tema.margenes(QVBoxLayout(self))
        lay.addWidget(tema.etiqueta("Documento de compra", "titulo"))

        g1 = tema.tarjeta()
        f1 = QGridLayout(g1)
        f1.setContentsMargins(*[tema.ESPACIO[4]] * 4)
        f1.setHorizontalSpacing(tema.ESPACIO[2])
        nombre = sesion.db.nombre_cuenta(sesion.empresa_id, codigo)
        for col, (et, val) in enumerate([("Cuenta", f"{util.formato_codigo(codigo)}  {nombre}"),
                                         ("Debe", util.fmt_monto(debe)), ("Haber", util.fmt_monto(haber))]):
            f1.addWidget(tema.etiqueta(et, "etiqueta"), 0, col * 2)
            e = QLineEdit(val)
            e.setReadOnly(True)
            if col:
                e.setProperty("cifra", True)
                e.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            f1.addWidget(e, 0, col * 2 + 1)
        lay.addWidget(g1)

        form = tema.formulario(QFormLayout())
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
        b_nuevo = tema.boton("Nuevo proveedor…", "mas")
        b_nuevo.setAutoDefault(False)
        b_nuevo.setToolTip("Crear un proveedor nuevo")
        b_nuevo.clicked.connect(self._nuevo_proveedor)
        fila_prov.addWidget(self.proveedor, 1)
        fila_prov.addWidget(b_nuevo)

        self.neto = MontoEdit(valor=doc.get("neto", 0))
        self.iva = MontoEdit(valor=doc.get("iva", 0))
        self.total = MontoEdit(valor=total)
        self.total.setReadOnly(True)
        fila_montos = QHBoxLayout()
        fila_montos.setSpacing(tema.ESPACIO[2])
        for et, w in [("Neto", self.neto), ("IVA", self.iva), ("Total", self.total)]:
            fila_montos.addWidget(tema.etiqueta(et, "etiqueta"))
            fila_montos.addWidget(w)
        b_calc = tema.boton("Calcular IVA")
        b_calc.setAutoDefault(False)
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

        form.addRow("Tipo de documento", self.tipo)
        form.addRow("N° de documento", self.numero)
        form.addRow("Fecha del documento", self.fecha)
        form.addRow("Proveedor", fila_prov)
        form.addRow("Montos", fila_montos)
        form.addRow("Detalle", self.detalle)
        form.addRow("Fecha de pago", fila_pago)
        lay.addLayout(form)
        self.cdcosto = cdcosto

        bb = tema.botones_dialogo("Aceptar", "Cancelar")
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
            error(self, "Ingresa el número de documento.")
            self.numero.setFocus()
            return
        rut = self.proveedor.codigo()
        if not rut:
            error(self, "Selecciona un proveedor existente o créalo con «Nuevo proveedor…».")
            self.proveedor.setFocus()
            return
        if not self.detalle.text().strip():
            error(self, "Ingresa el detalle del documento.")
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
class SelectorCuenta(QDialog):
    """Búsqueda de una cuenta por código o nombre (F2 o «Buscar…» en la línea del comprobante)."""

    def __init__(self, parent, cuentas: list, texto: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Buscar cuenta")
        self.resize(620, 480)
        self.codigo: str | None = None
        lay = tema.margenes(QVBoxLayout(self))
        lay.addWidget(tema.etiqueta("Buscar cuenta", "titulo"))
        self.buscar = QLineEdit(texto)
        self.buscar.setPlaceholderText("Escribe parte del código o del nombre")
        self.buscar.setClearButtonEnabled(True)
        self.buscar.addAction(tema.icono("buscar"), QLineEdit.ActionPosition.LeadingPosition)
        lay.addWidget(self.buscar)
        self.tabla = Tabla([("Código", 100, "L"), ("Nombre", 0, "L")], self)
        self.tabla.cargar([[util.formato_codigo(c["codigo"]), c["nombre"]] for c in cuentas],
                          [c["codigo"] for c in cuentas])
        self.tabla.doubleClicked.connect(lambda _: self._aceptar())
        lay.addWidget(self.tabla, 1)
        bb = tema.botones_dialogo("Elegir", "Cancelar")
        bb.accepted.connect(self._aceptar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.buscar.textChanged.connect(self._filtrar)
        self.buscar.returnPressed.connect(self._aceptar)
        atajo = QShortcut(QKeySequence(Qt.Key.Key_Down), self.buscar)
        atajo.setContext(Qt.ShortcutContext.WidgetShortcut)
        atajo.activated.connect(self.tabla.setFocus)
        self._filtrar(texto)
        self.buscar.setFocus()

    def _filtrar(self, texto: str):
        self.tabla.filtrar(texto)
        # deja marcada la primera cuenta visible, para elegirla con Enter
        if self.tabla.dato_actual() is None or self.tabla.isRowHidden(self.tabla.currentRow()):
            for r in range(self.tabla.rowCount()):
                if not self.tabla.isRowHidden(r):
                    self.tabla.selectRow(r)
                    break

    def _aceptar(self):
        r = self.tabla.currentRow()
        if r < 0 or self.tabla.isRowHidden(r):
            return
        self.codigo = self.tabla.dato_actual()
        self.accept()


class LineaDialog(QDialog):
    """Cuenta + monto en el Debe o en el Haber. El código se escribe con la máscara 99.99.99 (igual
    que al crear la cuenta) y el nombre aparece al lado; F2 o «Buscar…» busca por nombre. El cursor
    parte en la cuenta y Enter avanza Cuenta → Debe → Haber → Aceptar. Si la cuenta no existe,
    ofrece crearla."""

    def __init__(self, parent, sesion: Sesion, cuentas: list, linea: dict | None,
                 cdcosto: str, fecha_asiento: _dt.date):
        super().__init__(parent)
        self.s, self.cdcosto, self.fecha_asiento = sesion, cdcosto, fecha_asiento
        self.cuentas = {c["codigo"]: c for c in cuentas}
        self.cuenta_creada = False          # el editor recarga el plan de cuentas si se creó una
        self.linea_original = linea or {}
        self.setWindowTitle("Línea del comprobante")
        self.setMinimumWidth(620)
        lay = tema.margenes(QVBoxLayout(self))
        lay.addWidget(tema.etiqueta("Modificar línea" if linea else "Nueva línea", "titulo"))
        form = tema.formulario(QFormLayout())

        self.cuenta = CodigoCuentaEdit()
        self.cuenta.setFixedWidth(120)
        self.cuenta.setToolTip("Código de la cuenta · F2 para buscarla por nombre")
        self.cuenta.set_codigo(self.linea_original.get("codigo") or "")
        self.nombre_cuenta = QLineEdit()
        self.nombre_cuenta.setReadOnly(True)
        self.nombre_cuenta.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        fila_cuenta = QHBoxLayout()
        fila_cuenta.setSpacing(tema.ESPACIO[2])
        fila_cuenta.addWidget(self.cuenta)
        fila_cuenta.addWidget(self.nombre_cuenta, 1)
        b_buscar = tema.boton("Buscar…", "buscar")
        b_buscar.setToolTip("Buscar la cuenta por nombre (F2)")
        b_buscar.clicked.connect(self._buscar)
        b_nueva = tema.boton("Nueva cuenta…", "mas")
        b_nueva.setToolTip("Agregar una cuenta al plan de cuentas")
        b_nueva.clicked.connect(self._boton_nueva)
        for b in (b_buscar, b_nueva):
            b.setAutoDefault(False)
            b.setFocusPolicy(Qt.FocusPolicy.ClickFocus)    # Tab va de la cuenta directo al Debe
            fila_cuenta.addWidget(b)
        form.addRow("Cuenta", fila_cuenta)
        self.aviso_doc = QLabel("")
        tema.marcar(self.aviso_doc, estado="aviso")
        form.addRow(self.aviso_doc)

        # línea nueva: Debe y Haber vacíos, sin proponer montos
        self.debe = MontoEdit(valor=self.linea_original.get("debe", 0))
        self.haber = MontoEdit(valor=self.linea_original.get("haber", 0))
        for w in (self.debe, self.haber):
            if not w.valor():
                w.clear()
        # el monto va en el Debe o en el Haber: al escribir en uno, el otro queda en cero
        self.debe.textEdited.connect(lambda _: self._exclusivo(self.debe, self.haber))
        self.haber.textEdited.connect(lambda _: self._exclusivo(self.haber, self.debe))
        # calculadora: sugiere poner el resultado en el campo (Debe o Haber) donde estaba el cursor
        self._campo_monto = self.debe
        for w in (self.debe, self.haber):
            w.installEventFilter(self)
        montos = QHBoxLayout()
        montos.setSpacing(tema.ESPACIO[4])
        for et, w in [("Debe", self.debe), ("Haber", self.haber)]:
            col = QVBoxLayout()
            col.setSpacing(tema.ESPACIO[2])
            col.addWidget(tema.etiqueta(et, "etiqueta"))
            col.addWidget(w)
            montos.addLayout(col)
        col = QVBoxLayout()
        col.setSpacing(tema.ESPACIO[2])
        col.addWidget(tema.etiqueta(" ", "etiqueta"))
        b_calc = tema.boton("Calculadora", "calculadora")
        b_calc.setAutoDefault(False)
        b_calc.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        b_calc.setToolTip("Calcular el monto (F4); el resultado va al Debe o al Haber")
        b_calc.clicked.connect(self.calculadora)
        col.addWidget(b_calc)
        montos.addLayout(col)
        form.addRow(montos)
        lay.addLayout(form)
        lay.addWidget(tema.etiqueta("Una línea lleva monto en el Debe o en el Haber: al escribir en uno, "
                                    "el otro queda en cero. Enter avanza al campo siguiente · "
                                    "F2 busca la cuenta · F4 abre la calculadora.", "ayuda"))
        # botones propios sin «default»: Enter avanza entre campos en vez de aceptar a medias
        botones = QHBoxLayout()
        botones.addStretch()
        b_cancelar = tema.boton("Cancelar")
        b_cancelar.clicked.connect(self.reject)
        b_aceptar = tema.boton("Aceptar", variante="primario")
        b_aceptar.clicked.connect(self._aceptar)
        for b in (b_cancelar, b_aceptar):
            b.setAutoDefault(False)
            botones.addWidget(b)
        lay.addLayout(botones)

        self.cuenta.textChanged.connect(lambda _: self._mostrar_cuenta())
        self.cuenta.returnPressed.connect(self._enter_cuenta)
        atajo = QShortcut(QKeySequence(Qt.Key.Key_F2), self)
        atajo.activated.connect(self._buscar)
        QShortcut(QKeySequence(Qt.Key.Key_F4), self).activated.connect(self.calculadora)
        self.debe.returnPressed.connect(lambda: self._aceptar() if self.debe.valor() else self.haber.setFocus())
        self.haber.returnPressed.connect(self._aceptar)
        self._mostrar_cuenta()
        self.linea: dict | None = None
        self.cuenta.setFocus()

    def showEvent(self, evento):
        super().showEvent(evento)
        # el cursor siempre parte en la cuenta (también al abrir otra línea seguida)
        QTimer.singleShot(0, self._enfocar_cuenta)

    def _enfocar_cuenta(self):
        self.cuenta.setFocus()
        if self.cuenta.codigo():
            self.cuenta.selectAll()
        else:
            self.cuenta.setCursorPosition(0)

    # ------------------------------------------------------------------ cuenta
    def _codigo_escrito(self) -> str:
        return self.cuenta.codigo()

    def _codigo_valido(self) -> str | None:
        """Código escrito si existe en el plan de cuentas; si no, None."""
        cod = self._codigo_escrito()
        return cod if cod in self.cuentas else None

    def _mostrar_cuenta(self):
        cod = self._codigo_escrito()
        c = self.cuentas.get(cod)
        if c:
            self.nombre_cuenta.setText(c["nombre"])
            tema.marcar(self.nombre_cuenta, error=False)
        else:
            self.nombre_cuenta.setText("La cuenta no existe" if len(cod) == 6 else "")
            tema.marcar(self.nombre_cuenta, error=len(cod) == 6)
        pide = bool(c and c["cdocum"])
        self.aviso_doc.setText("⚠ Esta cuenta pide documento de compra al aceptar." if pide else "")
        self.aviso_doc.setVisible(pide)

    def _poner_cuenta(self, codigo: str):
        self.cuenta.set_codigo(codigo)
        self._mostrar_cuenta()
        self.debe.setFocus()
        self.debe.selectAll()

    def _buscar(self):
        dlg = SelectorCuenta(self, list(self.cuentas.values()))
        if dlg.exec() and dlg.codigo:
            self._poner_cuenta(dlg.codigo)
        else:
            self.cuenta.setFocus()

    def _enter_cuenta(self):
        cod = self._codigo_escrito()
        if not cod:                        # sin código: abre la búsqueda por nombre
            self._buscar()
        elif self._codigo_valido():
            self.debe.setFocus()
            self.debe.selectAll()
        elif len(cod) == 6:
            self._ofrecer_crear(cod)
        else:
            error(self, "Completa el código de la cuenta (99.99.99) o búscala con F2.")
            self.cuenta.setFocus()

    def _ofrecer_crear(self, cod: str) -> bool:
        if not confirmar(self, f"La cuenta {util.formato_codigo(cod)} no existe en el plan de cuentas.\n\n"
                               "¿Quieres crearla ahora?"):
            self.cuenta.setFocus()
            return False
        return self._crear_cuenta(cod)

    def _boton_nueva(self):
        # siempre en blanco; sólo propone el código si se escribió uno completo que todavía no existe
        cod = self._codigo_escrito()
        self._crear_cuenta(cod if len(cod) == 6 and not self._codigo_valido() else "")

    def _crear_cuenta(self, cod: str = "") -> bool:
        """Abre el formulario de cuenta nueva (con el código propuesto, si hay). Al guardarla queda
        puesta en la línea."""
        f = FormCuenta(self, self.s, propuesta=dict(codigo=cod) if cod else None)
        if not f.exec() or not f.cod_guardado:
            self.cuenta.setFocus()
            return False
        self.cuentas = {c["codigo"]: c for c in self.s.db.cuentas(self.s.empresa_id)}
        self.cuenta_creada = True
        self._poner_cuenta(f.cod_guardado)
        return True

    # ------------------------------------------------------------------ montos
    def eventFilter(self, obj, evento):
        if evento.type() == QEvent.Type.FocusIn and obj in (self.debe, self.haber):
            self._campo_monto = obj
        return super().eventFilter(obj, evento)

    def calculadora(self):
        campo = self._campo_monto
        destino = "haber" if campo is self.haber else "debe"
        dlg = Calculadora(self, campo.valor(), destino)
        if not dlg.exec() or dlg.resultado is None:
            campo.setFocus()
            return
        poner, otro = (self.debe, self.haber) if dlg.destino == "debe" else (self.haber, self.debe)
        poner.set_valor(dlg.resultado)
        otro.clear()                       # Debe y Haber son excluyentes
        poner.setFocus()
        poner.selectAll()

    @staticmethod
    def _exclusivo(escrito: MontoEdit, otro: MontoEdit):
        if escrito.valor() and otro.valor():
            otro.clear()

    def _aceptar(self):
        cod = self._codigo_escrito()
        if cod and not self._codigo_valido() and len(cod) == 6:
            if not self._ofrecer_crear(cod):
                return
        codigo = self._codigo_valido()
        if not codigo:
            error(self, "Ingresa el código de una cuenta del plan de cuentas (F2 para buscarla) "
                        "o créala con «Nueva cuenta…».")
            self.cuenta.setFocus()
            return
        c = self.cuentas[codigo]
        debe, haber = self.debe.valor(), self.haber.valor()
        if debe < 0 or haber < 0:
            error(self, "Los montos no pueden ser negativos.")
            return
        if debe == 0 and haber == 0:
            error(self, "Ingresa un monto en el Debe o en el Haber.")
            self.debe.setFocus()
            return
        if debe and haber:
            error(self, "Ingresa el monto en el Debe o en el Haber, no en ambos.")
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
        self.setWindowTitle("Modificar comprobante" if asiento_id else "Nuevo comprobante")
        self.resize(980, 660)

        lay = tema.margenes(QVBoxLayout(self))
        # el número de un comprobante nuevo se genera al guardarlo (el siguiente del año en ese momento)
        titulo = QHBoxLayout()
        titulo.setSpacing(tema.ESPACIO[3])
        self.lbl_numero = tema.etiqueta(f"Comprobante N° {util.fmt_monto(a['numero'])}" if asiento_id
                                        else "Comprobante nuevo", "titulo")
        titulo.addWidget(self.lbl_numero)
        chip = QLabel("Modificando" if asiento_id else "N° se asigna al guardar")
        tema.marcar(chip, chip=True)
        titulo.addWidget(chip)
        titulo.addStretch()
        titulo.addWidget(tema.etiqueta(f"{sesion.empresa['razon_social']} · Año {sesion.ano}"
                                       if sesion.empresa else "", "secundario"))
        lay.addLayout(titulo)
        cab = tema.tarjeta()
        g = QGridLayout(cab)
        g.setContentsMargins(*[tema.ESPACIO[4]] * 4)
        g.setHorizontalSpacing(tema.ESPACIO[4])
        g.setVerticalSpacing(tema.ESPACIO[2])
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
        # etiquetas arriba de cada campo
        for col, (et, w, ancho) in enumerate([("Tipo", self.tipo, 1), ("Fecha", self.fecha, 1),
                                              ("Centro de costo", self.ccosto, 2)]):
            g.addWidget(tema.etiqueta(et, "etiqueta"), 0, [0, 1, 2][col], 1, ancho if col == 2 else 1)
            g.addWidget(w, 1, [0, 1, 2][col], 1, ancho if col == 2 else 1)
        g.addWidget(tema.etiqueta("Glosa", "etiqueta"), 2, 0, 1, 4)
        g.addWidget(self.glosa, 3, 0, 1, 4)
        g.setColumnStretch(2, 1)
        g.setColumnStretch(3, 1)
        lay.addWidget(cab)
        for w in (self.tipo, self.ccosto):
            w.currentIndexChanged.connect(self._marcar)
        self.glosa.textEdited.connect(self._marcar)
        self.fecha.dateChanged.connect(self._marcar)

        self.tabla = Tabla([("Código", 100, "L"), ("Cuenta", 0, "L"), ("Debe", 140, "R"),
                            ("Haber", 140, "R"), ("Documento", 190, "L")], self)
        self.tabla.doubleClicked.connect(lambda _: self.modificar_linea())
        lay.addWidget(self.tabla, 1)

        # fila de totales, fija al pie de la tabla, con estado cuadrado / descuadrado
        fila = QHBoxLayout()
        fila.setSpacing(tema.ESPACIO[2])
        for texto, ic, acc, ayuda in [("Nueva línea", "mas", self.nueva_linea, "Insert"),
                                      ("Modificar", "editar", self.modificar_linea, "Enter o doble clic"),
                                      ("Borrar", "borrar", self.borrar_linea, "Supr")]:
            b = tema.boton(texto, ic)
            b.setAutoDefault(False)
            b.setToolTip(ayuda)
            b.clicked.connect(acc)
            fila.addWidget(b)
        fila.addStretch()
        self.lbl_dif = QLabel()
        fila.addWidget(self.lbl_dif)
        fila.addSpacing(tema.ESPACIO[3])
        self.tot_debe = QLineEdit()
        self.tot_haber = QLineEdit()
        for w in (self.tot_debe, self.tot_haber):
            w.setReadOnly(True)
            w.setProperty("cifra", True)
            w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            w.setFixedWidth(150)
        fila.addWidget(tema.etiqueta("Totales", "etiqueta"))
        fila.addWidget(self.tot_debe)
        fila.addWidget(self.tot_haber)
        lay.addLayout(fila)

        bot = QHBoxLayout()
        bot.setSpacing(tema.ESPACIO[2])
        bot.addWidget(tema.etiqueta("Ctrl+S guarda · Insert agrega línea · Supr borra línea", "ayuda"))
        bot.addStretch()
        self.botones_guardar = []
        for texto, ic, acc, variante in [("&Cerrar", "cerrar", self.reject, "secundario"),
                                         ("Guardar e &imprimir", "imprimir", self.guardar_imprimir, "secundario"),
                                         ("&Guardar comprobante", "guardar", self.guardar, "primario")]:
            b = tema.boton(texto, ic, variante)
            b.setAutoDefault(False)
            b.clicked.connect(acc)
            bot.addWidget(b)
            if acc != self.reject:
                self.botones_guardar.append(b)
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
        """Fecha del último comprobante ingresado: el guardado en esta sesión y, si no hay, el de
        número más alto del año; sin comprobantes, hoy (o el 1 de enero si es otro año)."""
        ultima = self.s.ultima_fecha.get(self.s.periodo_id)
        if ultima:
            return ultima
        r = self.s.db.q1("SELECT fecha FROM asiento WHERE periodo_id=? AND fecha IS NOT NULL "
                         "ORDER BY numero DESC LIMIT 1", (self.s.periodo_id,))
        if r and r["fecha"]:
            return util.from_iso(r["fecha"])
        hoy = _dt.date.today()
        ano = self.s.ano or hoy.year
        return hoy if hoy.year == ano else _dt.date(ano, 1, 1)

    def _marcar(self, *_):
        self.modificado = True

    def _totales(self) -> tuple[int, int]:
        return sum(l["debe"] for l in self.lineas), sum(l["haber"] for l in self.lineas)

    def _refrescar(self, seleccionar: int | dict | None = None):
        """seleccionar: índice de fila o la línea (dict) que debe quedar marcada tras ordenar."""
        self.lineas.sort(key=util.orden_linea)       # Debe primero, luego Haber; por código de cuenta
        if isinstance(seleccionar, dict):
            seleccionar = next((i for i, l in enumerate(self.lineas) if l is seleccionar), None)
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
        self.tot_debe.setText(util.fmt_pesos(td))
        self.tot_haber.setText(util.fmt_pesos(th))
        # sólo se puede guardar un comprobante con líneas y cuadrado
        for b in getattr(self, "botones_guardar", []):
            b.setEnabled(self._cuadrado())
            b.setToolTip("" if self._cuadrado() else "El comprobante debe estar cuadrado para guardarlo")
        if td == th:
            self.lbl_dif.setText("✓ Cuadrado" if td else "")
            tema.marcar(self.lbl_dif, estado="ok")
        else:
            self.lbl_dif.setText(f"⚠ Descuadrado · Diferencia {util.fmt_pesos(abs(td - th))} "
                                 f"en el {'Debe' if td > th else 'Haber'}")
            tema.marcar(self.lbl_dif, estado="error")

    def _cuadrado(self) -> bool:
        td, th = self._totales()
        return bool(self.lineas) and td == th

    def _cdcosto(self) -> str:
        return self.ccosto.codigo() or ""

    def _recargar_cuentas(self, dlg: LineaDialog):
        if dlg.cuenta_creada:
            self.cuentas = self.s.db.cuentas(self.s.empresa_id)
            self.nombres = {c["codigo"]: c["nombre"] for c in self.cuentas}

    def nueva_linea(self):
        dlg = LineaDialog(self, self.s, self.cuentas, None, self._cdcosto(), self.fecha.fecha())
        ok = dlg.exec()
        self._recargar_cuentas(dlg)
        if ok and dlg.linea:
            self.lineas.append(dlg.linea)
            self.modificado = True
            self._refrescar(dlg.linea)

    def modificar_linea(self):
        i = self.tabla.dato_actual()
        if i is None:
            return
        dlg = LineaDialog(self, self.s, self.cuentas, self.lineas[i], self._cdcosto(), self.fecha.fecha())
        ok = dlg.exec()
        self._recargar_cuentas(dlg)
        if ok and dlg.linea:
            self.lineas[i] = dlg.linea
            self.modificado = True
            self._refrescar(dlg.linea)

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
        if not self.lineas:
            error(self, "El comprobante no tiene líneas. Agrega las cuentas con «Nueva línea» (Insert).")
            return False
        td, th = self._totales()
        if td != th:
            error(self, f"Las sumas del comprobante no están cuadradas: diferencia {util.fmt_pesos(abs(td - th))} "
                        f"en el {'Debe' if td > th else 'Haber'}.\n\nSólo se puede guardar un comprobante cuadrado.")
            return False
        fecha = self.fecha.fecha()
        if self.s.ano and fecha.year != self.s.ano:
            if not confirmar(self, f"La fecha {util.fmt_fecha(fecha)} no corresponde al año de trabajo "
                                   f"({self.s.ano}).\n¿Guardar de todas formas?"):
                return False
        cab = dict(tipo=self.tipo.currentData(), fecha=fecha, glosa=self.glosa.text(), cdcosto=self._cdcosto())
        # el centro de costo de la cabecera se propaga a los documentos de compra (como el original)
        for l in self.lineas:
            if l.get("documento"):
                l["documento"]["cdcosto"] = cab["cdcosto"]
        nuevo = self.asiento_id is None
        try:
            self.asiento_id = self.s.db.guardar_asiento(self.s.periodo_id, cab, self.lineas, self.asiento_id)
        except ErrorDatos as e:
            error(self, str(e))
            return False
        self.numero = self.s.db.asiento(self.asiento_id)["numero"]
        if nuevo:                              # el siguiente comprobante parte con esta fecha
            self.s.ultima_fecha[self.s.periodo_id] = fecha
        self.lbl_numero.setText(f"Comprobante N° {util.fmt_monto(self.numero)}")
        self.nuevo_guardado = nuevo
        self.modificado = False
        return True

    def guardar(self):
        if self._grabar():
            if self.nuevo_guardado:
                info(self, f"Se guardó el comprobante N° {util.fmt_monto(self.numero)}.", "Comprobante guardado")
            self.accept()

    def guardar_imprimir(self):
        if self._grabar():
            impresion.vista_previa(self, reports.comprobante(self.s.db, self.s.empresa_id, self.asiento_id))
            self.accept()

    def reject(self):
        if self.modificado and not confirmar(self, "Hay cambios sin guardar. ¿Cerrar sin guardar?"):
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

    titulo = f"Comprobantes - {sesion.empresa['razon_social']} · Año {sesion.ano}"
    Catalogo(parent, titulo,
             [("N°", 70, "R"), ("Tipo", 50, "C"), ("Fecha", 100, "C"), ("Glosa", 0, "L"),
              ("Debe", 140, "R"), ("Haber", 140, "R")],
             cargar, [("Número", "numero"), ("Fecha", "fecha"), ("Tipo", "tipo")],
             nuevo, modificar, db.borrar_asiento, describir,
             extras=[("Imprimir &comprobante", "imprimir", imprimir)],
             tamano=(1040, 660), al_final=True).exec()
