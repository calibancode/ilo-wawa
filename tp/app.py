# app.py
# -------------------------------------------------------------------
# application entrypoint
# -------------------------------------------------------------------

import sys
from PySide6.QtWidgets import QApplication

from ui_main import MainWindow
from log import log


def main():
    log.info("starting ilo wawa")

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()

    log.info("app initialized — entering event loop")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
