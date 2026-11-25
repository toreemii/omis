from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from ui.screens import MainWindow
from ui.styles import APP_STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())