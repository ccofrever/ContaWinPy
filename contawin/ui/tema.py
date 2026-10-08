"""Sistema de diseño ContaWin aplicado a Qt.

Traduce los tokens del sistema de diseño «ContaWin» (colores claro/oscuro, tipografía,
espacios, radios) a una hoja de estilo Qt, una paleta, fuentes e íconos de línea.

Uso:
    from contawin.ui import tema
    tema.aplicar(app, "claro")          # o "oscuro" / "automatico"
    tema.color("brand")                 # "#0F6B66"
    tema.icono("comprobante")           # QIcon de línea en ink-muted
    tema.fuente_mono()                  # QFont para montos, códigos y RUT

Fuentes: el sistema usa IBM Plex Sans / IBM Plex Mono. Si se copian los archivos
.ttf/.otf en la carpeta contawin/fuentes se cargan solos; si no, se usa Segoe UI y
Consolas (los respaldos definidos en el sistema).
"""
from __future__ import annotations

import glob
import os
import tempfile

# ---------------------------------------------------------------------------
# Tokens (copiados de tokens.json del sistema de diseño ContaWin)
# ---------------------------------------------------------------------------
COLORES: dict[str, dict[str, str]] = {
    "claro": {
        "surface-100": "#F5F7F6", "surface-200": "#FFFFFF", "surface-300": "#E8EEEC",
        "border": "#D3DCDA", "border-strong": "#8A9995",
        "ink": "#13201F", "ink-muted": "#56645F",
        "brand": "#0F6B66", "brand-strong": "#0A4F4B", "brand-subtle": "#D6EBE8", "on-brand": "#FFFFFF",
        "accent": "#C7781A", "accent-subtle": "#FBEBD4",
        "positive": "#1E7A3C", "negative": "#B3261E",
    },
    "oscuro": {
        "surface-100": "#111716", "surface-200": "#182120", "surface-300": "#1F2A29",
        "border": "#2E3B39", "border-strong": "#5E6E6A",
        "ink": "#E8EFEE", "ink-muted": "#9AABA7",
        "brand": "#3FB8AE", "brand-strong": "#7BD4CB", "brand-subtle": "#1C3D3A", "on-brand": "#0B1514",
        "accent": "#E8A04A", "accent-subtle": "#3A2A14",
        "positive": "#5BC27A", "negative": "#F2827A",
    },
}
for _t in COLORES.values():
    _t["focus"] = _t["brand"]

FAMILIA_SANS = ["IBM Plex Sans", "Segoe UI", "Arial"]
FAMILIA_MONO = ["IBM Plex Mono", "Consolas", "Courier New"]

# escala tipográfica (px, peso)
TEXTO = {
    "display": (32, 600), "title": (20, 600), "heading": (16, 600),
    "body": (14, 400), "label": (13, 500), "caption": (12, 400),
    "amount": (14, 500), "code": (13, 400),
}
ESPACIO = {1: 4, 2: 8, 3: 12, 4: 16, 6: 24, 8: 32}
RADIO = {"sm": 4, "md": 6, "lg": 10}
ALTO_CONTROL = 36
ANCHO_BARRA_LATERAL = 232

_actual = "claro"


def nombre_tema() -> str:
    return _actual


def color(nombre: str) -> str:
    """Valor hexadecimal de un token de color en el tema actual."""
    return COLORES[_actual][nombre]


def qcolor(nombre: str):
    from PySide6.QtGui import QColor
    return QColor(color(nombre))


# ---------------------------------------------------------------------------
# Fuentes
# ---------------------------------------------------------------------------
def _carpeta_fuentes() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fuentes")


def cargar_fuentes() -> int:
    """Registra los .ttf/.otf de contawin/fuentes (IBM Plex). Devuelve cuántos cargó."""
    try:
        from PySide6.QtGui import QFontDatabase
    except ImportError:
        return 0
    n = 0
    for patron in ("*.ttf", "*.otf"):
        for ruta in glob.glob(os.path.join(_carpeta_fuentes(), patron)):
            try:
                if QFontDatabase.addApplicationFont(ruta) >= 0:
                    n += 1
            except Exception:  # noqa: BLE001
                pass
    return n


