"""Diálogo del asiento de apertura: vista previa de los saldos del balance del año
anterior y elección de la cuenta de patrimonio que recibe el resultado del ejercicio.

Usa la lógica de db.py (saldos_cierre / lineas_apertura / traspasar_apertura /
crear_periodo_con_apertura)."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from .. import apertura, util
from ..db import Database, ErrorDatos
from . import tema
from .comunes import Buscador, Tabla, confirmar, error, info


class AperturaDialog(QDialog):
    """origen: periodo del año anterior (fila de BD). ano_destino: año que se abre.
    Si se acepta, deja la cuenta elegida en self.cuenta_resultado (None si no hay resultado).
    Con permitir_omitir=True agrega «Crear sin apertura» (self.omitido = True)."""

    def __init__(self, parent, db: Database, empresa_id: int, origen, ano_destino: int,
                 periodo_destino_id: int | None = None, permitir_omitir: bool = False):
        super().__init__(parent)
        self.db, self.empresa_id, self.origen = db, empresa_id, origen
        self.ano_destino, self.periodo_destino_id = ano_destino, periodo_destino_id
        self.cuenta_resultado: str | None = None
        self.omitido = False
        self.sc = db.saldos_cierre(origen["id"])
        self.nombres = {c["codigo"]: c["nombre"] for c in db.cuentas(empresa_id)}
        emp = db.empresa(empresa_id)
        descuadrados = db.q1("SELECT COUNT(*) n FROM asiento WHERE periodo_id=? AND debe<>haber",
                             (origen["id"],))["n"]

        self.setWindowTitle(f"Asiento de apertura {ano_destino}")
        self.resize(820, 640)
        lay = tema.margenes(QVBoxLayout(self))
        lay.addWidget(tema.etiqueta(f"Asiento de apertura {ano_destino}", "titulo"))
        lay.addWidget(tema.etiqueta(f"{emp['razon_social']} · Saldos del balance al 31-12-{origen['ano']}",
                                    "secundario"))
        avisos = []
        if descuadrados:
            avisos.append(f"⚠ El año {origen['ano']} tiene {descuadrados} comprobante(s) descuadrado(s); "
                          "corrígelos o la apertura no cuadrará.")
        previo = db.asiento_apertura(periodo_destino_id) if periodo_destino_id else None
        if previo:
            avisos.append(f"Se reemplazará el asiento de apertura N° {previo['numero']} ya existente.")
        for t in avisos:
            av = QLabel(t)
            av.setWordWrap(True)
            tema.marcar(av, estado="aviso")
            lay.addWidget(av)

        lay.addWidget(tema.etiqueta("Cuenta de patrimonio donde se traspasa el resultado", "etiqueta"))
        self.cuenta = Buscador()
        self.cuenta.set_items([(c["codigo"], c["nombre"]) for c in db.cuentas(empresa_id)
                               if not util.es_cuenta_resultado(c["codigo"])], util.formato_codigo)
        self.cuenta.set_codigo(db.cuenta_resultado_sugerida(empresa_id))
        lay.addWidget(self.cuenta)
        lay.addWidget(tema.etiqueta(apertura.resumen_resultado(self.sc["resultado"]), "ayuda"))
        if not self.sc["resultado"]:
            self.cuenta.setEnabled(False)

        self.tabla = Tabla([("Código", 100, "L"), ("Cuenta", 0, "L"), ("Debe", 150, "R"), ("Haber", 150, "R")],
                           self)
        lay.addWidget(self.tabla, 1)
        tot = QHBoxLayout()
        tot.setSpacing(tema.ESPACIO[2])
        self.lbl_estado = QLabel()
        tot.addWidget(self.lbl_estado)
        tot.addStretch()
        tot.addWidget(tema.etiqueta("Totales", "etiqueta"))
        self.tot_debe, self.tot_haber = QLineEdit(), QLineEdit()
        for w in (self.tot_debe, self.tot_haber):
            w.setReadOnly(True)
            w.setProperty("cifra", True)
            w.setFixedWidth(150)
            tot.addWidget(w)
        lay.addLayout(tot)

        bot = QHBoxLayout()
        bot.setSpacing(tema.ESPACIO[2])
        bot.addStretch()
        if permitir_omitir:
            b_omitir = tema.boton("Crear el año sin apertura")
            b_omitir.setAutoDefault(False)
            b_omitir.clicked.connect(self._omitir)
            bot.addWidget(b_omitir)
        b_cancelar = tema.boton("Cancelar")
        b_cancelar.setAutoDefault(False)
        b_cancelar.clicked.connect(self.reject)
        bot.addWidget(b_cancelar)
        b_ok = tema.boton("Traspasar saldos", "importar", "primario")
        b_ok.clicked.connect(self._aceptar)
        bot.addWidget(b_ok)
        lay.addLayout(bot)
        self.cuenta.currentIndexChanged.connect(lambda _: self._previa())
        self._previa()

    def _codigo(self) -> str | None:
        return (self.cuenta.codigo() or None) if self.sc["resultado"] else None

    def _previa(self):
        try:
            det = self.db.lineas_apertura(self.origen["id"], self._codigo())
            falta = False
        except ErrorDatos:            # falta la cuenta del resultado: muestra solo los saldos
            det = [{"codigo": c, "debe": max(s, 0), "haber": max(-s, 0)} for c, s in sorted(self.sc["saldos"].items())]
            falta = True
        filas = [[util.formato_codigo(l["codigo"]), self.nombres.get(l["codigo"], "(cuenta no existe)"),
                  util.fmt_monto(l["debe"], True), util.fmt_monto(l["haber"], True)] for l in det]
        self.tabla.cargar(filas, list(range(len(filas))))
        td, th = sum(l["debe"] for l in det), sum(l["haber"] for l in det)
        self.tot_debe.setText(util.fmt_pesos(td))
        self.tot_haber.setText(util.fmt_pesos(th))
        if falta:
            self.lbl_estado.setText("Falta elegir la cuenta para el resultado")
            tema.marcar(self.lbl_estado, estado="error")
        elif td == th:
            self.lbl_estado.setText(f"✓ Cuadrado · {len(det)} cuentas")
            tema.marcar(self.lbl_estado, estado="ok")
        else:
            self.lbl_estado.setText(f"⚠ Descuadrado · Diferencia {util.fmt_pesos(abs(td - th))}")
            tema.marcar(self.lbl_estado, estado="error")

    def _omitir(self):
        self.omitido = True
        self.accept()

    def _aceptar(self):
        cod = self._codigo()
        if self.sc["resultado"] and not cod:
            error(self, "Elige la cuenta de patrimonio donde se traspasa el resultado del ejercicio.")
            return
        if cod and cod[:1] == "1" and not confirmar(
                self, f"La cuenta {util.formato_codigo(cod)} {self.nombres.get(cod, '')} es de activo.\n"
                      "El resultado normalmente va a una cuenta de patrimonio (resultados acumulados).\n\n"
                      "¿Usarla de todas formas?", "Cuenta del resultado"):
            return
        self.cuenta_resultado = cod
        if self.periodo_destino_id is not None:       # año existente: traspasa ahora
            try:
                aid = self.db.traspasar_apertura(self.origen["id"], self.periodo_destino_id, cod)
            except ErrorDatos as e:
                error(self, str(e))
                return
            a = self.db.asiento(aid)
            info(self, f"Asiento de apertura N° {a['numero']} guardado ({util.fmt_pesos(a['debe'])}).",
                 "Asiento de apertura")
        self.accept()


def abrir(parent, db: Database, empresa_id: int, periodo_id: int) -> bool:
    """Genera o regenera la apertura del año periodo_id. True si se grabó."""
    per = db.periodo(periodo_id)
    origen = db.periodo_anterior(empresa_id, per["ano"])
    if not origen:
        error(parent, f"No hay un año anterior a {per['ano']}: no hay saldos que traspasar.")
        return False
    dlg = AperturaDialog(parent, db, empresa_id, origen, per["ano"], periodo_id)
    return bool(dlg.exec())


def crear_ano(parent, db: Database, empresa_id: int, ano: int) -> int | None:
    """Crea el año; si hay un año anterior con saldos, ofrece traspasarlos (apertura).
    Devuelve el id del periodo creado, o None si se canceló."""
    origen = db.periodo_anterior(empresa_id, ano)
    hay_saldos = False
    if origen:
        sc = db.saldos_cierre(origen["id"])
        hay_saldos = bool(sc["saldos"] or sc["resultado"])
    if not hay_saldos:
        return db.crear_periodo(empresa_id, ano)
    dlg = AperturaDialog(parent, db, empresa_id, origen, ano, permitir_omitir=True)
    if not dlg.exec():
        return None
    if dlg.omitido:
        return db.crear_periodo(empresa_id, ano)
    pid = db.crear_periodo_con_apertura(empresa_id, ano, origen["id"], dlg.cuenta_resultado)
    a = db.asiento_apertura(pid)
    if a:
        info(parent, f"Año {ano} creado con el asiento de apertura N° {a['numero']} "
                     f"({util.fmt_pesos(a['debe'])}).", "Asiento de apertura")
    return pid
