"""Ventana principal (Main() y MenuMain() de CONTAB.PRG)."""
from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QLabel, QMainWindow, QMessageBox,
                               QPlainTextEdit, QToolBar, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__, importer, util
from ..config import Config, carpeta_programa
from ..db import nombre_respaldo
from . import asientos, informes_dlg, mantenedores
from .comunes import Sesion, confirmar, error, icono, info
from .inicio import SeleccionEmpresaDialog


class Principal(QMainWindow):
    def __init__(self, sesion: Sesion, config: Config):
        super().__init__()
        self.s, self.cfg = sesion, config
        self.setWindowTitle(config.titulo)
        self.resize(1100, 700)
        self._crear_fondo()
        self._crear_acciones()
        self._crear_menu()
        self._crear_barra()
        self._actualizar_estado()

    # ------------------------------------------------------------------ construcción
    def _crear_fondo(self):
        w = QWidget()
        w.setObjectName("fondo")
        w.setStyleSheet("#fondo { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                        " stop:0 rgb(0,100,100), stop:1 rgb(0,55,70)); }")
        lay = QVBoxLayout(w)
        lay.addStretch()
        self.lbl_titulo = QLabel(self.cfg.titulo)
        f = QFont("Arial", 30)
        f.setBold(True)
        self.lbl_titulo.setFont(f)
        self.lbl_titulo.setStyleSheet("color: white;")
        self.lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empresa = QLabel("")
        self.lbl_empresa.setFont(QFont("Arial", 15))
        self.lbl_empresa.setStyleSheet("color: #d8f0f0;")
        self.lbl_empresa.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_titulo)
        lay.addWidget(self.lbl_empresa)
        lay.addStretch()
        self.setCentralWidget(w)

    def _accion(self, texto, ic, fn, atajo=None, consejo=None, empresa=True):
        a = QAction(icono(self, ic), texto, self)
        a.setStatusTip(consejo or texto)
        if atajo:
            a.setShortcut(QKeySequence(atajo))
        a.triggered.connect(lambda: self._ejecutar(fn, empresa))
        return a

    def _crear_acciones(self):
        A = self._accion
        self.a_sel = A("Selecciona &Empresa", "SP_DirOpenIcon", self.seleccionar_empresa, "F2",
                       "Selecciona empresa y año a trabajar", empresa=False)
        self.a_asi = A("&Asientos Contables", "SP_FileDialogListView",
                       lambda: asientos.mantener_asientos(self, self.s), "F3", "Mantención Asientos Contables")
        self.a_cta = A("&Plan de Cuentas", "SP_FileDialogDetailedView",
                       lambda: mantenedores.mantener_cuentas(self, self.s), "F4", "Mantención Plan de Cuentas")
        self.a_pro = A("P&roveedores", "SP_DirHomeIcon",
                       lambda: mantenedores.mantener_proveedores(self, self.s), None, "Ingreso de Proveedores")
        self.a_cco = A("C. de &Costo", "SP_DirLinkIcon",
                       lambda: mantenedores.mantener_ccostos(self, self.s), None, "Ingreso de Centros de Costo")
        self.a_emp = A("Crear / Mantener E&mpresas", "SP_ComputerIcon",
                       lambda: mantenedores.mantener_empresas(self, self.s), None, "Mantención Datos Empresa",
                       empresa=False)
        self.a_b8 = A("Balance de &8 Columnas", "SP_FileDialogInfoView",
                      lambda: informes_dlg.balance_8(self, self.s), None, "Balance 8 Columnas")
        self.a_bti = A("Balance &Tipo Informe", "SP_FileDialogContentsView",
                       lambda: informes_dlg.balance_tipo_informe(self, self.s), None, "Balance Tipo Informe")
        self.a_ld = A("Libro &Diario", "SP_FileIcon",
                      lambda: informes_dlg.libro_diario(self, self.s), None, "Consulta e Impresión Libro Diario")
        self.a_ldt = A("Libro Diario por T&ipo", "SP_FileLinkIcon",
                       lambda: informes_dlg.libro_diario(self, self.s, True), None, "Libro Diario por Tipo")
        self.a_may = A("Movimientos de &Mayor", "SP_DriveHDIcon",
                       lambda: informes_dlg.libro_mayor(self, self.s), None, "Movimientos de Mayor")
        self.a_lc = A("Libro de &Compras", "SP_DialogApplyButton",
                      lambda: informes_dlg.libro_compras(self, self.s), None, "Impresión de Libro de Compras")
        self.a_usu = A("&Usuarios", "SP_DialogYesButton", lambda: mantenedores.mantener_usuarios(self, self.s),
                       None, "Define claves de acceso de usuarios", empresa=False)
        self.a_imp = A("&Importar datos del ContaWin antiguo (DBF)…", "SP_ArrowDown", self.importar_dbf,
                       None, "Trae empresas, cuentas, asientos y compras desde los archivos DBF", empresa=False)
        self.a_res = A("&Respaldar base de datos…", "SP_DialogSaveButton", self.respaldar, None,
                       "Guarda una copia de seguridad de todos los datos", empresa=False)
        self.a_acerca = A("Acerca &de…", "SP_MessageBoxInformation", self.acerca, None, empresa=False)
        self.a_salir = A("&Salir", "SP_DialogCloseButton", self.close, "Alt+F4", "Salir del Programa",
                         empresa=False)

    def _crear_menu(self):
        mb = self.menuBar()
        m = mb.addMenu("&Ingresos")
        m.addAction(self.a_asi)
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
        m.addAction(self.a_acerca)
        m = mb.addMenu("&Salir")
        m.addAction(self.a_salir)

    def _crear_barra(self):
        tb = QToolBar("Principal")
        tb.setIconSize(QSize(28, 28))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        tb.setMovable(False)
        for a in (self.a_sel, self.a_asi, self.a_cta, self.a_pro, self.a_cco, None, self.a_emp, None,
                  self.a_b8, self.a_bti, self.a_ld, self.a_ldt, self.a_may, None, self.a_lc, None, self.a_salir):
            if a is None:
                tb.addSeparator()
            else:
                tb.addAction(a)
        self.addToolBar(tb)

    # ------------------------------------------------------------------ estado
    def _actualizar_estado(self):
        u = self.s.usuario or {}
        if self.s.empresa and self.s.periodo:
            texto = f"Trabajando con Empresa < {self.s.empresa['razon_social']}  AÑO {self.s.ano} >"
            self.lbl_empresa.setText(f"{self.s.empresa['razon_social']}\nR.U.T. "
                                     f"{util.formato_rut(self.s.empresa['rut'])}   ·   Año {self.s.ano}")
        else:
            texto = "Seleccione una empresa para trabajar (F2)"
            self.lbl_empresa.setText("Seleccione una empresa para trabajar (F2)")
        self.statusBar().showMessage(f"Usuario: {u.get('usuario', '')}  -  {texto}")

    def _ejecutar(self, fn, requiere_empresa: bool):
        if requiere_empresa and not (self.s.empresa and self.s.periodo):
            error(self, "Debe primero seleccionar una empresa\n\nOpción <Ingresos> <Selecciona Empresa>")
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
                               "¿Desea importar los datos del ContaWin antiguo (archivos DBF)?\n"
                               "(Responda No para crear una empresa nueva)"):
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