def _fuente(familias: list[str], px: int, peso: int):
    from PySide6.QtGui import QFont
    f = QFont()
    try:
        f.setFamilies(familias)
    except Exception:  # noqa: BLE001
        f.setFamily(familias[0])
    f.setPixelSize(px)
    try:
        f.setWeight(QFont.Weight(peso))
    except Exception:  # noqa: BLE001
        f.setBold(peso >= 600)
    return f


def fuente(estilo: str = "body"):
    """QFont sans del estilo indicado (display, title, heading, body, label, caption)."""
    px, peso = TEXTO[estilo]
    return _fuente(FAMILIA_SANS, px, peso)


def fuente_mono(estilo: str = "amount"):
    """QFont monoespaciada con cifras tabulares, para montos, códigos y RUT."""
    px, peso = TEXTO[estilo]
    return _fuente(FAMILIA_MONO, px, peso)


# ---------------------------------------------------------------------------
# Íconos de línea (1.5 px, 24×24, esquinas redondeadas)
# ---------------------------------------------------------------------------
_TRAZOS = {
    "inicio": '<path d="M4 11l8-7 8 7v8a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z"/>',
    "empresa": '<rect x="4" y="3" width="16" height="18" rx="2"/>'
               '<path d="M9 7h1M14 7h1M9 11h1M14 11h1M9 15h1M14 15h1M10 21v-3h4v3"/>',
    "comprobante": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
    "cuentas": '<path d="M4 5v14M4 5h3M4 12h3M4 19h3M10 5h10M10 12h10M10 19h10"/>',
    "proveedor": '<path d="M3 6h11v10H3z"/><path d="M14 9h4l3 3v4h-7"/>'
                 '<circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
    "ccosto": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 12h.01"/>',
    "balance": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 4v16M15 4v16"/>',
    "informe": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
               '<path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "diario": '<path d="M5 19.5V4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5 1.5 1.5 0 0 0 6.5 21H19v-3"/>'
              '<path d="M9 8h6M9 12h4"/>',
    "tipo": '<path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z"/><circle cx="8" cy="8" r="1.5"/>',
    "mayor": '<path d="M12 4v16M8 20h8M5 7h14"/><path d="M5 7l-3 6a3 3 0 0 0 6 0zM19 7l-3 6a3 3 0 0 0 6 0z"/>',
    "compras": '<path d="M3 4h2l2.4 11h10.2L20 8H6.2"/><circle cx="9" cy="19" r="1.5"/><circle cx="17" cy="19" r="1.5"/>',
    "usuarios": '<circle cx="9" cy="8" r="3.5"/><path d="M3 20a6 6 0 0 1 12 0"/>'
                '<path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14.5a6 6 0 0 1 3 5.5"/>',
    "importar": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    "respaldar": '<rect x="3" y="4" width="18" height="5" rx="1"/>'
                 '<path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "salir": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
    "cambiar": '<path d="M4 8h14l-3-3M20 16H6l3 3"/>',
    "mas": '<path d="M12 5v14M5 12h14"/>',
    "editar": '<path d="M16 4l4 4L8 20H4v-4z"/>',
    "borrar": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
    "imprimir": '<path d="M7 9V3h10v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M7 14h10v7H7z"/>',
    "excel": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M4 9h16M4 15h16M10 9v12"/>',
    "guardar": '<path d="M5 3h11l3 3v13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z"/><path d="M8 3v5h7M8 21v-6h8v6"/>',
    "cerrar": '<path d="M6 6l12 12M18 6L6 18"/>',
    "buscar": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "ojo": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "ojo_cerrado": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'
                   '<path d="M4 4l16 16"/>',
    "ok": '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
    "alerta": '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
    "calculadora": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8"/>'
                   '<path d="M8 11h.01M12 11h.01M16 11h.01M8 14h.01M12 14h.01M16 14h.01M8 17h.01M12 17h4"/>',
    "calendario": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "imagen": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="9.5" r="1.5"/>'
              '<path d="M21 16l-5-5-9 9"/>',
    "vista": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "chevron_abajo": '<path d="M6 9l6 6 6-6"/>',
    "chevron_izquierda": '<path d="M15 6l-6 6 6 6"/>',
    "chevron_derecha": '<path d="M9 6l6 6-6 6"/>',
    "chevron_arriba": '<path d="M6 15l6-6 6 6"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
}

