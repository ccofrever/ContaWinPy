"""Calculadora para los montos de una línea del comprobante: el resultado (redondeado a pesos)
se pone en el Debe o en el Haber; se sugiere el campo donde estaba el cursor."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout

from .. import util
from . import tema

_TECLAS = [["C", "←", "(", ")"],
           ["7", "8", "9", "/"],
           ["4", "5", "6", "*"],
           ["1", "2", "3", "-"],
           ["0", ",", "=", "+"]]
_SIMBOLO = {"/": "÷", "*": "×", "-": "−"}


class Calculadora(QDialog):
    def __init__(self, parent, valor_inicial: int = 0, destino: str = "debe"):
        super().__init__(parent)
        self.setWindowTitle("Calculadora")
        self.setFixedWidth(340)
        self.destino = destino if destino in ("debe", "haber") else "debe"
        self.resultado: int | None = None
        lay = tema.margenes(QVBoxLayout(self), 6, 3)
        lay.addWidget(tema.etiqueta("Calculadora", "titulo"))

        self.expresion = QLineEdit(util.fmt_monto(valor_inicial) if valor_inicial else "")
        self.expresion.setProperty("cifra", True)
        self.expresion.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.expresion.setPlaceholderText("Ej.: 119.000 / 1,19")
        self.expresion.setMinimumHeight(40)
        lay.addWidget(self.expresion)
        self.lbl_resultado = tema.etiqueta("", "cifra-grande")
        self.lbl_resultado.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.lbl_resultado)
        self.lbl_nota = tema.etiqueta("", "ayuda")
        self.lbl_nota.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(self.lbl_nota)

        teclado = QGridLayout()
        teclado.setSpacing(tema.ESPACIO[2])
        for r, fila in enumerate(_TECLAS):
            for c, t in enumerate(fila):
                b = tema.boton(_SIMBOLO.get(t, t), variante="primario" if t == "=" else "secundario")
                b.setAutoDefault(False)
                b.setFocusPolicy(Qt.FocusPolicy.NoFocus)     # el cursor sigue en la expresión
                b.setMinimumHeight(40)
                b.clicked.connect(lambda _=False, t=t: self.tecla(t))
                teclado.addWidget(b, r, c)
        lay.addLayout(teclado)

        lay.addSpacing(tema.ESPACIO[2])
        botones = QHBoxLayout()
        botones.setSpacing(tema.ESPACIO[2])
        self.b_debe = tema.boton("Poner en el Debe", variante="primario" if self.destino == "debe" else "secundario")
        self.b_haber = tema.boton("Poner en el Haber", variante="primario" if self.destino == "haber" else "secundario")
        self.b_debe.clicked.connect(lambda: self.poner("debe"))
        self.b_haber.clicked.connect(lambda: self.poner("haber"))
        for b in (self.b_debe, self.b_haber):
            b.setAutoDefault(False)
            botones.addWidget(b, 1)
        lay.addLayout(botones)
        lay.addWidget(tema.etiqueta(f"Enter pone el resultado en el {self.destino.capitalize()} · Esc cancela",
                                    "ayuda"))

        self.expresion.textChanged.connect(lambda _: self._calcular())
        self.expresion.returnPressed.connect(lambda: self.poner(self.destino))
        self._calcular()
        self.expresion.setFocus()

    def tecla(self, t: str):
        e = self.expresion
        if t == "C":
            e.clear()
        elif t == "←":
            e.backspace()
        elif t == "=":
            v = self._valor()
            if v is not None:
                e.setText(util.fmt_monto(v))
        else:
            e.insert(t)
        e.setFocus()

    def _valor(self) -> int | None:
        try:
            v = util.evaluar_expresion(self.expresion.text())
        except ValueError:
            return None
        return util.redondear_pesos(v)

    def _calcular(self):
        texto = self.expresion.text().strip()
        try:
            v = util.evaluar_expresion(texto) if texto else 0
        except ValueError as e:
            self.lbl_resultado.setText("")
            self.lbl_nota.setText(str(e))
            tema.marcar(self.lbl_nota, estado="error")
            for b in (self.b_debe, self.b_haber):
                b.setEnabled(False)
            return
        n = util.redondear_pesos(v)
        self.lbl_resultado.setText(f"= {util.fmt_monto(n)}")
        self.lbl_nota.setText(f"Redondeado a pesos (resultado exacto {util.fmt_decimal(v)})" if n != v else "")
        tema.marcar(self.lbl_nota, estado="")
        valido = n > 0
        for b in (self.b_debe, self.b_haber):
            b.setEnabled(valido)
            b.setToolTip("" if valido else "El resultado debe ser mayor que cero")

    def poner(self, destino: str):
        v = self._valor()
        if v is None or v <= 0:
            return
        self.resultado, self.destino = v, destino
        self.accept()
