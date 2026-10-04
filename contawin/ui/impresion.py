"""Impresión de informes con vista previa, PDF y Excel.

Reemplaza PRINT oPrn ... PREVIEW / oPrn:CmSay / EncabezaV / Membrete / HaceLinea
y los REPORT de FiveWin. Dibuja un objeto reports.Informe página por página.
"""
from __future__ import annotations

import datetime as _dt
import os

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QDesktopServices, QFont, QFontMetricsF, QPageLayout, QPageSize, QPainter, QPen
from PySide6.QtCore import QUrl
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QVBoxLayout)

from .. import reports, util
from . import tema
from .comunes import Tabla, error, info

ALINEACION = {"L": Qt.AlignmentFlag.AlignLeft, "R": Qt.AlignmentFlag.AlignRight, "C": Qt.AlignmentFlag.AlignHCenter}


def preparar_impresora(inf: reports.Informe, impresora: QPrinter | None = None) -> QPrinter:
    p = impresora or QPrinter(QPrinter.PrinterMode.HighResolution)
    p.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
    p.setPageOrientation(QPageLayout.Orientation.Landscape if inf.horizontal else QPageLayout.Orientation.Portrait)
    p.setPageMargins(QMarginsF(12, 10, 12, 10), QPageLayout.Unit.Millimeter)
    p.setDocName(inf.titulo)
    return p


def _fuente(puntos: float, negrita: bool = False) -> QFont:
    f = QFont("Arial")
    f.setPointSizeF(puntos)
    f.setBold(negrita)
    return f