# nombres de QStyle.StandardPixmap usados antes -> ícono del sistema
EQUIVALENCIAS = {
    "SP_FileIcon": "mas", "SP_FileDialogDetailedView": "editar", "SP_TrashIcon": "borrar",
    "SP_DialogSaveButton": "guardar", "SP_FileDialogContentsView": "imprimir", "SP_DialogCloseButton": "cerrar",
    "SP_DirOpenIcon": "empresa", "SP_FileDialogListView": "comprobante", "SP_DirHomeIcon": "proveedor",
    "SP_DirLinkIcon": "ccosto", "SP_ComputerIcon": "empresa", "SP_FileDialogInfoView": "balance",
    "SP_FileLinkIcon": "tipo", "SP_DriveHDIcon": "mayor", "SP_DialogApplyButton": "compras",
    "SP_DialogYesButton": "usuarios", "SP_ArrowDown": "importar", "SP_MessageBoxInformation": "info",
}


def _carpeta_iconos() -> str:
    c = os.path.join(tempfile.gettempdir(), "contawin_iconos")
    os.makedirs(c, exist_ok=True)
    return c


def ruta_svg(nombre: str, color_hex: str, grosor: float = 1.5) -> str:
    """Escribe (una vez) el SVG del ícono en el color pedido y devuelve su ruta con '/'."""
    nombre = EQUIVALENCIAS.get(nombre, nombre)
    trazo = _TRAZOS.get(nombre, _TRAZOS["info"])
    archivo = os.path.join(_carpeta_iconos(), f"{nombre}_{color_hex.lstrip('#').lower()}_{grosor:g}.svg")
    if not os.path.exists(archivo):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
               f'stroke="{color_hex}" stroke-width="{grosor:g}" stroke-linecap="round" stroke-linejoin="round">'
               f'{trazo}</svg>')
        try:
            with open(archivo, "w", encoding="utf-8") as f:
                f.write(svg)
        except OSError:
            pass
    return archivo.replace("\\", "/")


def icono(nombre: str, token: str = "ink-muted"):
    """QIcon de línea. token: color del sistema (ink-muted por defecto, brand si está activo)."""
    from PySide6.QtGui import QIcon
    ic = QIcon(ruta_svg(nombre, color(token)))
    try:
        ic.addFile(ruta_svg(nombre, color("border-strong")), mode=QIcon.Mode.Disabled)
    except Exception:  # noqa: BLE001
        pass
    return ic


