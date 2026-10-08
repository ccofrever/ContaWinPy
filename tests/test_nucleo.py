"""Pruebas del núcleo (sin interfaz gráfica).

Ejecutar:  python -m unittest discover -s tests -v
"""
import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contawin import reports, util  # noqa: E402
from contawin.db import Database, ErrorDatos  # noqa: E402


class TestUtil(unittest.TestCase):
    def test_rut(self):
        self.assertTrue(util.validar_rut("76.127.217-9"))
        self.assertTrue(util.validar_rut("96792430K"))
        self.assertFalse(util.validar_rut("76127217-8"))
        self.assertEqual(util.formato_rut("761272179"), "76.127.217-9")
        self.assertEqual(util.limpiar_rut("10.411.341-9"), "104113419")

    def test_formatos(self):
        self.assertEqual(util.formato_codigo("100001"), "10.00.01")
        self.assertEqual(util.fmt_monto(1234567), "1.234.567")
        self.assertEqual(util.fmt_monto(-1500), "-1.500")
        self.assertEqual(util.parse_monto("1.234.567"), 1234567)
        self.assertEqual(util.to_iso("20170103"), "2017-01-03")
        self.assertEqual(util.fmt_fecha("2017-01-03"), "03/01/2017")


class TestContabilidad(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "t.db"))
        self.emp = self.db.guardar_empresa({"rut": "76.127.217-9", "razon_social": "Empresa de prueba",
                                            "directorio": "PRUEBA", "ciudad": "Chillán"}, ano_inicial=2026)
        self.per = self.db.periodos(self.emp)[0]["id"]
        for cod, nom, doc in [("110101", "CAJA", 0), ("110201", "BANCO", 0), ("210101", "PROVEEDORES", 0),
                              ("310101", "MATERIALES", 1), ("410101", "VENTAS", 0)]:
            self.db.guardar_cuenta(self.emp, cod, nom, doc, True)
        self.db.guardar_ccosto(self.emp, "01", "General", True)
        self.db.guardar_proveedor(self.emp, {"rut": "96792430-K", "nombre": "Sodimac"}, True)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _asientos(self):
        self.db.guardar_asiento(self.per, {"tipo": "I", "fecha": dt.date(2026, 1, 2), "glosa": "apertura"}, [
            {"codigo": "110101", "debe": 500000, "haber": 0},
            {"codigo": "410101", "debe": 0, "haber": 500000}])
        self.db.guardar_asiento(self.per, {"tipo": "E", "fecha": dt.date(2026, 2, 10), "glosa": "compra",
                                           "cdcosto": "01"}, [
            {"codigo": "310101", "debe": 119000, "haber": 0,
             "documento": {"tdocum": 11, "numero_doc": 555, "fecha_doc": "2026-02-09", "rut_prov": "96792430K",
                           "neto": 100000, "iva": 19000, "total": 119000, "detalle": "pintura"}},
            {"codigo": "110101", "debe": 0, "haber": 119000}])

    def test_descuadrado(self):
        with self.assertRaises(ErrorDatos):
            self.db.guardar_asiento(self.per, {"tipo": "T", "fecha": "2026-01-01", "glosa": "x"},
                                    [{"codigo": "110101", "debe": 10, "haber": 0}])

    def test_numeracion_y_modificacion(self):
        self._asientos()
        nums = [a["numero"] for a in self.db.asientos(self.per)]
        self.assertEqual(nums, [1, 2])
        a2 = self.db.asientos(self.per)[1]
        lineas = self.db.detalle_asiento(a2["id"])
        self.assertIsNotNone(lineas[0]["documento"])
        # modificar sin documento: la compra debe desaparecer
        for l in lineas:
            l["documento"] = None
        self.db.guardar_asiento(self.per, dict(a2), lineas, a2["id"])
        self.assertEqual(len(self.db.compras(self.per)), 0)
        self.db.borrar_asiento(a2["id"])
        self.assertEqual(self.db.q1("SELECT COUNT(*) n FROM detalle")["n"], 2)

    def test_cuentas_de_resultado_grupo_5(self):
        """Plan con resultado en el grupo 5 (ventas 51.01, costos 51.02): van a Pérdida/Ganancia y
        se cierran en la apertura; el patrimonio 23.xx sigue siendo de balance."""
        for cod, nom in [("230550", "UTILIDAD ACUMULADA"), ("510101", "VENTAS"), ("510201", "COSTO DE VENTA")]:
            self.db.guardar_cuenta(self.emp, cod, nom, False, True)
        self.db.guardar_asiento(self.per, dict(tipo="T", fecha="2026-05-01", glosa="venta"), [
            dict(codigo="110101", debe=1000, haber=0), dict(codigo="510101", debe=0, haber=1000)])
        self.db.guardar_asiento(self.per, dict(tipo="T", fecha="2026-05-02", glosa="costo"), [
            dict(codigo="510201", debe=600, haber=0), dict(codigo="110101", debe=0, haber=600)])
        b = reports.calcular_balance_8(self.db, self.emp, self.per, "2026-01-01", "2026-12-31")
        f = {x["codigo"]: x for x in b["filas"]}
        self.assertEqual((f["510101"]["ganancia"], f["510101"]["pasivo"]), (1000, 0))
        self.assertEqual((f["510201"]["perdida"], f["510201"]["activo"]), (600, 0))
        self.assertEqual(f["110101"]["activo"], 400)
        self.assertTrue(b["es_ganancia"])
        self.assertEqual(b["resultado"]["perdida"], 400)
        s = b["sumas"]
        self.assertEqual((s["activo"], s["perdida"]), (s["pasivo"], s["ganancia"]))
        sc = self.db.saldos_cierre(self.per)
        self.assertNotIn("510101", sc["saldos"])
        self.assertNotIn("510201", sc["saldos"])
        self.assertEqual(sc["resultado"], -400)                  # utilidad
        self.assertEqual(self.db.cuenta_resultado_sugerida(self.emp), "230550")

    def test_orden_lineas_al_guardar(self):
        aid = self.db.guardar_asiento(self.per, dict(tipo="T", fecha="2026-03-01", glosa="orden"), [
            dict(codigo="410101", debe=0, haber=300), dict(codigo="310101", debe=100, haber=0),
            dict(codigo="210101", debe=0, haber=50), dict(codigo="110101", debe=250, haber=0)])
        det = self.db.detalle_asiento(aid)
        self.assertEqual([(l["codigo"], l["debe"], l["haber"]) for l in det],
                         [("110101", 250, 0), ("310101", 100, 0), ("210101", 0, 50), ("410101", 0, 300)])

    def test_calculadora_y_mascara(self):
        ev = util.evaluar_expresion
        self.assertEqual(ev("119.000 / 1,19"), 100000)
        self.assertEqual(ev("1.000.000 + 250.000"), 1250000)
        self.assertEqual(ev("(100 + 50) * 2"), 300)
        self.assertEqual(ev("100.000 * 19%"), 19000)
        self.assertAlmostEqual(ev("10 / 1.19"), 8.403361, 5)        # '1.19' sin grupos de 3: decimal
        self.assertEqual(util.redondear_pesos(2.5), 3)
        self.assertEqual(util.redondear_pesos(ev("1000 / 3")), 333)
        for malo in ("", "5 +", "1 / 0", "import os", "2 ** 3"):
            with self.assertRaises(ValueError):
                ev(malo)
        self.assertEqual(util.mascara_monto("1000000"), "1.000.000")
        self.assertEqual(util.mascara_monto("1.0000"), "10.000")
        self.assertEqual(util.mascara_monto("12a3"), "123")
        self.assertEqual(util.mascara_monto(""), "")

    def test_balance_8(self):
        self._asientos()
        b = reports.calcular_balance_8(self.db, self.emp, self.per, "2026-01-01", "2026-12-31")
        t = b["totales"]
        self.assertEqual(t["debitos"], t["creditos"])
        self.assertEqual(t["deudor"], t["acreedor"])
        s = b["sumas"]
        self.assertEqual(s["activo"], s["pasivo"])
        self.assertEqual(s["perdida"], s["ganancia"])
        # Caja 381.000 deudor; ventas 500.000 ganancia; materiales 119.000 pérdida -> utilidad 381.000
        self.assertTrue(b["es_ganancia"])
        self.assertEqual(b["resultado"]["pasivo"], 381000)
        self.assertEqual(b["resultado"]["perdida"], 381000)

    def test_balance_tributario_sin_codigos(self):
        self._asientos()
        for borr, trib in [
            (reports.balance_8_columnas(self.db, self.emp, self.per, "2026-01-01", "2026-12-31"),
             reports.balance_8_columnas(self.db, self.emp, self.per, "2026-01-01", "2026-12-31", tributario=True)),
            (reports.balance_tipo_informe(self.db, self.emp, self.per, "2026-12-31"),
             reports.balance_tipo_informe(self.db, self.emp, self.per, "2026-12-31", tributario=True)),
        ]:
            codigos = {f.valores[0] for f in borr.filas if f.estilo == reports.NORMAL}
            cuentas = [f for f in trib.filas if f.estilo == reports.NORMAL]
            self.assertTrue(codigos)
            self.assertEqual([f.valores[0] for f in cuentas], list(range(1, len(cuentas) + 1)))
            textos = {t for f in trib.filas for t in trib.textos(f)}
            self.assertFalse(textos & {borr.texto_celda(0, c) for c in codigos}, "no debe mostrar códigos")
            # mismas cifras y nombres que el borrador
            self.assertEqual([f.valores[1:] for f in borr.filas], [f.valores[1:] for f in trib.filas])

    def test_informes(self):
        self._asientos()
        a = self.db.asientos(self.per)[1]
        for inf in [
            reports.comprobante(self.db, self.emp, a["id"]),
            reports.libro_diario(self.db, self.emp, self.per, "2026-01-01", "2026-12-31"),
            reports.libro_diario(self.db, self.emp, self.per, "2026-01-01", "2026-12-31", tipo="E"),
            reports.libro_mayor(self.db, self.emp, self.per, "2026-02-01", "2026-12-31"),
            reports.balance_8_columnas(self.db, self.emp, self.per, "2026-01-01", "2026-12-31"),
            reports.balance_tipo_informe(self.db, self.emp, self.per, "2026-12-31"),
            reports.balance_8_columnas(self.db, self.emp, self.per, "2026-01-01", "2026-12-31", tributario=True),
            reports.balance_tipo_informe(self.db, self.emp, self.per, "2026-12-31", tributario=True),
            reports.libro_compras(self.db, self.emp, self.per, "2026-01-01", "2026-12-31"),
            reports.listado_empresas(self.db), reports.listado_cuentas(self.db, self.emp),
            reports.listado_ccostos(self.db, self.emp), reports.listado_proveedores(self.db, self.emp),
        ]:
            self.assertTrue(inf.filas, inf.titulo)
            for f in inf.filas:
                if f.estilo != reports.GRUPO:
                    self.assertEqual(len(f.valores), len(inf.columnas), inf.titulo)
                    inf.textos(f)
            for ext in (".xlsx", ".csv"):
                ruta = reports.exportar_excel(inf, os.path.join(self.tmp.name, inf.nombre_archivo + ext))
                self.assertTrue(os.path.getsize(ruta) > 0)
        mayor = reports.libro_mayor(self.db, self.emp, self.per, "2026-02-01", "2026-12-31", "110101", "110101")
        textos = [inf_f.valores for inf_f in mayor.filas if inf_f.estilo != reports.GRUPO]
        self.assertEqual(textos[0][-1], "500.000 D")   # arrastre de enero
        self.assertEqual(textos[-1][-1], "381.000 D")  # saldo final

    def test_apertura_nuevo_ano(self):
        self._asientos()
        self.db.guardar_cuenta(self.emp, "220101", "RESULTADOS ACUMULADOS", 0, True)
        # sin cuenta para el resultado no se crea el año
        with self.assertRaises(ErrorDatos):
            self.db.crear_periodo_con_apertura(self.emp, 2027, self.per)
        self.assertEqual([p["ano"] for p in self.db.periodos(self.emp)], [2026])
        self.assertEqual(self.db.cuenta_resultado_sugerida(self.emp), "220101")

        p27 = self.db.crear_periodo_con_apertura(self.emp, 2027, self.per, "220101")
        (a,) = self.db.asientos(p27)
        self.assertEqual((a["numero"], a["tipo"], a["fecha"]), (1, "T", "2027-01-01"))
        lineas = {l["codigo"]: (l["debe"], l["haber"]) for l in self.db.detalle_asiento(a["id"])}
        # Caja 381.000 deudor; utilidad 381.000 a resultados acumulados; cuentas 3 y 4 cerradas
        self.assertEqual(lineas, {"110101": (381000, 0), "220101": (0, 381000)})

        # corregir 2026 y regenerar: reemplaza el mismo asiento, no crea otro
        self.db.guardar_asiento(self.per, {"tipo": "T", "fecha": "2026-12-31", "glosa": "deposito"}, [
            {"codigo": "110201", "debe": 100000, "haber": 0}, {"codigo": "110101", "debe": 0, "haber": 100000}])
        self.db.guardar_asiento(p27, {"tipo": "I", "fecha": "2027-01-05", "glosa": "venta"}, [
            {"codigo": "110101", "debe": 1000, "haber": 0}, {"codigo": "410101", "debe": 0, "haber": 1000}])
        aid = self.db.traspasar_apertura(self.per, p27, "220101")
        self.assertEqual(aid, a["id"])
        self.assertEqual([x["numero"] for x in self.db.asientos(p27)], [1, 2])
        lineas = {l["codigo"]: (l["debe"], l["haber"]) for l in self.db.detalle_asiento(aid)}
        self.assertEqual(lineas, {"110101": (281000, 0), "110201": (100000, 0), "220101": (0, 381000)})

        with self.assertRaises(ErrorDatos):
            self.db.traspasar_apertura(p27, self.per, "220101")      # al revés

    def test_usuarios(self):
        self.assertTrue(self.db.login("admin", "admin"))
        self.assertFalse(self.db.login("admin", "otra"))
        self.db.guardar_usuario("pepe", "Pepe", "1234", nuevo=True)
        self.assertTrue(self.db.login("PEPE", "1234"))


if __name__ == "__main__":
    unittest.main()
