"""Sistema de Contabilidad ContaWin - versión Python.

Ejecutar:   python main.py
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _registrar_error(tipo, valor, tb):
    """Equivalente a Error.log del original: guarda el error y lo muestra."""
    texto = "".join(traceback.format_exception(tipo, valor, tb))
    try:
        from contawin.config import carpeta_programa
        with open(os.path.join(carpeta_programa(), "error.log"), "a", encoding="utf-8") as f:
            import datetime
            f.write(f"\n===== {datetime.datetime.now():%d/%m/%Y %H:%M:%S}\n{texto}")
    except OSError:
        pass
    try:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "Error inesperado",
                             f"Ocurrió un error inesperado (quedó registrado en error.log):\n\n{valor}")
    except Exception:  # noqa: BLE001
        print(texto, file=sys.stderr)


def main():
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("Falta instalar PySide6. Ejecute:  pip install -r requirements.txt")
        return 1
    from PySide6.QtCore import QLocale

    from contawin.config import Config
    from contawin.db import Database
    from contawin.ui.comunes import ESTILO, Sesion
    from contawin.ui.inicio import LoginDialog
    from contawin.ui.principal import Principal

    sys.excepthook = _registrar_error
    app = QApplication(sys.argv)
    app.setApplicationName("ContaWin")
    app.setStyle("Fusion")
    app.setStyleSheet(ESTILO)
    QLocale.setDefault(QLocale(QLocale.Language.Spanish, QLocale.Country.Chile))

    cfg = Config()
    db = Database(cfg.ruta_base)
    sesion = Sesion(db)
    if not LoginDialog(sesion, cfg.titulo).exec():
        return 0
    win = Principal(sesion, cfg)
    win.showMaximized()
    win.seleccionar_empresa()
    code = app.exec()
    db.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