# ---------------------------------------------------------------------------
# Hoja de estilo
# ---------------------------------------------------------------------------
def hoja_de_estilo(t: dict[str, str] | None = None) -> str:
    c = dict(t or COLORES[_actual])
    sans = ", ".join(f'"{f}"' for f in FAMILIA_SANS)
    mono = ", ".join(f'"{f}"' for f in FAMILIA_MONO)
    flecha = ruta_svg("chevron_abajo", c["ink-muted"])
    flecha_arriba = ruta_svg("chevron_arriba", c["ink-muted"])
    check = ruta_svg("check", c["on-brand"], 2.5)
    c.update(sans=sans, mono=mono, flecha=flecha, flecha_arriba=flecha_arriba, check=check)
    return """
* {{ font-family: {sans}; font-size: 14px; }}
QWidget {{ color: {ink}; }}
QMainWindow, QDialog, QMessageBox {{ background: {surface-100}; }}
QToolTip {{ background: {ink}; color: {surface-200}; border: 0; padding: 4px 8px; border-radius: 4px; }}

/* ---------- textos ---------- */
QLabel {{ background: transparent; }}
QLabel[rol="display"] {{ font-size: 32px; font-weight: 600; }}
QLabel[rol="titulo"] {{ font-size: 20px; font-weight: 600; }}
QLabel[rol="encabezado"] {{ font-size: 16px; font-weight: 600; }}
QLabel[rol="etiqueta"] {{ font-size: 13px; font-weight: 500; }}
QLabel[rol="ayuda"] {{ font-size: 12px; color: {ink-muted}; }}
QLabel[rol="secundario"] {{ color: {ink-muted}; }}
QLabel[rol="marca"] {{ font-size: 16px; font-weight: 600; color: {brand-strong}; }}
QLabel[rol="seccion"] {{ font-size: 12px; font-weight: 600; color: {ink-muted}; padding: 12px 12px 4px 12px; }}
QLabel[rol="cifra"] {{ font-family: {mono}; font-weight: 500; }}
QLabel[rol="cifra-grande"] {{ font-family: {mono}; font-size: 20px; font-weight: 600; }}
QLabel[estado="ok"] {{ color: {positive}; font-weight: 600; }}
QLabel[estado="error"] {{ color: {negative}; font-weight: 600; }}
QLabel[estado="aviso"] {{ color: {ink}; background: {accent-subtle}; border-radius: 4px; padding: 4px 8px; }}
QLabel[chip="true"] {{ background: {brand-subtle}; color: {ink}; border-radius: 4px; padding: 2px 8px;
                      font-size: 13px; font-weight: 500; }}
QLabel#totalOk {{ color: {positive}; font-weight: 600; }}
QLabel#totalMal {{ color: {negative}; font-weight: 600; }}

/* ---------- superficies ---------- */
QFrame[tarjeta="true"] {{ background: {surface-200}; border: 1px solid {border}; border-radius: 10px; }}
QFrame[tarjeta="true"] QLabel {{ border: 0; }}
QGroupBox {{ background: {surface-200}; border: 1px solid {border}; border-radius: 10px;
            margin-top: 0; padding: 12px; }}
QFrame#barraLateral {{ background: {surface-300}; border: 0; border-right: 1px solid {border}; }}
QFrame#cabecera {{ background: {surface-200}; border: 0; border-bottom: 1px solid {border}; }}
QScrollArea {{ background: transparent; border: 0; }}
QWidget#qt_scrollarea_viewport {{ background: transparent; }}
QWidget#lienzo {{ background: {surface-100}; }}
QWidget#navLista {{ background: transparent; }}
QFrame[linea="true"] {{ background: {border}; border: 0; max-height: 1px; min-height: 1px; }}

/* ---------- botones ---------- */
QPushButton, QToolButton {{
    min-height: 34px; padding: 0 12px; border: 1px solid {border-strong}; border-radius: 6px;
    background: {surface-200}; color: {ink}; font-weight: 500; }}
QPushButton:hover, QToolButton:hover {{ background: {surface-300}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {border}; }}
QPushButton:focus, QToolButton:focus {{ border: 2px solid {focus}; padding: 0 11px; }}
QPushButton:disabled {{ color: {border-strong}; border-color: {border}; background: {surface-100}; }}
QPushButton[variante="primario"] {{ background: {brand}; color: {on-brand}; border: 1px solid {brand}; }}
QPushButton[variante="primario"]:hover {{ background: {brand-strong}; border-color: {brand-strong}; }}
QPushButton[variante="primario"]:pressed {{ background: {brand-strong}; }}
QPushButton[variante="primario"]:focus {{ border: 2px solid {ink}; }}
QPushButton[variante="primario"]:disabled {{ background: {border}; border-color: {border}; color: {ink-muted}; }}
QPushButton[variante="peligro"] {{ background: {negative}; color: {on-brand}; border: 1px solid {negative}; }}
QPushButton[variante="peligro"]:focus {{ border: 2px solid {ink}; }}
QPushButton[variante="navegacion"] {{
    text-align: left; border: 0; background: transparent; padding: 0 12px; margin: 0 8px;
    min-height: 36px; font-weight: 400; }}
QPushButton[variante="navegacion"]:hover {{ background: {surface-200}; }}
QPushButton[variante="navegacion"]:focus {{ border: 2px solid {focus}; padding: 0 10px; }}
QPushButton[variante="navegacion"][activo="true"] {{ background: {brand-subtle}; font-weight: 600; }}
QPushButton[variante="opcion"] {{ text-align: left; min-height: 40px; padding: 0 12px; border: 1px solid {border};
                                  background: {surface-200}; font-weight: 500; }}
QPushButton[variante="opcion"]:hover {{ background: {surface-100}; border-color: {border-strong}; }}
QPushButton[variante="opcion"]:checked {{ background: {brand-subtle}; border: 1px solid {brand}; }}
QPushButton[variante="opcion"]:focus {{ border: 2px solid {focus}; padding: 0 11px; }}
QPushButton[variante="enlace"] {{ border: 0; background: transparent; color: {brand}; padding: 0 4px;
                                  min-height: 24px; }}
QPushButton[variante="enlace"]:hover {{ text-decoration: underline; }}
QPushButton[variante="enlace"]:focus {{ border: 2px solid {focus}; padding: 0 2px; }}

/* ---------- campos ---------- */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QAbstractSpinBox {{
    min-height: 34px; padding: 0 8px; border: 1px solid {border-strong}; border-radius: 4px;
    background: {surface-200}; color: {ink};
    selection-background-color: {brand-subtle}; selection-color: {ink}; }}
QPlainTextEdit, QTextEdit {{
    border: 1px solid {border-strong}; border-radius: 4px; background: {surface-200}; padding: 8px;
    selection-background-color: {brand-subtle}; selection-color: {ink}; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QAbstractSpinBox:focus,
QPlainTextEdit:focus {{ border: 2px solid {focus}; padding: 0 7px; }}
QPlainTextEdit:focus {{ padding: 7px; }}
QLineEdit[readOnly="true"] {{ background: {surface-300}; color: {ink-muted}; border-color: {border}; }}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled, QSpinBox:disabled {{
    background: {surface-300}; color: {ink-muted}; border-color: {border}; }}
QLineEdit[cifra="true"] {{ font-family: {mono}; font-weight: 500; }}
QLineEdit[error="true"] {{ border: 2px solid {negative}; padding: 0 7px; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: 0; width: 28px; subcontrol-position: center right; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url("{flecha}"); width: 16px; height: 16px; }}
QComboBox QAbstractItemView {{
    background: {surface-200}; border: 1px solid {border}; border-radius: 6px; padding: 4px;
    selection-background-color: {brand-subtle}; selection-color: {ink}; outline: 0; }}
QSpinBox::up-button, QSpinBox::down-button {{ border: 0; width: 24px; subcontrol-origin: border; }}
QSpinBox::up-button {{ subcontrol-position: top right; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; }}
QSpinBox::up-arrow {{ image: url("{flecha_arriba}"); width: 12px; height: 12px; }}
QSpinBox::down-arrow {{ image: url("{flecha}"); width: 12px; height: 12px; }}
QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {border-strong}; border-radius: 4px;
                        background: {surface-200}; }}
QCheckBox::indicator:checked {{ background: {brand}; border-color: {brand}; image: url("{check}"); }}
QCheckBox:focus {{ color: {brand}; }}
QCheckBox::indicator:focus {{ border: 2px solid {focus}; }}

/* ---------- calendario ---------- */
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {surface-300}; }}
QCalendarWidget QToolButton {{ min-height: 28px; border: 0; background: transparent; color: {ink}; }}
QCalendarWidget QToolButton:hover {{ background: {surface-200}; border-radius: 4px; }}
QCalendarWidget QToolButton::menu-indicator {{ image: none; width: 0; }}
QCalendarWidget QSpinBox {{ min-height: 24px; padding: 0 4px; }}
QCalendarWidget QAbstractItemView {{ background: {surface-200}; alternate-background-color: {surface-200};
                                     color: {ink}; selection-background-color: {brand};
                                     selection-color: {on-brand}; border: 0; border-radius: 0;
                                     font-size: 13px; outline: 0; }}
QCalendarWidget QAbstractItemView:disabled {{ color: {border-strong}; }}
QCalendarWidget QTableView::item {{ padding: 0; }}

/* ---------- tablas ---------- */
QTableView, QTableWidget, QListView, QTreeView {{
    background: {surface-200}; alternate-background-color: {surface-100};
    border: 1px solid {border}; border-radius: 10px; gridline-color: {border};
    selection-background-color: {brand-subtle}; selection-color: {ink}; outline: 0; }}
QTableView:focus, QTableWidget:focus {{ border: 2px solid {focus}; }}
QTableView::item {{ padding: 0 8px; border: 0; }}
QTableView::item:selected {{ background: {brand-subtle}; color: {ink}; }}
QHeaderView {{ background: transparent; border: 0; }}
QHeaderView::section {{
    background: {surface-300}; color: {ink}; font-size: 13px; font-weight: 500;
    padding: 0 8px; min-height: 36px; border: 0; border-bottom: 1px solid {border}; border-right: 1px solid {border}; }}
QHeaderView::section:first {{ border-top-left-radius: 9px; }}
QHeaderView::section:last {{ border-top-right-radius: 9px; border-right: 0; }}
QTableCornerButton::section {{ background: {surface-300}; border: 0; }}

/* ---------- menús y barra de estado ---------- */
QMenuBar {{ background: {surface-200}; border-bottom: 1px solid {border}; padding: 2px 8px; }}
QMenuBar::item {{ background: transparent; padding: 6px 12px; border-radius: 4px; }}
QMenuBar::item:selected, QMenuBar::item:pressed {{ background: {brand-subtle}; }}
QMenu {{ background: {surface-200}; border: 1px solid {border}; border-radius: 6px; padding: 4px; }}
QMenu::item {{ padding: 8px 32px 8px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background: {brand-subtle}; color: {ink}; }}
QMenu::item:disabled {{ color: {border-strong}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 4px 8px; }}
QMenu::icon {{ padding-left: 8px; }}
QStatusBar {{ background: {surface-200}; border-top: 1px solid {border}; color: {ink-muted}; font-size: 12px; }}
QStatusBar QLabel {{ color: {ink-muted}; font-size: 12px; padding: 0 8px; }}

/* ---------- barras de desplazamiento ---------- */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle {{ background: {border}; border-radius: 4px; min-height: 32px; min-width: 32px; }}
QScrollBar::handle:hover {{ background: {border-strong}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QDialogButtonBox {{ dialogbuttonbox-buttons-have-icons: 0; }}
QMessageBox QLabel {{ color: {ink}; }}
QMessageBox QPushButton {{ min-width: 88px; }}
""".format_map(c)


