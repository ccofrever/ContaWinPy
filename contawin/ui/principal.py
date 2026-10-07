"""Ventana principal (Main() y MenuMain() de CONTAB.PRG).

Sigue el patrón «Ventana principal» del sistema de diseño ContaWin: barra lateral con los
módulos (Ingresos, Informes, Compras, Utilidades), cabecera con empresa, período y usuario,
y un tablero en el área de trabajo sobre la imagen de fondo elegida (FONDO.BMP por omisión).
"""
from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from .. import APP_NAME, __version__, importer, util
from ..config import Config, carpeta_programa
from ..db import nombre_respaldo
from . import apertura, asientos, fondo, informes_dlg, mantenedores, tema
from .comunes import Sesion, Tabla, confirmar, error, info
from .inicio import SeleccionEmpresaDialog


class BotonNavegacion(QPushButton):
    """Ítem de la barra lateral: ícono + etiqueta + atajo de teclado a la derecha."""

    def __init__(self, accion: QAction, icono_nombre: str, texto: str, consejo: str = "", parent=None):
        super().__init__(parent)
        self.accion = accion
        self.setProperty("variante", "navegacion")
        self.setText(texto.replace("&", "").split(" (")[0].rstrip("…"))
        self.setIcon(tema.icono(icono_nombre))
        self.setIconSize(QSize(20, 20))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        atajo = accion.shortcut().toString() if accion.shortcut() else ""
        self.setToolTip(f"{consejo}  ({atajo})" if atajo else consejo)
        if atajo:
            lay = QHBoxLayout(self)
            lay.setContentsMargins(0, 0, tema.ESPACIO[2] + tema.ESPACIO[3], 0)   # margen del ítem + space-3
            lay.addStretch()
            lb = tema.etiqueta(atajo, "ayuda")
            lb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lay.addWidget(lb)
        self.clicked.connect(accion.trigger)

    def set_activo(self, activo: bool):
        tema.marcar(self, activo=bool(activo))


