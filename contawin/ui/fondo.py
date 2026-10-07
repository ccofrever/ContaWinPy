"""Imagen de fondo del área de trabajo y la utilidad para elegirla (Útiles ▸ Imagen de fondo)."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QSlider,
                               QSpinBox, QStyle, QStyleOption, QVBoxLayout, QWidget)

from ..config import Config, carpeta_programa
from . import tema
from .comunes import error

MODOS = [("tamano", "Tamaño elegido (centrada)"),
         ("llenar", "Llenar el área (recorta los bordes)"),
         ("ajustar", "Ajustar al área (imagen completa)"),
         ("mosaico", "Mosaico (repetida)"),
         ("ninguno", "Sin imagen")]

FILTRO = "Imágenes (*.bmp *.png *.jpg *.jpeg *.gif *.webp);;Todos los archivos (*)"


class Lienzo(QWidget):
    """Área de trabajo que dibuja la imagen de fondo según el modo y la escala elegidos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("lienzo")
        self._imagen = QPixmap()
        self.modo, self.escala = "ninguno", 100
        self._escalada, self._clave = QPixmap(), None

    def set_fondo(self, ruta: str, modo: str, escala: int):
        self._imagen = QPixmap(ruta) if ruta and os.path.isfile(ruta) else QPixmap()
        self.modo, self.escala = modo, escala
        self._clave = None
        self.update()

    def _pixmap(self) -> QPixmap:
        """Imagen ya escalada para el modo actual (se recalcula sólo si cambia el tamaño)."""
        if self.modo in ("llenar", "ajustar"):
            clave = (self.modo, self.width(), self.height())
            aspecto = (Qt.AspectRatioMode.KeepAspectRatioByExpanding if self.modo == "llenar"
                       else Qt.AspectRatioMode.KeepAspectRatio)
            hacer = lambda: self._imagen.scaled(self.size(), aspecto, Qt.TransformationMode.SmoothTransformation)
        else:
            clave = ("escala", self.escala)
            hacer = lambda: self._imagen if self.escala == 100 else self._imagen.scaled(max(1, self._imagen.width() * self.escala // 100),
                                                max(1, self._imagen.height() * self.escala // 100),
                                                Qt.AspectRatioMode.IgnoreAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
        if clave != self._clave:
            self._clave, self._escalada = clave, hacer()
        return self._escalada

    def paintEvent(self, evento):
        p = QPainter(self)
        opt = QStyleOption()
        opt.initFrom(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)   # color del tema
        if self._imagen.isNull() or self.modo == "ninguno":
            return
        img = self._pixmap()
        if self.modo == "mosaico":
            p.drawTiledPixmap(self.rect(), img)
        else:
            p.drawPixmap((self.width() - img.width()) // 2, (self.height() - img.height()) // 2, img)


class FondoDialog(QDialog):
    """Permite elegir la imagen de fondo y su tamaño; los cambios se ven al instante en la ventana."""

    def __init__(self, parent, cfg: Config, lienzo: Lienzo):
        super().__init__(parent)
        self.cfg, self.lienzo = cfg, lienzo
        self.setWindowTitle("Imagen de fondo")
        self.setMinimumWidth(520)
        lay = tema.margenes(QVBoxLayout(self))
        lay.addWidget(tema.etiqueta("Imagen de fondo", "titulo"))
        form = tema.formulario(QFormLayout())

        fila = QHBoxLayout()
        self.e_ruta = QLineEdit(cfg.fondo_imagen)
        self.e_ruta.editingFinished.connect(self._vista_previa)
        fila.addWidget(self.e_ruta, 1)
        b = tema.boton("Examinar…", "imagen")
        b.clicked.connect(self._examinar)
        fila.addWidget(b)
        form.addRow("Archivo de imagen", fila)

        self.c_modo = QComboBox()
        for clave, texto in MODOS:
            self.c_modo.addItem(texto, clave)
        self.c_modo.setCurrentIndex(max(0, self.c_modo.findData(cfg.fondo_modo)))
        self.c_modo.currentIndexChanged.connect(self._vista_previa)
        form.addRow("Cómo mostrarla", self.c_modo)

        fila = QHBoxLayout()
        self.sl_escala = QSlider(Qt.Orientation.Horizontal)
        self.sl_escala.setRange(10, 400)
        self.sp_escala = QSpinBox()
        self.sp_escala.setRange(10, 400)
        self.sp_escala.setSuffix(" %")
        self.sl_escala.valueChanged.connect(self.sp_escala.setValue)
        self.sp_escala.valueChanged.connect(self.sl_escala.setValue)
        self.sp_escala.setValue(cfg.fondo_escala)
        self.sp_escala.valueChanged.connect(self._vista_previa)
        fila.addWidget(self.sl_escala, 1)
        fila.addWidget(self.sp_escala)
        form.addRow("Tamaño (porcentaje del tamaño real)", fila)
        self.lbl_info = tema.etiqueta("", "ayuda")
        form.addRow(self.lbl_info)
        lay.addLayout(form)

        lay.addSpacing(tema.ESPACIO[2])
        bb = tema.botones_dialogo("Guardar", "Cancelar")
        bb.accepted.connect(self._aceptar)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._vista_previa()

    def _examinar(self):
        actual = self.e_ruta.text().strip()
        inicio = os.path.dirname(actual) if actual else carpeta_programa()
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegir imagen de fondo", inicio, FILTRO)
        if ruta:
            self.e_ruta.setText(os.path.normpath(ruta))
            if self.c_modo.currentData() == "ninguno":
                self.c_modo.setCurrentIndex(self.c_modo.findData("tamano"))
            self._vista_previa()

    def _vista_previa(self):
        modo = self.c_modo.currentData()
        self.sl_escala.setEnabled(modo in ("tamano", "mosaico"))
        self.sp_escala.setEnabled(modo in ("tamano", "mosaico"))
        ruta = self.e_ruta.text().strip()
        img = QPixmap(ruta) if ruta and os.path.isfile(ruta) else QPixmap()
        if modo == "ninguno":
            self.lbl_info.setText("No se mostrará ninguna imagen.")
        elif img.isNull():
            self.lbl_info.setText("No se encontró la imagen o el formato no es compatible.")
        else:
            esc = self.sp_escala.value()
            txt = f"Tamaño real: {img.width()} × {img.height()} px."
            if modo in ("tamano", "mosaico"):
                txt += f"  Se mostrará a {img.width() * esc // 100} × {img.height() * esc // 100} px."
                if esc > 100:
                    txt += "  Sobre 100 % la imagen puede verse borrosa."
            self.lbl_info.setText(txt)
        self.lienzo.set_fondo(ruta, modo, self.sp_escala.value())

    def _aceptar(self):
        ruta, modo = self.e_ruta.text().strip(), self.c_modo.currentData()
        if modo != "ninguno" and (not ruta or QPixmap(ruta).isNull()):
            error(self, "No se pudo abrir la imagen elegida.\n\nElige otro archivo o selecciona «Sin imagen».")
            return
        self.cfg.guardar_fondo(ruta, modo, self.sp_escala.value())
        self.accept()

    def reject(self):   # deshace la vista previa
        aplicar(self.cfg, self.lienzo)
        super().reject()


def aplicar(cfg: Config, lienzo: Lienzo):
    lienzo.set_fondo(cfg.fondo_imagen, cfg.fondo_modo, cfg.fondo_escala)
