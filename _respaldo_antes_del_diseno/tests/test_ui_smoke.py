"""Prueba de humo de la interfaz con un PySide6 simulado (tests/fake_qt).

Recorre los flujos principales: login, selección de empresa/año, mantenedores,
ingreso/modificación/borrado de asientos con documento de compra, todos los
informes con vista previa (dibujo paginado), PDF, Excel, importación y respaldo.

Se ejecuta sólo si PySide6 real NO está instalado (en ese caso, pruebe la
aplicación directamente con  python main.py).
"""
import datetime as dt
import glob
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))

try:
    import PySide6  # noqa: F401
    REAL = getattr(PySide6, "__version__", "") != "fake"
except ImportError:
    REAL = False
if not REAL:
    sys.path.insert(0, os.path.join(AQUI, "fake_qt"))
    for m in [m for m in sys.modules if m.startswith("PySide6")]:
        del sys.modules[m]

# carpeta con EMPRESA.DBF: variable CONTAWIN_DBF, o la carpeta CONTAWIN que contiene a ContaWinPy
_PADRE = os.path.dirname(os.path.dirname(AQUI))
RAIZ_DBF = os.environ.get("CONTAWIN_DBF") or next(
    (c for c in (_PADRE, os.path.join(_PADRE, "raiz")) if os.path.exists(os.path.join(c, "EMPRESA.DBF"))), _PADRE)