class Principal(QMainWindow):
    def __init__(self, sesion: Sesion, config: Config):
        super().__init__()
        self.s, self.cfg = sesion, config
        self.setWindowTitle(f"ContaWin · {config.titulo}")
        self.resize(1200, 760)
        self._crear_acciones()
        self._crear_menu()
        self._crear_interfaz()
        self._actualizar_estado()

    # ------------------------------------------------------------------ construcción
    def _accion(self, texto, ic, fn, atajo=None, consejo=None, empresa=True):
        a = QAction(tema.icono(ic), texto, self)
        a.setStatusTip(consejo or texto.replace("&", ""))
        if atajo:
            a.setShortcut(QKeySequence(atajo))
        a.triggered.connect(lambda: self._ejecutar(fn, empresa))
        a.icono_nombre = ic
        a.etiqueta = texto
        a.consejo = consejo or texto.replace("&", "")
        return a

    def _crear_acciones(self):
        A = self._accion
        self.a_sel = A("Seleccionar &empresa…", "cambiar", self.seleccionar_empresa, "F2",
                       "Selecciona la empresa y el año de trabajo", empresa=False)
        self.a_asi = A("&Comprobantes", "comprobante",
                       lambda: asientos.mantener_asientos(self, self.s), "F3", "Asientos contables del año")
        self.a_nuevo = A("&Nuevo comprobante", "mas", self.nuevo_comprobante, "Ctrl+N",
                         "Ingresa un comprobante contable")
        self.a_ape = A("Asiento de a&pertura…", "importar", self.asiento_apertura, None,
                       "Genera el asiento de apertura con los saldos del balance del año anterior")
        self.a_cta = A("&Plan de cuentas", "cuentas",
                       lambda: mantenedores.mantener_cuentas(self, self.s), "F4", "Mantención del plan de cuentas")
        self.a_pro = A("P&roveedores", "proveedor",
                       lambda: mantenedores.mantener_proveedores(self, self.s), None, "Proveedores de la empresa")
        self.a_cco = A("Centros de c&osto", "ccosto",
                       lambda: mantenedores.mantener_ccostos(self, self.s), None, "Centros de costo de la empresa")
        self.a_emp = A("E&mpresas", "empresa",
                       lambda: mantenedores.mantener_empresas(self, self.s), None, "Crea y mantiene empresas",
                       empresa=False)
        self.a_b8 = A("Balance de &8 columnas", "balance",
                      lambda: informes_dlg.balance_8(self, self.s), None, "Balance de 8 columnas")
        self.a_bti = A("Balance &tipo informe", "informe",
                       lambda: informes_dlg.balance_tipo_informe(self, self.s), None, "Balance tipo informe")
        self.a_ld = A("Libro &diario", "diario",
                      lambda: informes_dlg.libro_diario(self, self.s), None, "Consulta e impresión del libro diario")
        self.a_ldt = A("Libro diario por t&ipo", "tipo",
                       lambda: informes_dlg.libro_diario(self, self.s, True), None, "Libro diario por tipo de asiento")
        self.a_may = A("Movimientos de &mayor", "mayor",
                       lambda: informes_dlg.libro_mayor(self, self.s), None, "Movimientos de mayor por cuenta")
        self.a_lc = A("Libro de &compras", "compras",
                      lambda: informes_dlg.libro_compras(self, self.s), None, "Libro de compras")
        self.a_usu = A("&Usuarios", "usuarios", lambda: mantenedores.mantener_usuarios(self, self.s),
                       None, "Define las claves de acceso de los usuarios", empresa=False)
        self.a_imp = A("&Importar datos del ContaWin antiguo (DBF)…", "importar", self.importar_dbf,
                       None, "Trae empresas, cuentas, asientos y compras desde los archivos DBF", empresa=False)
        self.a_res = A("&Respaldar base de datos…", "respaldar", self.respaldar, None,
                       "Guarda una copia de seguridad de todos los datos", empresa=False)
        self.a_fondo = A("Imagen de &fondo…", "imagen", self.elegir_fondo, None,
                         "Elige la imagen del área de trabajo y su tamaño", empresa=False)
        self.a_acerca = A("Acerca &de ContaWin…", "info", self.acerca, None, empresa=False)
        self.a_salir = A("&Salir", "salir", self.close, "Alt+F4", "Salir del programa", empresa=False)

    def _crear_menu(self):
        mb = self.menuBar()
        m = mb.addMenu("&Ingresos")
        m.addAction(self.a_nuevo)
        m.addAction(self.a_asi)
        m.addAction(self.a_ape)
        m.addSeparator()
        for a in (self.a_cta, self.a_pro, self.a_cco):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_emp)
        m.addSeparator()
        m.addAction(self.a_sel)
        m = mb.addMenu("I&nformes")
        for a in (self.a_b8, self.a_bti, self.a_ld, self.a_ldt, self.a_may):
            m.addAction(a)
        m = mb.addMenu("&Compras")
        m.addAction(self.a_lc)
        m = mb.addMenu("&Útiles")
        m.addAction(self.a_usu)
        m.addSeparator()
        m.addAction(self.a_imp)
        m.addAction(self.a_res)
        m.addSeparator()
        ap = m.addMenu("&Apariencia")
        grupo = QActionGroup(self)
        actual = (self.cfg.tema or "claro").lower()
        for clave, texto in [("claro", "Claro"), ("oscuro", "Oscuro"), ("automatico", "Según Windows")]:
            a = QAction(texto, self)
            a.setCheckable(True)
            a.setChecked(actual == clave)
            a.triggered.connect(lambda _=False, c=clave: self.cambiar_tema(c))
            grupo.addAction(a)
            ap.addAction(a)
        m.addAction(self.a_fondo)
        m.addSeparator()
        m.addAction(self.a_acerca)
        m = mb.addMenu("&Salir")
        m.addAction(self.a_salir)

    def _crear_interfaz(self):
        raiz = QWidget()
        h = QHBoxLayout(raiz)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._crear_barra_lateral())
        derecha = QVBoxLayout()
        derecha.setSpacing(0)
        derecha.addWidget(self._crear_cabecera())
        derecha.addWidget(self._crear_tablero(), 1)
        h.addLayout(derecha, 1)
        self.setCentralWidget(raiz)

    def _crear_barra_lateral(self) -> QWidget:
        barra = QFrame()
        barra.setObjectName("barraLateral")
        barra.setFixedWidth(tema.ANCHO_BARRA_LATERAL)
        externo = QVBoxLayout(barra)
        externo.setContentsMargins(0, 0, 0, 0)
        desplaza = QScrollArea()
        desplaza.setWidgetResizable(True)
        desplaza.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        desplaza.setFrameShape(QFrame.Shape.NoFrame)
        cont = QWidget()
        cont.setObjectName("navLista")
        lay = QVBoxLayout(cont)
        lay.setContentsMargins(0, tema.ESPACIO[4], 0, tema.ESPACIO[4])
        lay.setSpacing(2)
        marca = tema.etiqueta("ContaWin", "marca")
        marca.setContentsMargins(tema.ESPACIO[6] - 4, 0, 0, tema.ESPACIO[2])
        lay.addWidget(marca)

        self.navegacion: list[BotonNavegacion] = []
        self.b_inicio = QPushButton("Inicio")
        tema.marcar(self.b_inicio, variante="navegacion", activo=True)
        self.b_inicio.setIcon(tema.icono("inicio", "brand"))
        self.b_inicio.setIconSize(QSize(20, 20))
        self.b_inicio.clicked.connect(self._actualizar_estado)
        lay.addWidget(self.b_inicio)

        secciones = [("Ingresos", [self.a_asi, self.a_ape, self.a_cta, self.a_pro, self.a_cco]),
                     ("Informes", [self.a_b8, self.a_bti, self.a_ld, self.a_ldt, self.a_may]),
                     ("Compras", [self.a_lc]),
                     ("Utilidades", [self.a_emp, self.a_usu, self.a_imp, self.a_res, self.a_fondo])]
        cortos = {id(self.a_imp): "Importar desde DBF", id(self.a_ape): "Asiento de apertura", id(self.a_res): "Respaldar datos",
                  id(self.a_fondo): "Imagen de fondo",
                  id(self.a_ldt): "Diario por tipo", id(self.a_may): "Mayor"}
        for titulo, acciones in secciones:
            lay.addWidget(tema.etiqueta(titulo, "seccion"))
            for a in acciones:
                b = BotonNavegacion(a, a.icono_nombre, cortos.get(id(a), a.etiqueta), a.consejo)
                self.navegacion.append(b)
                lay.addWidget(b)
        lay.addStretch()
        desplaza.setWidget(cont)
        externo.addWidget(desplaza, 1)
        salir = BotonNavegacion(self.a_salir, "salir", "Salir", "Salir del programa")
        externo.addWidget(salir)
        externo.addSpacing(tema.ESPACIO[2])
        return barra

    def _crear_cabecera(self) -> QWidget:
        cab = QFrame()
        cab.setObjectName("cabecera")
        h = QHBoxLayout(cab)
        h.setContentsMargins(tema.ESPACIO[6], tema.ESPACIO[3], tema.ESPACIO[6], tema.ESPACIO[3])
        h.setSpacing(tema.ESPACIO[4])
        col = QVBoxLayout()
        col.setSpacing(0)
        self.lbl_empresa = tema.etiqueta("", "encabezado")
        self.lbl_rut = tema.etiqueta("", "ayuda")
        col.addWidget(self.lbl_empresa)
        col.addWidget(self.lbl_rut)
        h.addLayout(col)
        self.lbl_periodo = QLabel("")
        tema.marcar(self.lbl_periodo, chip=True)
        h.addWidget(self.lbl_periodo, 0, Qt.AlignmentFlag.AlignVCenter)
        h.addStretch()
        self.lbl_usuario = tema.etiqueta("", "secundario")
        h.addWidget(self.lbl_usuario)
        self.b_cambiar = tema.boton("Cambiar empresa", "cambiar")
        self.b_cambiar.setToolTip("Selecciona otra empresa o año (F2)")
        self.b_cambiar.clicked.connect(self.a_sel.trigger)
        h.addWidget(self.b_cambiar)
        return cab

    def _crear_tablero(self) -> QWidget:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        lienzo = self.lienzo = fondo.Lienzo()
        fondo.aplicar(self.cfg, lienzo)
        lay = tema.margenes(QVBoxLayout(lienzo), 8, 6)

        # --- estado vacío (sin empresa seleccionada)
        self.vacio = tema.tarjeta()
        v = tema.margenes(QVBoxLayout(self.vacio), 8, 3)
        v.addWidget(tema.etiqueta("Selecciona una empresa para comenzar", "titulo"))
        v.addWidget(tema.etiqueta("Elige la empresa y el año contable con los que vas a trabajar.", "secundario"))
        b = tema.boton("Seleccionar empresa", "cambiar", "primario")
        b.setToolTip("F2")
        b.clicked.connect(self.a_sel.trigger)
        fila = QHBoxLayout()
        fila.addWidget(b)
        fila.addStretch()
        v.addLayout(fila)
        lay.addWidget(self.vacio)

        # --- contenido del tablero
        self.contenido = QWidget()
        c = QVBoxLayout(self.contenido)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(tema.ESPACIO[6])
        self.lbl_titulo = tema.etiqueta("", "titulo")
        c.addWidget(self.lbl_titulo)

        fila = QHBoxLayout()
        fila.setSpacing(tema.ESPACIO[4])
        # estado del período
        t_estado = tema.tarjeta()
        g = QGridLayout(t_estado)
        g.setContentsMargins(*[tema.ESPACIO[6]] * 4)
        g.setHorizontalSpacing(tema.ESPACIO[8])
        g.setVerticalSpacing(tema.ESPACIO[1])
        g.addWidget(tema.etiqueta("Estado del período", "encabezado"), 0, 0, 1, 3)
        self.lbl_cant = tema.etiqueta("0", "cifra-grande")
        self.lbl_debe = tema.etiqueta("$ 0", "cifra-grande")
        self.lbl_haber = tema.etiqueta("$ 0", "cifra-grande")
        for col, (titulo, w) in enumerate([("Comprobantes", self.lbl_cant), ("Total debe", self.lbl_debe),
                                           ("Total haber", self.lbl_haber)]):
            g.addWidget(tema.etiqueta(titulo, "ayuda"), 1, col)
            g.addWidget(w, 2, col)
        self.lbl_cuadre = tema.etiqueta("")
        g.addWidget(self.lbl_cuadre, 3, 0, 1, 3)
        self.lbl_rango = tema.etiqueta("", "ayuda")
        g.addWidget(self.lbl_rango, 4, 0, 1, 3)
        g.setRowMinimumHeight(3, 32)
        fila.addWidget(t_estado, 3)

        # accesos rápidos
        t_acc = tema.tarjeta()
        va = tema.margenes(QVBoxLayout(t_acc), 6, 3)
        va.addWidget(tema.etiqueta("Accesos rápidos", "encabezado"))
        ga = QGridLayout()
        ga.setSpacing(tema.ESPACIO[2])
        b_nuevo = tema.boton("Nuevo comprobante", "mas", "primario")
        b_nuevo.setToolTip("Ctrl+N")
        b_nuevo.clicked.connect(self.a_nuevo.trigger)
        ga.addWidget(b_nuevo, 0, 0, 1, 2)
        for i, (a, texto) in enumerate([(self.a_asi, "Comprobantes  F3"), (self.a_cta, "Plan de cuentas  F4"),
                                         (self.a_ld, "Libro diario"), (self.a_b8, "Balance 8 columnas")]):
            bb = tema.boton(texto, a.icono_nombre)
            bb.clicked.connect(a.trigger)
            ga.addWidget(bb, 1 + i // 2, i % 2)
        va.addLayout(ga)
        va.addStretch()
        fila.addWidget(t_acc, 2)
        c.addLayout(fila)

        # últimos comprobantes
        t_ult = tema.tarjeta()
        vu = tema.margenes(QVBoxLayout(t_ult), 6, 3)
        cab = QHBoxLayout()
        cab.addWidget(tema.etiqueta("Últimos comprobantes", "encabezado"))
        cab.addStretch()
        ver = tema.boton("Ver todos (F3)", variante="enlace")
        ver.clicked.connect(self.a_asi.trigger)
        cab.addWidget(ver)
        vu.addLayout(cab)
        self.tabla_ult = Tabla([("N°", 70, "R"), ("Fecha", 100, "C"), ("Tipo", 100, "L"), ("Glosa", 0, "L"),
                                ("Monto", 140, "R"), ("Estado", 140, "L")], self)
        self.tabla_ult.setMinimumHeight(tema.ALTO_CONTROL * 9)
        self.tabla_ult.doubleClicked.connect(lambda _: self._abrir_comprobante())
        vu.addWidget(self.tabla_ult)
        self.lbl_sin_comp = tema.etiqueta("Aún no hay comprobantes en este año. Usa «Nuevo comprobante» para "
                                          "ingresar el primero.", "secundario")
        vu.addWidget(self.lbl_sin_comp)
        c.addWidget(t_ult)
        lay.addWidget(self.contenido)
        lay.addStretch()
        area.setWidget(lienzo)
        return area

    # ------------------------------------------------------------------ estado
    def _actualizar_estado(self):
        u = self.s.usuario or {}
        nombre_u = u.get("nombre") or u.get("usuario", "")
        self.lbl_usuario.setText(f"{nombre_u} · {u.get('usuario', '')}" if u else "")
        hay = bool(self.s.empresa and self.s.periodo)
        if hay:
            e = self.s.empresa
            self.lbl_empresa.setText(e["razon_social"])
            self.lbl_rut.setText(f"RUT {util.formato_rut(e['rut'])}")
            self.lbl_periodo.setText(f"Año {self.s.ano}")
            texto = f"{e['razon_social']} · Año {self.s.ano}"
        else:
            self.lbl_empresa.setText("Sin empresa seleccionada")
            self.lbl_rut.setText("Presiona F2 para elegir empresa y año")
            self.lbl_periodo.setText("")
            texto = "Selecciona una empresa para trabajar (F2)"
        self.lbl_periodo.setVisible(hay)
        self.vacio.setVisible(not hay)
        self.contenido.setVisible(hay)
        if hay:
            self._actualizar_tablero()
        self.statusBar().showMessage(f"Usuario: {u.get('usuario', '')}  ·  {texto}")

    def _actualizar_tablero(self):
        db = self.s.db
        lista = db.asientos(self.s.periodo_id)
        self.lbl_titulo.setText(f"Resumen del año {self.s.ano}")
        debe = sum(a["debe"] for a in lista)
        haber = sum(a["haber"] for a in lista)
        descuadrados = sum(1 for a in lista if a["debe"] != a["haber"])
        self.lbl_cant.setText(util.fmt_monto(len(lista)))
        self.lbl_debe.setText(util.fmt_pesos(debe))
        self.lbl_haber.setText(util.fmt_pesos(haber))
        if not lista:
            self.lbl_cuadre.setText("Sin comprobantes todavía.")
            tema.marcar(self.lbl_cuadre, estado="", rol="secundario")
        elif descuadrados:
            self.lbl_cuadre.setText(f"⚠ {descuadrados} comprobante{'s' if descuadrados > 1 else ''} "
                                    f"descuadrado{'s' if descuadrados > 1 else ''}")
            tema.marcar(self.lbl_cuadre, estado="error", rol="")
        else:
            self.lbl_cuadre.setText("✓ Todos los comprobantes están cuadrados")
            tema.marcar(self.lbl_cuadre, estado="ok", rol="")
        d, h = db.rango_fechas(self.s.periodo_id)
        self.lbl_rango.setText(f"Movimientos del {util.fmt_fecha(d)} al {util.fmt_fecha(h)}" if d else "")

        ultimos = sorted(lista, key=lambda a: a["numero"], reverse=True)[:8]
        filas = [[util.fmt_monto(a["numero"]), util.fmt_fecha(a["fecha"]), util.nombre_tipo_asiento(a["tipo"]),
                  a["glosa"], util.fmt_pesos(max(a["debe"], a["haber"])),
                  "✓ Cuadrado" if a["debe"] == a["haber"] else "⚠ Descuadrado"] for a in ultimos]
        self.tabla_ult.cargar(filas, [a["id"] for a in ultimos])
        for r, a in enumerate(ultimos):
            it = self.tabla_ult.item(r, 5)
            if it is not None:
                it.setForeground(tema.qcolor("positive" if a["debe"] == a["haber"] else "negative"))
        self.tabla_ult.setVisible(bool(ultimos))
        self.lbl_sin_comp.setVisible(not ultimos)

    def _abrir_comprobante(self):
        aid = self.tabla_ult.dato_actual()
        if aid is not None:
            self._ejecutar(lambda: asientos.AsientoEditor(self, self.s, aid).exec(), True)

    def asiento_apertura(self):
        apertura.abrir(self, self.s.db, self.s.empresa_id, self.s.periodo_id)

    def nuevo_comprobante(self):
        asientos.AsientoEditor(self, self.s).exec()

    def elegir_fondo(self):
        fondo.FondoDialog(self, self.cfg, self.lienzo).exec()

    def cambiar_tema(self, clave: str):
        self.cfg.tema = clave
        info(self, "La apariencia se aplicará la próxima vez que abras ContaWin.", "Apariencia")

    def _ejecutar(self, fn, requiere_empresa: bool):
        if requiere_empresa and not (self.s.empresa and self.s.periodo):
            error(self, "Primero debes seleccionar una empresa.\n\nUsa «Cambiar empresa» o presiona F2.")
            if not self.seleccionar_empresa():
                return
        try:
            fn()
        finally:
            self.s.refrescar_empresa()
            self._actualizar_estado()

    def seleccionar_empresa(self) -> bool:
        if not self.s.db.empresas():
            if confirmar(self, "No hay empresas en la base de datos.\n\n"
                               "¿Quieres importar los datos del ContaWin antiguo (archivos DBF)?\n"
                               "(Responde No para crear una empresa nueva)"):
                self.importar_dbf()
            else:
                mantenedores.mantener_empresas(self, self.s)
            if not self.s.db.empresas():
                return False
        dlg = SeleccionEmpresaDialog(self, self.s)
        if dlg.exec() and dlg.empresa_id:
            self.s.empresa = dict(self.s.db.empresa(dlg.empresa_id))
            self.s.periodo = dict(self.s.db.periodo(dlg.periodo_id))
            self._actualizar_estado()
            return True
        return False

    # ------------------------------------------------------------------ útiles
    def importar_dbf(self):
        inicial = self.cfg.carpeta_dbf
        if not inicial:     # si el programa se instaló dentro de la carpeta CONTAWIN, partir ahí
            padre = os.path.dirname(carpeta_programa())
            inicial = padre if os.path.exists(os.path.join(padre, "EMPRESA.DBF")) else ""
        carpeta = QFileDialog.getExistingDirectory(
            self, "Seleccione la carpeta CONTAWIN (la que contiene EMPRESA.DBF)", inicial)
        if not carpeta:
            return
        if not os.path.exists(os.path.join(carpeta, "EMPRESA.DBF")) and \
                not any(f.lower() == "empresa.dbf" for f in os.listdir(carpeta)):
            error(self, "En esa carpeta no está el archivo EMPRESA.DBF.")
            return
        reemplazar = False
        if self.s.db.empresas():
            r = QMessageBox.question(
                self, "Importar",
                "Ya hay empresas en la base de datos.\n\n"
                "¿Reemplazar las empresas que ya existan (mismo RUT) con los datos de los DBF?\n\n"
                "Sí = reemplazar   ·   No = importar solo las empresas nuevas",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.No)
            if r == QMessageBox.StandardButton.Cancel:
                return
            reemplazar = r == QMessageBox.StandardButton.Yes
            if reemplazar:
                self.s.empresa = self.s.periodo = None
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = importer.importar(carpeta, self.s.db, reemplazar,
                                    progreso=lambda t: (self.statusBar().showMessage(t), QApplication.processEvents()))
        except Exception as e:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            error(self, f"No se pudo importar:\n{e}")
            return
        QApplication.restoreOverrideCursor()
        self.cfg.carpeta_dbf = carpeta
        _mostrar_texto(self, "Resultado de la importación", res.resumen())

    def respaldar(self):
        sugerido = os.path.join(os.path.expanduser("~"), nombre_respaldo(self.s.db.ruta))
        ruta, _ = QFileDialog.getSaveFileName(self, "Respaldar base de datos", sugerido, "Base de datos (*.db)")
        if not ruta:
            return
        try:
            self.s.db.respaldar(ruta)
        except Exception as e:  # noqa: BLE001
            error(self, f"No se pudo respaldar:\n{e}")
            return
        info(self, f"Respaldo guardado en:\n{ruta}\n\nPara restaurarlo, copie el archivo sobre:\n{self.s.db.ruta}")

    def acerca(self):
        QMessageBox.about(self, "Acerca de",
                          f"<h3>{APP_NAME} v{__version__}</h3>"
                          "<p>Versión Python (PySide6 + SQLite) del Sistema de Contabilidad ContaWin, "
                          "escrito originalmente en xHarbour/FiveWin por Claudio A. Cofré V.</p>"
                          f"<p>Base de datos:<br><code>{self.s.db.ruta}</code></p>")

    def closeEvent(self, ev):
        if confirmar(self, "¿Salir del sistema?"):
            ev.accept()
        else:
            ev.ignore()


def _mostrar_texto(parent, titulo: str, texto: str):
    d = QDialog(parent)
    d.setWindowTitle(titulo)
    d.resize(720, 480)
    lay = QVBoxLayout(d)
    t = QPlainTextEdit(texto)
    t.setReadOnly(True)
    lay.addWidget(t)
    d.exec()
