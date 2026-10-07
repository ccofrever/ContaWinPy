"""Inicio de sesión (ChkPass / diálogo INICIAL) y selección de empresa y año
(Sel_Empresa / DLG_SelEmpresa, SLaEmpresa / DLG_SELANOS)."""
from __future__ import annotations

import os

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QAction, QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from .. import util
from ..config import carpeta_programa
from ..db import ErrorDatos
from . import tema
from .comunes import Sesion, Tabla, error


# colores fijos de la portada: van sobre la imagen, no cambian con el tema claro/oscuro
_TINTA_PORTADA = "#1F1D4A"
_TINTA_PORTADA_SUAVE = "#4A4F75"


class PortadaLogin(QWidget):
    """Mitad izquierda del inicio de sesión: la imagen (FONDO.BMP) ajustada al ancho y apoyada
    abajo; arriba se funde con el color del cielo de la propia imagen para dejar leer el título."""

    def __init__(self, ruta: str, parent=None):
        super().__init__(parent)
        self._imagen = QPixmap(ruta) if ruta and os.path.isfile(ruta) else QPixmap()
        self._cielo = QColor("#AAB9EE")
        if not self._imagen.isNull():   # color promedio de la franja superior de la imagen
            franja = self._imagen.copy(0, 0, self._imagen.width(), max(1, self._imagen.height() // 12))
            self._cielo = franja.scaled(1, 1, Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation).toImage().pixelColor(0, 0)
        self._escalada, self._ancho = QPixmap(), -1

    def logo(self, lado: int = 44) -> QPixmap:
        """Ícono de la marca: recorte cuadrado de la imagen con esquinas redondeadas."""
        lienzo = QPixmap(lado, lado)
        lienzo.fill(Qt.GlobalColor.transparent)
        if self._imagen.isNull():
            return lienzo
        alto = self._imagen.height()
        x = max(0, min(self._imagen.width() - alto, int(self._imagen.width() * 0.6) - alto // 2))
        recorte = self._imagen.copy(x, 0, alto, alto).scaled(lado, lado, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                             Qt.TransformationMode.SmoothTransformation)
        p = QPainter(lienzo)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        camino = QPainterPath()
        camino.addRoundedRect(QRectF(0, 0, lado, lado), 10, 10)
        p.setClipPath(camino)
        p.drawPixmap(0, 0, recorte)
        p.end()
        return lienzo

    def paintEvent(self, evento):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), self._cielo)
        if not self._imagen.isNull():
            if self._ancho != w:
                self._escalada = self._imagen.scaledToWidth(w, Qt.TransformationMode.SmoothTransformation)
                self._ancho = w
            alto = self._escalada.height()
            y = h - alto
            p.drawPixmap(0, y, self._escalada)
            # funde el borde superior de la imagen con el cielo
            franja = int(alto * 0.35) + 1
            borde = QLinearGradient(0, y, 0, y + franja)
            transparente = QColor(self._cielo)
            transparente.setAlpha(0)
            borde.setColorAt(0, self._cielo)
            borde.setColorAt(1, transparente)
            p.fillRect(0, y, w, franja, borde)
        # oscurece el pie para que se lea la firma
        pie = QLinearGradient(0, h - 120, 0, h)
        pie.setColorAt(0, QColor(31, 29, 74, 0))
        pie.setColorAt(1, QColor(31, 29, 74, 110))
        p.fillRect(0, h - 120, w, 120, pie)
        p.end()


class LoginDialog(QDialog):
    """Inicio de sesión a pantalla completa: portada con la imagen y el nombre del sistema a la
    izquierda; a la derecha usuario, confirmación del nombre, clave con mostrar/ocultar e Ingresar."""

    def __init__(self, sesion: Sesion, titulo: str, imagen: str | None = None):
        super().__init__()
        self.s = sesion
        self.intentos = 0
        self.setWindowTitle("Selección de usuario")
        self.setMinimumSize(900, 600)
        self.resize(1200, 720)
        self.setWindowState(Qt.WindowState.WindowMaximized)
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # --- portada
        portada = PortadaLogin(imagen if imagen is not None else os.path.join(carpeta_programa(), "FONDO.BMP"))
        pl = QVBoxLayout(portada)
        pl.setContentsMargins(tema.ESPACIO[8], tema.ESPACIO[6], tema.ESPACIO[8], tema.ESPACIO[3])
        pl.setSpacing(tema.ESPACIO[3])
        marca = QHBoxLayout()
        marca.setSpacing(tema.ESPACIO[3])
        logo = QLabel()
        logo.setPixmap(portada.logo())
        marca.addWidget(logo)
        marca.addWidget(self._texto_portada("ContaWin", 16, 600, _TINTA_PORTADA))
        marca.addStretch()
        pl.addLayout(marca)
        pl.addStretch(2)
        t = self._texto_portada(titulo or "Sistema de Contabilidad", 32, 600, _TINTA_PORTADA)
        t.setWordWrap(True)
        t.setMaximumWidth(300)
        pl.addWidget(t)
        d = self._texto_portada("Comprobantes, libros, balances y compras de cada empresa y año de trabajo, "
                                "con las mismas reglas de siempre.", 13, 400, _TINTA_PORTADA_SUAVE)
        d.setWordWrap(True)
        d.setMaximumWidth(340)
        pl.addWidget(d)
        pl.addStretch(5)
        pl.addWidget(self._texto_portada("ContaWin · creado por Claudio A. Cofré V.", 12, 500, "#FFFFFF"))
        raiz.addWidget(portada, 13)

        # --- formulario
        lado = QWidget()
        lado.setObjectName("lienzo")
        ll = QVBoxLayout(lado)
        ll.addStretch()
        fila = QHBoxLayout()
        fila.addStretch()
        form = QWidget()
        form.setFixedWidth(400)
        fila.addWidget(form)
        fila.addStretch()
        ll.addLayout(fila)
        ll.addStretch()
        raiz.addWidget(lado, 12)

        lay = QVBoxLayout(form)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(tema.ESPACIO[2])
        lay.addWidget(tema.etiqueta("Ingresar", "titulo"))
        lay.addWidget(tema.etiqueta("Ingresa con tu usuario y clave.", "secundario"))
        lay.addSpacing(tema.ESPACIO[6])

        lay.addWidget(tema.etiqueta("Usuario", "etiqueta"))
        self.usuario = QLineEdit()
        self.usuario.setMaxLength(10)
        self.usuario.setPlaceholderText("Ej.: Usuario")
        lay.addWidget(self.usuario)
        self.nombre = tema.etiqueta("", "ayuda")       # confirmación: CAC -> Claudio Cofré V.
        self.nombre.setMinimumHeight(tema.ESPACIO[6])
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
        self.lbl_error.setWordWrap(True)
        tema.marcar(self.lbl_error, estado="error")
        lay.addWidget(self.lbl_error)

        self.b_ingresar = tema.boton("Ingresar", variante="primario")
        self.b_ingresar.setAutoDefault(False)        # Enter avanza entre campos; en la clave, ingresa
        lay.addWidget(self.b_ingresar)
        self.b_ingresar.clicked.connect(self._aceptar)   # Esc o cerrar la ventana: salir

        self.usuario.editingFinished.connect(self._mostrar_nombre)
        self.usuario.returnPressed.connect(self.clave.setFocus)
        self.clave.returnPressed.connect(self._aceptar)
        self.usuario.setFocus()

    @staticmethod
    def _texto_portada(texto: str, px: int, peso: int, color_hex: str) -> QLabel:
        lb = QLabel(texto)
        lb.setStyleSheet(f"color: {color_hex}; font-size: {px}px; font-weight: {peso}; background: transparent;")
        return lb

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


class _BotonAno(QPushButton):
    """Año de trabajo en el panel derecho: un clic lo marca; doble clic o Enter trabaja en él."""

    def __init__(self, ano: int, al_elegir, al_aceptar):
        super().__init__()
        self._al_aceptar = al_aceptar
        self.setProperty("variante", "opcion")
        self.setCheckable(True)
        self.setAutoDefault(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(tema.ESPACIO[4], 0, tema.ESPACIO[4], 0)
        fila.setSpacing(tema.ESPACIO[3])
        for w in (self._icono("calendario", "ink-muted"), self._texto(str(ano))):
            fila.addWidget(w)
        self.marca = self._icono("check", "positive")
        self.marca.setVisible(False)
        fila.addWidget(self.marca)
        fila.addStretch()
        self.clicked.connect(al_elegir)

    def _icono(self, nombre: str, token: str) -> QLabel:
        lb = QLabel()
        lb.setPixmap(tema.icono(nombre, token).pixmap(16, 16))
        lb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        return lb

    def _texto(self, texto: str) -> QLabel:
        lb = QLabel(texto)
        lb.setFont(tema.fuente_mono("amount"))
        lb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        return lb

    def marcar(self, activo: bool):
        self.setChecked(activo)
        self.marca.setVisible(activo)

    def mouseDoubleClickEvent(self, evento):
        self._al_aceptar()

    def keyPressEvent(self, evento):
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            self._al_aceptar()
        else:
            super().keyPressEvent(evento)


class SeleccionEmpresaDialog(QDialog):
    """Selección de empresa y año en una sola ventana: a la izquierda la lista de empresas
    (con buscador) y a la derecha los años de trabajo registrados de la empresa marcada."""

    def __init__(self, parent, sesion: Sesion):
        super().__init__(parent)
        self.s = sesion
        self.setWindowTitle("Seleccionar empresa y año de trabajo")
        self.resize(1100, 580)
        self.empresa_id = None
        self.periodo_id = None
        self._empresa_vista = None      # empresa cuyos años se muestran a la derecha
        self._periodo_sel = None
        self._botones: dict[int, _BotonAno] = {}

        lay = tema.margenes(QVBoxLayout(self))
        lay.addWidget(tema.etiqueta("Selecciona la empresa y el año de trabajo", "titulo"))
        lay.addWidget(tema.etiqueta("Marca una empresa para ver sus años. Doble clic o Enter en un año "
                                    "para trabajar en él.", "ayuda"))
        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(tema.ESPACIO[6])
        lay.addLayout(cuerpo, 1)

        # --- izquierda: empresas
        izq = QVBoxLayout()
        izq.setSpacing(tema.ESPACIO[3])
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar por RUT, razón social o giro")
        self.buscar.setClearButtonEnabled(True)
        self.buscar.addAction(tema.icono("buscar"), QLineEdit.ActionPosition.LeadingPosition)
        izq.addWidget(self.buscar)
        self.tabla = Tabla([("RUT", 120, "R"), ("Razón social", 0, "L"), ("Giro", 220, "L")], self)
        empresas = sesion.db.empresas()
        self.tabla.cargar([[util.formato_rut(e["rut"]), e["razon_social"], e["giro"]] for e in empresas],
                          [e["id"] for e in empresas])
        self.buscar.textChanged.connect(self.tabla.filtrar)
        self.tabla.itemSelectionChanged.connect(self._cargar_anos)
        self.tabla.doubleClicked.connect(lambda _: self._enfocar_anos())
        izq.addWidget(self.tabla, 1)
        cuerpo.addLayout(izq, 1)

        # --- derecha: años de la empresa marcada
        panel = tema.tarjeta(self)
        panel.setFixedWidth(360)
        der = tema.margenes(QVBoxLayout(panel), 6, 2)
        der.addWidget(tema.etiqueta("Año de trabajo", "encabezado"))
        self.lbl_empresa = tema.etiqueta("", "ayuda")
        self.lbl_empresa.setWordWrap(True)
        der.addWidget(self.lbl_empresa)
        der.addSpacing(tema.ESPACIO[2])

        lista = QWidget()
        lista.setObjectName("listaAnos")
        lista.setStyleSheet("QWidget#listaAnos { background: transparent; }")
        self.lay_anos = QVBoxLayout(lista)
        self.lay_anos.setContentsMargins(0, 0, 0, 0)
        self.lay_anos.setSpacing(tema.ESPACIO[2])
        self.lbl_sin_anos = tema.etiqueta("La empresa no tiene años de trabajo. Crea uno con «Crear nuevo año…».",
                                          "secundario")
        self.lbl_sin_anos.setWordWrap(True)
        self.lay_anos.addWidget(self.lbl_sin_anos)
        self.lay_anos.addStretch()
        desplazar = QScrollArea()
        desplazar.setWidgetResizable(True)
        desplazar.setFrameShape(QFrame.Shape.NoFrame)
        desplazar.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        desplazar.setWidget(lista)
        der.addWidget(desplazar, 1)

        self.b_nuevo = tema.boton("Crear nuevo año…", "mas")
        self.b_nuevo.setAutoDefault(False)
        self.b_nuevo.clicked.connect(self._nuevo)
        der.addWidget(self.b_nuevo)
        linea = QFrame()
        linea.setProperty("linea", True)
        der.addSpacing(tema.ESPACIO[2])
        der.addWidget(linea)
        der.addSpacing(tema.ESPACIO[2])
        botones = QHBoxLayout()
        botones.addStretch()
        b_cancelar = tema.boton("Cancelar")
        b_cancelar.clicked.connect(self.reject)
        self.b_trabajar = tema.boton("Trabajar en este año", variante="primario")
        self.b_trabajar.clicked.connect(self._aceptar)
        for b in (b_cancelar, self.b_trabajar):
            b.setAutoDefault(False)
            botones.addWidget(b)
        der.addLayout(botones)
        cuerpo.addWidget(panel)

        if not (sesion.empresa_id and self.tabla.seleccionar_dato(sesion.empresa_id)) and empresas:
            self.tabla.selectRow(0)
        self._cargar_anos()
        self.tabla.setFocus()

    # ------------------------------------------------------------------ años
    def _cargar_anos(self, seleccionar=None):
        eid = self.tabla.dato_actual()
        self._empresa_vista = eid
        for b in self._botones.values():
            self.lay_anos.removeWidget(b)
            b.hide()
            b.deleteLater()
        self._botones = {}
        self._periodo_sel = None
        if eid is None:
            self.lbl_empresa.setText("")
            self.lbl_sin_anos.setText("Marca una empresa de la lista.")
            self.lbl_sin_anos.setVisible(True)
            self.b_nuevo.setEnabled(False)
            return
        self.lbl_empresa.setText(self.s.db.empresa(eid)["razon_social"])
        self.b_nuevo.setEnabled(True)
        per = sorted(self.s.db.periodos(eid), key=lambda p: p["ano"], reverse=True)   # el más reciente arriba
        for i, p in enumerate(per):
            b = _BotonAno(p["ano"], lambda _=False, pid=p["id"]: self.elegir_periodo(pid), self._aceptar)
            self.lay_anos.insertWidget(1 + i, b)
            self._botones[p["id"]] = b
        self.lbl_sin_anos.setText("La empresa no tiene años de trabajo. Crea uno con «Crear nuevo año…».")
        self.lbl_sin_anos.setVisible(not per)
        if per:
            actual = seleccionar or (self.s.periodo_id if eid == self.s.empresa_id else None)
            self.elegir_periodo(actual if actual in self._botones else per[0]["id"])

    def elegir_periodo(self, pid: int):
        self._periodo_sel = pid
        for p, b in self._botones.items():
            b.marcar(p == pid)

    def _enfocar_anos(self):
        b = self._botones.get(self._periodo_sel)
        if b is not None:
            b.setFocus()

    def _nuevo(self):
        eid = self._empresa_vista
        if eid is None:
            return
        import datetime as _dt
        ano, ok = QInputDialog.getInt(self, "Crear nuevo año", "Año de trabajo:", _dt.date.today().year, 1981, 2200)
        if not ok:
            return
        # si hay año anterior con saldos, se ofrece el asiento de apertura (balance del año anterior)
        from .apertura import crear_ano
        try:
            pid = crear_ano(self, self.s.db, eid, ano)
        except ErrorDatos as e:
            error(self, str(e))
            return
        if pid:
            self._cargar_anos(pid)

    def _aceptar(self):
        eid = self.tabla.dato_actual()
        if eid is None:
            error(self, "Marca una empresa de la lista.")
            return
        if eid != self._empresa_vista:
            self._cargar_anos()
        if self._periodo_sel is None:
            error(self, "La empresa no tiene años de trabajo. Crea uno con el botón «Crear nuevo año…».")
            return
        self.empresa_id, self.periodo_id = eid, self._periodo_sel
        self.accept()
