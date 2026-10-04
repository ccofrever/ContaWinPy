"""PySide6 simulado SOLO para pruebas automáticas sin pantalla.

Implementa el comportamiento mínimo (estado de campos, combos, tablas, señales,
diálogos scriptables, impresora que registra lo dibujado) para ejecutar la
lógica de la interfaz de ContaWin sin tener Qt instalado.
"""
from __future__ import annotations

import datetime as _dt

# ---------------------------------------------------------------- registro de pruebas
HANDLERS: dict[str, object] = {}     # nombre de clase de diálogo -> fn(dialogo) -> resultado exec
MENSAJES: list[tuple[str, str]] = []  # (tipo, texto)
RESPUESTAS = {"question": "Yes", "file": "", "dir": "", "int": (2030, True), "text": ("", True)}
PAGINAS: list[int] = []


class _NS(int):
    """Enum/namespace universal: Qt.AlignmentFlag.AlignRight -> entero combinable."""

    def __new__(cls, name="", value=None):
        o = int.__new__(cls, value if value is not None else (abs(hash(name)) % 100000) + 2)
        o._name = name
        return o

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _NS(f"{self._name}.{name}")

    def __or__(self, other):
        return _NS(f"{self._name}|", int(self) | int(other))

    __ror__ = __or__

    def __call__(self, *a, **k):
        return _Dummy()


class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _NS(f"{cls.__name__}.{name}")


class _Dummy:
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Dummy()

    def __call__(self, *a, **k):
        return _Dummy()

    def __bool__(self):
        return True


class Signal:
    def __init__(self, *a, **k):
        self._slots = []

    def connect(self, fn):
        self._slots.append(fn)

    def emit(self, *args):
        for fn in list(self._slots):
            try:
                fn(*args)
            except TypeError:
                fn()


SIGNALS = {"clicked", "textChanged", "textEdited", "editingFinished", "currentIndexChanged", "toggled",
           "doubleClicked", "accepted", "rejected", "activated", "triggered", "dateChanged", "paintRequested"}


class QObject(metaclass=_Meta):
    def __init__(self, *a, **k):
        self._signals = {}
        self._blocked = False
        for nombre, fn in k.items():
            if nombre in SIGNALS:
                getattr(self, nombre).connect(fn)

    def __getattr__(self, name):
        if name.startswith("__") or name in ("_signals", "_blocked"):
            raise AttributeError(name)
        if name in SIGNALS:
            s = self.__dict__.setdefault("_signals", {})
            if name not in s:
                s[name] = Signal()
            return s[name]
        return _Dummy()

    def blockSignals(self, b):
        self._blocked = b

    def _emit(self, name, *args):
        if not getattr(self, "_blocked", False):
            getattr(self, name).emit(*args)


# ---------------------------------------------------------------- QtCore
class Qt(metaclass=_Meta):
    pass


class QDate:
    def __init__(self, y=2000, m=1, d=1):
        self._d = _dt.date(y, m, d)

    def year(self):
        return self._d.year

    def month(self):
        return self._d.month

    def day(self):
        return self._d.day


class QRectF:
    def __init__(self, x=0, y=0, w=0, h=0):
        self.x, self.y, self.w, self.h = x, y, w, h


class QRect(QRectF):
    def width(self):
        return self.w

    def height(self):
        return self.h


class QSize(_Dummy):
    pass


class QMarginsF(_Dummy):
    pass


class QRegularExpression(_Dummy):
    pass


class QUrl(_Dummy):
    @staticmethod
    def fromLocalFile(p):
        return p


class QLocale(metaclass=_Meta):
    def __init__(self, *a):
        pass

    @staticmethod
    def setDefault(x):
        pass


# ---------------------------------------------------------------- QtGui
class QFont:
    def __init__(self, *a):
        pass

    def setPointSizeF(self, x):
        self.size = x

    def setBold(self, b):
        self.bold = b


class QFontMetricsF:
    def __init__(self, font, dev=None):
        pass

    def height(self):
        return 30.0

    def horizontalAdvance(self, t):
        return 15.0 * len(t)

    def elidedText(self, t, mode, w):
        return t


class QColor(_Dummy):
    pass


class QPen(_Dummy):
    def setWidthF(self, w):
        assert w > 0


class QIcon(_Dummy):
    pass


class QKeySequence(_Dummy):
    pass


class QRegularExpressionValidator(_Dummy):
    pass


class QDesktopServices:
    abiertos: list = []

    @staticmethod
    def openUrl(u):
        QDesktopServices.abiertos.append(u)