class _Dibujante:
    def __init__(self, inf: reports.Informe, painter: QPainter, ancho: float, alto: float):
        self.inf, self.p, self.W, self.H = inf, painter, ancho, alto
        base = 7.5 if inf.horizontal or len(inf.columnas) > 6 else 8.5
        self.f_normal = _fuente(base)
        self.f_bold = _fuente(base, True)
        self.f_titulo = _fuente(base + 4, True)
        self.f_sub = _fuente(base + 1)
        dev = painter.device()
        self.fm = QFontMetricsF(self.f_normal, dev)
        self.fm_bold = QFontMetricsF(self.f_bold, dev)
        self.lh = self.fm.height() * 1.35
        self.pad = self.fm.horizontalAdvance("0") * 0.6
        peso = sum(c.ancho for c in inf.columnas) or 1
        self.xs, x = [], 0.0
        for c in inf.columnas:
            w = self.W * c.ancho / peso
            self.xs.append((x, w))
            x += w
        self.pagina = 0
        self.ahora = _dt.datetime.now()

    # --------------------------------------------------------------- utilidades
    def texto(self, x, y, w, t, fuente=None, alinear="L", alto=None):
        f = fuente or self.f_normal
        self.p.setFont(f)
        fm = QFontMetricsF(f, self.p.device())
        t = fm.elidedText(str(t), Qt.TextElideMode.ElideRight, max(1.0, w))
        self.p.drawText(QRectF(x, y, w, alto or self.lh), ALINEACION[alinear] | Qt.AlignmentFlag.AlignVCenter, t)

    def linea(self, y, x1=0.0, x2=None, grosor=1.0):
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidthF(max(1.0, self.p.device().logicalDpiY() / 150 * grosor))
        self.p.setPen(pen)
        self.p.drawLine(int(x1), int(y), int(self.W if x2 is None else x2), int(y))

    # --------------------------------------------------------------- partes de página
    def encabezado(self) -> float:
        inf = self.inf
        self.pagina += 1
        y = 0.0
        # Membrete (empresa) a la izquierda, fecha y página a la derecha (EncabezaV)
        ancho_der = self.W * 0.28
        fecha = inf.fecha_emision or self.ahora.date()
        derecha = [f"Fecha : {util.fmt_fecha(fecha)}   {self.ahora:%H:%M}", f"Página: {self.pagina}"]
        filas = max(len(inf.membrete), len(derecha))
        for i in range(filas):
            if i < len(inf.membrete):
                self.texto(0, y, self.W - ancho_der, inf.membrete[i], self.f_bold)
            if i < len(derecha):
                self.texto(self.W - ancho_der, y, ancho_der, derecha[i], self.f_bold, "R")
            y += self.lh
        y += self.lh * 0.4
        fm_t = QFontMetricsF(self.f_titulo, self.p.device())
        self.texto(0, y, self.W, inf.titulo, self.f_titulo, "C", fm_t.height() * 1.2)
        y += fm_t.height() * 1.3
        for s in inf.subtitulos:
            self.texto(0, y, self.W, s, self.f_sub, "C")
            y += self.lh
        for s in inf.datos_cabecera:
            self.texto(0, y, self.W, s, self.f_bold)
            y += self.lh
        y += self.lh * 0.3
        self.linea(y, grosor=1.5)
        for i, c in enumerate(inf.columnas):
            x, w = self.xs[i]
            self.texto(x + self.pad, y, w - 2 * self.pad, c.titulo, self.f_bold, c.alineacion)
        y += self.lh
        self.linea(y, grosor=1.5)
        return y + self.lh * 0.2

    def fila(self, y, fila: reports.Fila) -> float:
        inf = self.inf
        if fila.estilo == reports.GRUPO:
            y += self.lh * 0.25
            self.texto(self.pad, y, self.W - self.pad, fila.texto, self.f_bold)
            return y + self.lh
        fuente = self.f_bold if fila.estilo in (reports.TOTAL, reports.SUBTOTAL, reports.ENCABEZADO_ASIENTO) \
            else self.f_normal
        if fila.estilo == reports.TOTAL:
            self.linea(y)
        for i, t in enumerate(inf.textos(fila)):
            if t:
                x, w = self.xs[i]
                self.texto(x + self.pad, y, w - 2 * self.pad, t, fuente, inf.columnas[i].alineacion)
        y += self.lh
        if fila.estilo == reports.TOTAL:
            self.linea(y)
        return y

    def total_pagina(self, y, sumas: dict[int, int]):
        self.linea(y)
        cols = [i for i in self.inf.totales_pagina]
        self.texto(self.pad, y, self.xs[cols[0]][0] - 2 * self.pad, "TOTAL PÁGINA .......", self.f_bold, "R")
        for i in cols:
            x, w = self.xs[i]
            self.texto(x + self.pad, y, w - 2 * self.pad, util.fmt_monto(sumas.get(i, 0)), self.f_bold, "R")

    # --------------------------------------------------------------- documento completo
    def dibujar(self, impresora: QPrinter):
        inf = self.inf
        reserva = self.lh * 1.6 if inf.totales_pagina else 0
        limite = self.H - reserva
        y = self.encabezado()
        sumas: dict[int, int] = {}
        for fila in inf.filas:
            alto = self.lh * (1.25 if fila.estilo == reports.GRUPO else 1)
            if y + alto > limite:
                if inf.totales_pagina:
                    self.total_pagina(y + self.lh * 0.3, sumas)
                    sumas = {}
                impresora.newPage()
                y = self.encabezado()
            if inf.totales_pagina and fila.estilo != reports.TOTAL:
                for i in inf.totales_pagina:
                    v = fila.valores[i] if i < len(fila.valores) else None
                    if isinstance(v, (int, float)):
                        sumas[i] = sumas.get(i, 0) + int(v)
            y = self.fila(y, fila)
        if inf.totales_pagina and sumas:
            if y + self.lh * 1.5 > self.H:
                impresora.newPage()
                y = self.encabezado()
            self.total_pagina(y + self.lh * 0.3, sumas)
            y += self.lh * 1.5
        # Pie (detalle, Art. 100, etc.)
        if inf.pie:
            y += self.lh * 0.6
            for t in inf.pie:
                if y + self.lh > self.H:
                    impresora.newPage()
                    y = self.encabezado()
                self.texto(0, y, self.W, t, self.f_normal)
                y += self.lh
        # Firmas
        if inf.firmas:
            alto_firmas = self.lh * 5
            if y + alto_firmas > self.H:
                impresora.newPage()
                y = self.encabezado()
            y += self.lh * 3.5
            n = len(inf.firmas)
            ancho = self.W / n
            for i, t in enumerate(inf.firmas):
                x1 = ancho * i + ancho * 0.12
                x2 = ancho * (i + 1) - ancho * 0.12
                self.linea(y, x1, x2)
                self.texto(x1, y + self.lh * 0.1, x2 - x1, t, self.f_bold, "C")


def dibujar_informe(inf: reports.Informe, impresora: QPrinter):
    painter = QPainter()
    if not painter.begin(impresora):
        return False
    try:
        r = impresora.pageLayout().paintRectPixels(impresora.resolution())
        _Dibujante(inf, painter, float(r.width()), float(r.height())).dibujar(impresora)
    finally:
        painter.end()
    return True


def vista_previa(parent, inf: reports.Informe):
    impresora = preparar_impresora(inf)
    dlg = QPrintPreviewDialog(impresora, parent)
    dlg.setWindowTitle(f"Vista previa - {inf.titulo}")
    dlg.paintRequested.connect(lambda p: dibujar_informe(inf, p))
    dlg.resize(1100, 800)
    dlg.exec()


