import sys

from PyQt6.QtWidgets import QApplication

from dashboard import DirigeraDashboard


def main():
    app = QApplication(sys.argv)
    dashboard = DirigeraDashboard()
    dashboard.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