class QAction(QObject):
    def __init__(self, icon=None, text="", parent=None):
        super().__init__()
        self.text = text

    def trigger(self):
        self._emit("triggered")


class QShortcut(QObject):
    def __init__(self, key=None, parent=None, **k):
        super().__init__(**k)

    def setContext(self, c):
        pass


class QPainter:
    def begin(self, dev):
        self.dev = dev
        return True

    def end(self):
        pass

    def device(self):
        return self.dev

    def setFont(self, f):
        pass

    def setPen(self, p):
        pass

    def drawText(self, rect, flags, text):
        assert isinstance(text, str)
        assert rect.y + rect.h <= self.dev.H + 1, f"texto fuera de la página: {text!r} y={rect.y}"
        self.dev.textos.append(text)

    def drawLine(self, *a):
        assert all(isinstance(v, int) for v in a)


class QPageLayout(metaclass=_Meta):
    pass


class QPageSize(metaclass=_Meta):
    def __init__(self, *a):
        pass


# ---------------------------------------------------------------- QtPrintSupport
class QPrinter(metaclass=_Meta):
    H = 2400

    def __init__(self, *a):
        self.paginas = 1
        self.textos = []
        self.archivo = None

    def pageLayout(self):
        p = self

        class _L:
            def paintRectPixels(self, res):
                return QRect(0, 0, 3200 if getattr(p, "horiz", False) else 2500, p.H)
        return _L()

    def resolution(self):
        return 300

    def logicalDpiY(self):
        return 300

    def newPage(self):
        self.paginas += 1
        return True

    def setPageOrientation(self, o):
        self.horiz = "Landscape" in getattr(o, "_name", "")

    def setOutputFileName(self, f):
        self.archivo = f
        with open(f, "wb") as fh:
            fh.write(b"%PDF-fake")

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Dummy()


# ---------------------------------------------------------------- QtWidgets
class QApplication(QObject):
    def __init__(self, *a):
        super().__init__()

    @staticmethod
    def setOverrideCursor(c):
        pass

    @staticmethod
    def restoreOverrideCursor():
        pass

    @staticmethod
    def processEvents():
        pass


class QWidget(QObject):
    def __init__(self, *a, **k):
        super().__init__(**{x: y for x, y in k.items() if x in SIGNALS})
        self._enabled = True
        self._visible = True

    def setEnabled(self, b):
        self._enabled = bool(b)

    def isEnabled(self):
        return self._enabled


class QLabel(QWidget):
    def __init__(self, text="", parent=None):
        super().__init__()
        self._text = text

    def setText(self, t):
        self._text = t

    def text(self):
        return self._text


class QLineEdit(QWidget):
    def __init__(self, text="", parent=None):
        super().__init__()
        self._text = text if isinstance(text, str) else ""
        self._ro = False
        self._pos = 0
        self._max = 32767

    def text(self):
        return self._text

    def setText(self, t):
        self._text = (t or "")[: self._max]
        self._emit("textChanged", self._text)

    def clear(self):
        self.setText("")

    def setMaxLength(self, n):
        self._max = n

    def setReadOnly(self, b):
        self._ro = b

    def isReadOnly(self):
        return self._ro

    def cursorPosition(self):
        return self._pos

    def setCursorPosition(self, p):
        self._pos = p

    # simulación de tipeo del usuario
    def teclear(self, t):
        assert not self._ro, "se intentó escribir en un campo de solo lectura"
        self._text = t[: self._max]
        self._emit("textEdited", self._text)
        self._emit("textChanged", self._text)
        self._emit("editingFinished")


class QPlainTextEdit(QLineEdit):
    pass


class QCheckBox(QWidget):
    def __init__(self, text="", parent=None):
        super().__init__()
        self._c = False

    def isChecked(self):
        return self._c

    def setChecked(self, b):
        self._c = bool(b)
        self._emit("toggled", self._c)


class QSpinBox(QWidget):
    def __init__(self, *a):
        super().__init__()
        self._v = 0

    def value(self):
        return self._v

    def setValue(self, v):
        self._v = v


class QDateEdit(QWidget):
    def __init__(self, *a):
        super().__init__()
        self._d = QDate()

    def date(self):
        return self._d

    def setDate(self, d):
        self._d = d
        self._emit("dateChanged", d)