def imprimir(parent, inf: reports.Informe):
    impresora = preparar_impresora(inf)
    dlg = QPrintDialog(impresora, parent)
    if dlg.exec():
        dibujar_informe(inf, impresora)


def guardar_pdf(parent, inf: reports.Informe, carpeta: str = "") -> str | None:
    sugerido = os.path.join(carpeta or os.path.expanduser("~"), f"{inf.nombre_archivo}.pdf")
    ruta, _ = QFileDialog.getSaveFileName(parent, "Guardar PDF", sugerido, "PDF (*.pdf)")
    if not ruta:
        return None
    if not ruta.lower().endswith(".pdf"):
        ruta += ".pdf"
    impresora = preparar_impresora(inf)
    impresora.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    impresora.setOutputFileName(ruta)
    if dibujar_informe(inf, impresora):
        QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))
        return ruta
    error(parent, "No se pudo generar el PDF.")
    return None


def guardar_excel(parent, inf: reports.Informe, carpeta: str = "") -> str | None:
    sugerido = os.path.join(carpeta or os.path.expanduser("~"), f"{inf.nombre_archivo}.xlsx")
    ruta, _ = QFileDialog.getSaveFileName(parent, "Traspasar a Excel", sugerido,
                                          "Excel (*.xlsx);;CSV separado por ; (*.csv)")
    if not ruta:
        return None
    if not ruta.lower().endswith((".xlsx", ".csv")):
        ruta += ".xlsx"
    try:
        final = reports.exportar_excel(inf, ruta)
    except PermissionError:
        error(parent, "No se pudo guardar: el archivo está abierto en otro programa.")
        return None
    if final != ruta:
        info(parent, "No está instalado 'openpyxl', se generó un archivo CSV que Excel puede abrir:\n" + final)
    QDesktopServices.openUrl(QUrl.fromLocalFile(final))
    return final


class VisorInforme(QDialog):
    """Consulta en pantalla + Vista previa / Imprimir / PDF / Excel."""

    def __init__(self, parent, inf: reports.Informe):
        super().__init__(parent)
        self.inf = inf
        self.setWindowTitle(inf.titulo)
        self.resize(1150 if inf.horizontal else 950, 650)
        lay = tema.margenes(QVBoxLayout(self))
        lay.addWidget(tema.etiqueta(inf.titulo, "titulo"))
        sub = "  ·  ".join(t for t in (inf.subtitulos + inf.membrete[:1]) if t)
        if sub:
            lay.addWidget(tema.etiqueta(sub, "secundario"))
        cols = [(c.titulo, 0 if c.ancho >= 2 else int(70 * c.ancho + 30), c.alineacion) for c in inf.columnas]
        self.tabla = Tabla(cols, self)
        filas, estilos = [], []
        for f in inf.filas:
            if f.estilo == reports.GRUPO:
                filas.append([f.texto] + [""] * (len(inf.columnas) - 1))
            else:
                filas.append(inf.textos(f))
            estilos.append(f.estilo)
        self.tabla.cargar(filas, estilos=estilos)
        for r, f in enumerate(inf.filas):
            if f.estilo == reports.GRUPO:
                self.tabla.setSpan(r, 0, 1, len(inf.columnas))
        lay.addWidget(self.tabla, 1)
        if inf.pie:
            lay.addWidget(tema.etiqueta("\n".join(inf.pie), "ayuda"))
        bot = QHBoxLayout()
        bot.setSpacing(tema.ESPACIO[2])
        for texto, ic, accion, variante in [("Vista previa e imprimir", "imprimir", self._previa, "primario"),
                                            ("Guardar PDF", "guardar", self._pdf, "secundario"),
                                            ("Exportar a Excel", "excel", self._excel, "secundario")]:
            b = tema.boton(texto, ic, variante)
            b.setAutoDefault(False)
            b.clicked.connect(accion)
            bot.addWidget(b)
        bot.addStretch()
        cerrar = tema.boton("Cerrar", "cerrar")
        cerrar.setAutoDefault(False)
        cerrar.clicked.connect(self.accept)
        bot.addWidget(cerrar)
        lay.addLayout(bot)

    def _previa(self):
        vista_previa(self, self.inf)

    def _pdf(self):
        guardar_pdf(self, self.inf)

    def _excel(self):
        guardar_excel(self, self.inf)


def mostrar(parent, inf: reports.Informe):
    if not any(f.estilo in (reports.NORMAL, reports.ENCABEZADO_ASIENTO) for f in inf.filas):
        info(parent, "No existen datos en este período.")
        return
    VisorInforme(parent, inf).exec()
