import logging
import sys

from PyQt6.QtWidgets import QApplication

import theme
from dashboard import DirigeraDashboard


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.generate_stylesheet())
    dashboard = DirigeraDashboard()
    dashboard.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
