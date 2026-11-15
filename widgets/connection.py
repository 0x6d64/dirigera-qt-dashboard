"""
Centred connection block for the not-connected state.

Follows design-doc.md §8.12 and §9.1:
- Centred in the content area: heading, one help line, IP field, token field,
  Discover and Connect buttons. Nothing is drawn behind it.
- The form is a 400 px wide surface card with the card radius.
- While a connection attempt runs the form is disabled; the header chip
  reports the state (the dashboard owns the chip).
"""

from typing import Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import theme

CARD_WIDTH = 400


class ConnectionBlock(QWidget):
    """Card holding the hub credentials form."""

    discover_requested = pyqtSignal()  # type: ignore[call-arg]
    connect_requested = pyqtSignal()  # type: ignore[call-arg]

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.SP24, theme.SP24, theme.SP24, theme.SP24)
        outer.addStretch(1)

        card = QFrame()
        card.setProperty("role", "connectionCard")
        card.setFixedWidth(CARD_WIDTH)
        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)

        outer.addStretch(1)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(theme.SP24, theme.SP24, theme.SP24, theme.SP24)
        layout.setSpacing(theme.SP12)

        heading = QLabel("Connect to your hub")
        heading.setProperty("role", "cardTitle")
        layout.addWidget(heading)

        help_label = QLabel(
            "Enter the hub's IP address and an authentication token, "
            "or scan the local network."
        )
        help_label.setProperty("role", "caption")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("e.g. 192.168.1.100")
        layout.addWidget(self.ip_input)

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Authentication token")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.token_input)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(theme.SP8)

        self.discover_button = QPushButton("Discover")
        self.discover_button.clicked.connect(lambda: self.discover_requested.emit())
        button_row.addWidget(self.discover_button)

        button_row.addStretch(1)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setProperty("buttonVariant", "primary")
        self.connect_button.clicked.connect(lambda: self.connect_requested.emit())
        button_row.addWidget(self.connect_button)

        layout.addLayout(button_row)

    def credentials(self) -> Tuple[str, str]:
        """Return the stripped IP address and token."""
        return self.ip_input.text().strip(), self.token_input.text().strip()

    def set_busy(self, busy: bool) -> None:
        """Disable the form while a connection attempt is in flight."""
        for widget in (
            self.ip_input,
            self.token_input,
            self.discover_button,
            self.connect_button,
        ):
            widget.setEnabled(not busy)