def _paleta(t: dict[str, str]):
    from PySide6.QtGui import QColor, QPalette
    p = QPalette()
    R = QPalette.ColorRole
    for rol, tok in [(R.Window, "surface-100"), (R.WindowText, "ink"), (R.Base, "surface-200"),
                     (R.AlternateBase, "surface-100"), (R.Text, "ink"), (R.Button, "surface-200"),
                     (R.ButtonText, "ink"), (R.Highlight, "brand-subtle"), (R.HighlightedText, "ink"),
                     (R.ToolTipBase, "ink"), (R.ToolTipText, "surface-200"), (R.Link, "brand"),
                     (R.PlaceholderText, "ink-muted"), (R.Mid, "border"), (R.Dark, "border-strong")]:
        p.setColor(rol, QColor(t[tok]))
    p.setColor(QPalette.ColorGroup.Disabled, R.Text, QColor(t["ink-muted"]))
    p.setColor(QPalette.ColorGroup.Disabled, R.ButtonText, QColor(t["border-strong"]))
    return p


def _sistema_oscuro(app) -> bool:
    try:
        from PySide6.QtCore import Qt
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:  # noqa: BLE001
        return False


def aplicar(app, preferencia: str = "claro") -> str:
    """Aplica estilo Fusion + paleta + fuentes + hoja de estilo. Devuelve el tema usado."""
    global _actual
    pref = (preferencia or "claro").strip().lower()
    if pref in ("automatico", "automático", "sistema"):
        _actual = "oscuro" if _sistema_oscuro(app) else "claro"
    else:
        _actual = "oscuro" if pref == "oscuro" else "claro"
    cargar_fuentes()
    app.setStyle("Fusion")
    try:
        app.setPalette(_paleta(COLORES[_actual]))
    except Exception:  # noqa: BLE001
        pass
    app.setFont(fuente("body"))
    app.setStyleSheet(hoja_de_estilo())
    return _actual