@unittest.skipIf(REAL, "PySide6 real instalado: pruebe la interfaz directamente")
class TestInterfaz(unittest.TestCase):
    def setUp(self):
        from PySide6 import _fake
        from contawin import util  # noqa: F401
        from contawin.config import Config
        from contawin.db import Database
        from contawin.ui.comunes import Sesion
        self.f = _fake
        _fake.HANDLERS.clear()
        _fake.MENSAJES.clear()
        _fake.PAGINAS.clear()
        _fake.RESPUESTAS.update(question="Yes", file="", dir="")
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(os.path.join(self.tmp.name, "contawin.ini"))
        self.db = Database(os.path.join(self.tmp.name, "c.db"))
        self.s = Sesion(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def H(self, clase, fn):
        self.f.HANDLERS[clase] = fn

    def avisos(self, tipo="warning"):
        return [t for k, t in self.f.MENSAJES if k == tipo]

    # ------------------------------------------------------------------ flujo completo
    def test_flujo_completo(self):
        from contawin.ui import asientos, informes_dlg, mantenedores
        from contawin.ui.inicio import LoginDialog
        from contawin.ui.principal import Principal

        # --- login
        lg = LoginDialog(self.s, "Sistema")
        lg.usuario.teclear("admin")
        lg.clave.teclear("mala")
        lg._aceptar()
        self.assertIsNone(self.s.usuario)
        self.assertTrue(self.avisos())
        lg.clave.teclear("admin")
        lg._aceptar()
        self.assertEqual(self.s.usuario["usuario"], "ADMIN")

        win = Principal(self.s, self.cfg)

        # --- crear empresa desde el mantenedor
        def form_empresa(d):
            d.rut.teclear("76.127.217-9")
            d.razon.teclear("colegio prueba")
            d.directorio.teclear("prueba")
            d.ano.setValue(2026)
            d._aceptar()
        self.H("FormEmpresa", form_empresa)
        self.H("Catalogo", lambda c: c.accion_nuevo())
        mantenedores.mantener_empresas(win, self.s)
        e = self.db.empresa_por_rut("761272179")
        self.assertEqual(e["razon_social"], "COLEGIO PRUEBA")
        self.assertEqual([p["ano"] for p in self.db.periodos(e["id"])], [2026])

        # RUT inválido
        def form_empresa_mala(d):
            d.rut.teclear("11.111.111-2")
            d.razon.teclear("x")
            d.directorio.teclear("x")
            d._aceptar()
            return d._result
        self.H("FormEmpresa", form_empresa_mala)
        mantenedores.mantener_empresas(win, self.s)
        self.assertIn("dígito verificador", self.avisos()[-1])

        # --- seleccionar empresa y año (crea año 2027 desde el diálogo)
        def sel_ano(d):
            self.f.RESPUESTAS["int"] = (2027, True)
            d._nuevo()
            d.tabla.selectRow(0)       # 2026
            d._aceptar()
        self.H("SeleccionAnoDialog", sel_ano)
        self.H("SeleccionEmpresaDialog", lambda d: d._aceptar())
        self.assertTrue(win.seleccionar_empresa())
        self.assertEqual(self.s.ano, 2026)
        self.assertIn("COLEGIO PRUEBA", win._status.text())

        # --- plan de cuentas, centros de costo, proveedores
        cuentas = [("11.01.01", "caja", False), ("21.01.01", "proveedores", False),
                   ("31.01.01", "materiales", True), ("41.01.01", "subvencion", False)]
        for cod, nom, doc in cuentas:
            def form_cuenta(d, cod=cod, nom=nom, doc=doc):
                d.codigo.setText(cod)
                d.nombre.teclear(nom)
                d.cdocum.setChecked(doc)
                d._aceptar()
            self.H("FormCuenta", form_cuenta)
            mantenedores.mantener_cuentas(win, self.s)
        self.assertEqual(len(self.db.cuentas(self.s.empresa_id)), 4)

        def form_cc(d):
            d.codigo.teclear("01")
            d.nombre.teclear("general")
            d._aceptar()
        self.H("FormCCosto", form_cc)
        mantenedores.mantener_ccostos(win, self.s)

        def form_prov(d):
            d.rut.teclear("96792430-k")
            d.nombre.teclear("sodimac s.a.")
            d._aceptar()
        self.H("FormProveedor", form_prov)
        mantenedores.mantener_proveedores(win, self.s)
        self.assertEqual(self.db.proveedor(self.s.empresa_id, "96792430K")["nombre"], "SODIMAC S.A.")

        # --- asiento 1: apertura simple
        ed = asientos.AsientoEditor(win, self.s)
        ed.glosa.teclear("apertura")
        ed.tipo.setCurrentIndex(ed.tipo.findData("I"))
        ed.fecha.set_fecha(dt.date(2026, 1, 2))

        def linea(cod, debe, haber):
            def h(d):
                d.cuenta.teclear(cod)          # escribe sólo el código, como en el original
                d.debe.teclear(str(debe))
                d.haber.teclear(str(haber))
                d._aceptar()
            return h
        self.H("LineaDialog", linea("11.01.01", "1.000.000", 0))
        ed.nueva_linea()
        self.H("LineaDialog", linea("410101", 0, "1000000"))
        ed.nueva_linea()
        self.assertEqual(ed.lbl_dif.text(), "✔ Cuadrado")
        ed.guardar()
        self.assertEqual(ed._result, 1)

        # --- asiento 2: compra con documento (cuenta pide documento) y centro de costo
        ed = asientos.AsientoEditor(win, self.s)
        ed.glosa.teclear("compra materiales")
        ed.fecha.set_fecha(dt.date(2026, 2, 10))
        ed.ccosto.set_codigo("01")

        def linea_doc(d):
            d.cuenta.teclear("31.01.01")
            d.debe.teclear("119.000")

            def doc(dd):
                dd.tipo.setCurrentIndex(10)          # 11.- Factura Electrónica
                dd.numero.teclear("555")
                dd.proveedor.teclear("96.792.430-K")
                dd.detalle.teclear("pintura")
                dd._aceptar()
            self.H("DocumentoCompraDialog", doc)
            d._aceptar()
        self.H("LineaDialog", linea_doc)
        ed.nueva_linea()
        self.assertIsNotNone(ed.lineas[0]["documento"])
        self.assertEqual(ed.lineas[0]["documento"]["neto"], 100000)
        self.assertEqual(ed.lineas[0]["documento"]["iva"], 19000)
        # descuadrado -> no graba
        ed.guardar()
        self.assertIn("no están cuadradas", self.avisos()[-1])
        # la nueva línea propone el monto faltante en el haber
        self.H("LineaDialog", lambda d: (self.assertEqual(d.haber.valor(), 119000), d.cuenta.teclear("110101"),
                                         d._aceptar()))
        ed.nueva_linea()
        ed.guardar_imprimir()
        self.assertEqual(ed._result, 1)
        self.assertTrue(self.f.PAGINAS)
        compras = self.db.compras(self.s.periodo_id)
        self.assertEqual(len(compras), 1)
        self.assertEqual(compras[0]["cdcosto"], "01")

        # --- modificar asiento 2: cambiar monto de la línea de caja => descuadra; luego corrige
        aid = self.db.asientos(self.s.periodo_id)[1]["id"]
        ed = asientos.AsientoEditor(win, self.s, aid)
        self.assertEqual(len(ed.lineas), 2)
        ed.tabla.selectRow(1)

        def mod(d):
            d.haber.teclear("100000")
            d._aceptar()
        self.H("LineaDialog", mod)
        ed.modificar_linea()
        self.assertIn("Diferencia", ed.lbl_dif.text())
        ed.tabla.selectRow(1)
        ed.borrar_linea()
        self.H("LineaDialog", lambda d: (d.cuenta.teclear("21.01.01"), d._aceptar()))
        ed.nueva_linea()
        ed.guardar()
        self.assertEqual(ed._result, 1)
        det = self.db.detalle_asiento(aid)
        self.assertEqual([l["codigo"] for l in det], ["310101", "210101"])
        self.assertIsNotNone(det[0]["documento"])

        # --- fecha fuera del año: pregunta y respeta el "No"
        ed = asientos.AsientoEditor(win, self.s)
        ed.glosa.teclear("otro año")
        ed.fecha.set_fecha(dt.date(2025, 12, 31))
        self.H("LineaDialog", linea("110101", 10, 0))
        ed.nueva_linea()
        self.H("LineaDialog", linea("410101", 0, 10))
        ed.nueva_linea()
        self.f.RESPUESTAS["question"] = "No"
        ed.guardar()
        self.assertEqual(ed._result, 0)
        self.f.RESPUESTAS["question"] = "Yes"

        # --- lista de asientos: imprimir comprobante y borrar
        def cat_asientos(c):
            self.assertEqual(c.tabla.rowCount(), 2)
            c.tabla.selectRow(0)
            c._extra(lambda aid: None)
            c.ed_buscar.teclear("compra")
            self.assertTrue(c.tabla.isRowHidden(0))
            c.ed_buscar.teclear("")
        self.H("Catalogo", cat_asientos)
        asientos.mantener_asientos(win, self.s)

        # --- informes: todos con vista previa
        n_antes = len(self.f.PAGINAS)

        def visor(v):
            v._previa()
            self.f.RESPUESTAS["file"] = os.path.join(self.tmp.name, v.inf.nombre_archivo + ".pdf")
            v._pdf()
            self.assertTrue(os.path.exists(self.f.RESPUESTAS["file"]))
            self.f.RESPUESTAS["file"] = os.path.join(self.tmp.name, v.inf.nombre_archivo + ".xlsx")
            v._excel()
            self.assertTrue(os.path.exists(self.f.RESPUESTAS["file"]))
        self.H("VisorInforme", visor)
        self.H("ParametrosDialog", lambda d: d._aceptar())
        informes_dlg.libro_diario(win, self.s)
        informes_dlg.libro_diario(win, self.s, por_tipo=True)
        informes_dlg.libro_mayor(win, self.s)
        informes_dlg.balance_8(win, self.s)
        informes_dlg.balance_tipo_informe(win, self.s)
        informes_dlg.libro_compras(win, self.s)

        def compras_cc(d):
            d.todos.setChecked(False)
            d.cc.set_codigo("01")
            d._aceptar()
        self.H("ParametrosDialog", compras_cc)
        informes_dlg.libro_compras(win, self.s)
        self.assertGreaterEqual(len(self.f.PAGINAS) - n_antes, 7)

        # fechas invertidas
        def invertidas(d):
            d.f_desde.set_fecha(dt.date(2026, 12, 1))
            d.f_hasta.set_fecha(dt.date(2026, 1, 1))
            d._aceptar()
            return d._result
        self.H("ParametrosDialog", invertidas)
        informes_dlg.balance_8(win, self.s)
        self.assertIn("mayor o igual", self.avisos()[-1])

        # --- listados de mantenedores (Excel e imprimir)
        def cat_listado(c):
            self.f.RESPUESTAS["file"] = os.path.join(self.tmp.name, "listado.xlsx")
            c.accion_excel()
            c.accion_imprimir()
        self.H("Catalogo", cat_listado)
        for fn in (mantenedores.mantener_cuentas, mantenedores.mantener_ccostos,
                   mantenedores.mantener_proveedores, mantenedores.mantener_empresas):
            fn(win, self.s)

        # --- borrar cuenta con movimientos: debe impedirlo
        def cat_borrar(c):
            c.tabla.seleccionar_dato("110101")
            c.accion_borrar()
        self.H("Catalogo", cat_borrar)
        mantenedores.mantener_cuentas(win, self.s)
        self.assertIn("movimientos", self.avisos()[-1])

        # --- usuarios
        def cat_usuarios(c):
            def form(d):
                d.usuario.teclear("pepe")
                d.nombre.teclear("pepe perez")
                d.clave.teclear("123")
                d.confirma.teclear("123")
                d._aceptar()
            self.H("FormUsuario", form)
            c.accion_nuevo()
            c.tabla.seleccionar_dato("ADMIN")
            c.accion_borrar()          # no puede borrarse a sí mismo
        self.H("Catalogo", cat_usuarios)
        mantenedores.mantener_usuarios(win, self.s)
        self.assertTrue(self.db.login("PEPE", "123"))
        self.assertIn("está trabajando", self.avisos()[-1])

        # --- respaldo
        self.f.RESPUESTAS["file"] = os.path.join(self.tmp.name, "respaldo.db")
        win.respaldar()
        self.assertTrue(os.path.getsize(self.f.RESPUESTAS["file"]) > 0)

        # --- acciones del menú sin empresa -> pide seleccionar
        self.s.empresa = self.s.periodo = None
        self.H("SeleccionEmpresaDialog", lambda d: 0)
        win.a_asi.trigger()
        self.assertIn("seleccionar una empresa", self.avisos()[-1])

        # --- borrar empresa (pide el RUT)
        self.f.RESPUESTAS["text"] = ("76.127.217-9", True)
        self.H("Catalogo", lambda c: (c.tabla.selectRow(0), c.accion_borrar()))
        mantenedores.mantener_empresas(win, self.s)
        self.assertIsNone(self.db.empresa_por_rut("761272179"))

    # ------------------------------------------------------------------ importación + informes reales
    @unittest.skipUnless(glob.glob(os.path.join(RAIZ_DBF, "EMPRESA.DBF")), "sin datos DBF de ejemplo")
    def test_importacion_desde_menu(self):
        from contawin.ui import informes_dlg
        from contawin.ui.principal import Principal
        self.s.usuario = dict(self.db.login("CAC", "CAC"))
        win = Principal(self.s, self.cfg)
        self.f.RESPUESTAS["dir"] = RAIZ_DBF
        self.H("QDialog", lambda d: 1)       # ventana con el resumen
        win.importar_dbf()
        self.assertTrue(self.db.empresas())
        self.assertEqual(self.cfg.carpeta_dbf, RAIZ_DBF)
        # segunda importación: pregunta reemplazar (Yes)
        win.importar_dbf()
        self.assertEqual(len(self.db.empresas()), 2)

        e = self.db.empresa_por_rut("761272179")
        self.s.empresa = dict(e)
        self.s.periodo = dict(self.db.periodos(e["id"])[0])
        self.H("ParametrosDialog", lambda d: d._aceptar())
        self.H("VisorInforme", lambda v: v._previa())
        for fn in (informes_dlg.libro_diario, informes_dlg.libro_mayor, informes_dlg.balance_8,
                   informes_dlg.balance_tipo_informe, informes_dlg.libro_compras):
            fn(win, self.s)
        self.assertTrue(all(p >= 1 for p in self.f.PAGINAS))
        self.assertTrue(any(p > 1 for p in self.f.PAGINAS), "algún informe debería tener varias páginas")


if __name__ == "__main__":
    unittest.main()