class QComboBox(QWidget):
    def __init__(self, *a):
        super().__init__()
        self._items = []
        self._cur = -1
        self._edit = ""
        self._editable = False

    def setEditable(self, b):
        self._editable = b

    def addItem(self, text, data=None):
        self._items.append((text, data))
        if self._cur < 0:
            self.setCurrentIndex(0)

    def clear(self):
        self._items = []
        self._cur = -1
        self._edit = ""

    def count(self):
        return len(self._items)

    def itemData(self, i):
        return self._items[i][1] if 0 <= i < len(self._items) else None

    def itemText(self, i):
        return self._items[i][0]

    def findData(self, d):
        for i, (_, x) in enumerate(self._items):
            if x == d:
                return i
        return -1

    def findText(self, t, flags=None):
        for i, (x, _) in enumerate(self._items):
            if x == t:
                return i
        return -1

    def currentIndex(self):
        return self._cur

    def setCurrentIndex(self, i):
        self._cur = i
        self._edit = self._items[i][0] if 0 <= i < len(self._items) else ""
        self._emit("currentIndexChanged", i)

    def currentText(self):
        return self._edit

    def setEditText(self, t):
        self._edit = t

    def currentData(self):
        return self.itemData(self._cur)

    def teclear(self, t):
        self._edit = t
        i = self.findText(t)
        if i >= 0:
            self._cur = i


class QTableWidgetItem:
    def __init__(self, text=""):
        self._t = text
        self._data = {}

    def text(self):
        return self._t

    def setData(self, role, v):
        self._data[int(role)] = v

    def data(self, role):
        return self._data.get(int(role))

    def setTextAlignment(self, a):
        pass

    def font(self):
        return QFont()

    def setFont(self, f):
        pass

    def setBackground(self, c):
        pass


class QTableWidget(QWidget):
    def __init__(self, rows=0, cols=0, parent=None):
        super().__init__()
        self._rows = [[None] * cols for _ in range(rows)]
        self._cols = cols
        self._cur = -1
        self._hidden = set()

    def setRowCount(self, n):
        self._rows = (self._rows + [[None] * self._cols for _ in range(n)])[:n]
        self._hidden = {h for h in self._hidden if h < n}
        if self._cur >= n:
            self._cur = -1

    def rowCount(self):
        return len(self._rows)

    def columnCount(self):
        return self._cols

    def setItem(self, r, c, it):
        self._rows[r][c] = it

    def item(self, r, c):
        return self._rows[r][c]

    def currentRow(self):
        return self._cur

    def selectRow(self, r):
        self._cur = r

    def setRowHidden(self, r, b):
        (self._hidden.add if b else self._hidden.discard)(r)

    def isRowHidden(self, r):
        return r in self._hidden


class QDialog(QWidget):
    def __init__(self, *a, **k):
        super().__init__()
        self._result = 0

    def exec(self):
        for cls in type(self).__mro__:
            h = HANDLERS.get(cls.__name__)
            if h:
                r = h(self)
                return self._result if r is None else r
        return 0

    def accept(self):
        self._result = 1

    def reject(self):
        self._result = 0

    def resize(self, *a):
        pass


class QMainWindow(QWidget):
    def __init__(self, *a):
        super().__init__()
        self._status = QLabel()

    def statusBar(self):
        s = self._status

        class _S:
            def showMessage(self, t):
                s.setText(t)
        return _S()

    def close(self):
        return True


class QMessageBox(metaclass=_Meta):
    @staticmethod
    def question(parent, titulo, texto, *a):
        MENSAJES.append(("question", texto))
        return getattr(QMessageBox.StandardButton, RESPUESTAS["question"])

    @staticmethod
    def information(parent, titulo, texto):
        MENSAJES.append(("info", texto))

    @staticmethod
    def warning(parent, titulo, texto):
        MENSAJES.append(("warning", texto))

    @staticmethod
    def critical(parent, titulo, texto):
        MENSAJES.append(("critical", texto))

    @staticmethod
    def about(parent, titulo, texto):
        MENSAJES.append(("about", texto))


class QFileDialog(metaclass=_Meta):
    @staticmethod
    def getSaveFileName(*a):
        return RESPUESTAS["file"], ""

    @staticmethod
    def getExistingDirectory(*a):
        return RESPUESTAS["dir"]


class QInputDialog(metaclass=_Meta):
    @staticmethod
    def getInt(*a):
        return RESPUESTAS["int"]

    @staticmethod
    def getText(*a):
        return RESPUESTAS["text"]


class QPrintPreviewDialog(QDialog):
    def __init__(self, printer, parent=None):
        super().__init__()
        self.printer = printer

    def exec(self):
        self.paintRequested.emit(self.printer)
        PAGINAS.append(self.printer.paginas)
        return 1


class QPrintDialog(QDialog):
    def exec(self):
        return 1