# ---------------------------------------------------------------------------
# Ayudas para marcar widgets
# ---------------------------------------------------------------------------
def _repulir(w):
    try:
        w.style().unpolish(w)
        w.style().polish(w)
    except Exception:  # noqa: BLE001
        pass


def marcar(w, **propiedades):
    """Asigna propiedades dinámicas usadas por la hoja de estilo (rol, variante, estado...)."""
    for k, v in propiedades.items():
        w.setProperty(k, v)
    _repulir(w)
    return w


def etiqueta(texto: str = "", rol: str = "body", parent=None):
    from PySide6.QtWidgets import QLabel
    lb = QLabel(texto, parent)
    if rol != "body":
        lb.setProperty("rol", rol)
    return lb


def boton(texto: str, icono_nombre: str | None = None, variante: str = "secundario", parent=None):
    from PySide6.QtWidgets import QPushButton
    b = QPushButton(texto, parent)
    if icono_nombre:
        b.setIcon(icono(icono_nombre, "on-brand" if variante in ("primario", "peligro") else "ink-muted"))
    if variante != "secundario":
        b.setProperty("variante", variante)
    try:
        from PySide6.QtCore import Qt
        b.setCursor(Qt.CursorShape.PointingHandCursor)
    except Exception:  # noqa: BLE001
        pass
    return b


