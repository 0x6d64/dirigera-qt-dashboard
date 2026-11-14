import sys

from PyQt6.QtWidgets import QApplication

import theme
from dashboard import DirigeraDashboard


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.generate_stylesheet())
    dashboard = DirigeraDashboard()
    dashboard.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