def primario(b):
    """Convierte un QPushButton existente (p. ej. de QDialogButtonBox) en botón primario."""
    if b is not None:
        b.setProperty("variante", "primario")
        _repulir(b)
    return b


def tarjeta(parent=None):
    from PySide6.QtWidgets import QFrame
    f = QFrame(parent)
    f.setProperty("tarjeta", True)
    return f


def botones_dialogo(aceptar: str = "Aceptar", cancelar: str = "Cancelar"):
    """QDialogButtonBox con Aceptar (primario) y Cancelar, textos según la voz del sistema."""
    from PySide6.QtWidgets import QDialogButtonBox
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    ok = bb.button(QDialogButtonBox.StandardButton.Ok)
    ok.setText(aceptar)
    primario(ok)
    bb.button(QDialogButtonBox.StandardButton.Cancel).setText(cancelar)
    return bb


def formulario(form):
    """Etiquetas arriba del campo y separación de 16 px (patrón «Campos» del sistema)."""
    try:
        from PySide6.QtWidgets import QFormLayout
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setVerticalSpacing(ESPACIO[2])
        form.setHorizontalSpacing(ESPACIO[4])
    except Exception:  # noqa: BLE001
        pass
    return form


def margenes(layout, n: int = 6, espacio: int = 4):
    """Padding de diálogo (space-6 = 24 px) y separación entre elementos (space-4 = 16 px)."""
    layout.setContentsMargins(ESPACIO[n], ESPACIO[n], ESPACIO[n], ESPACIO[n])
    layout.setSpacing(ESPACIO[espacio])
    return layout
