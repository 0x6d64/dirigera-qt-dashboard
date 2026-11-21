"""
Scene tile component.

Follows design-doc.md §8.10:
- Minimum width 240 px; same card surface as device cards (1 px border,
  10 px radius, 16 px padding).
- Anatomy: glyph, name (title), primary "Activate" button aligned right.
- After activation the status line shows "Activated" in `ok` colour for about
  two seconds, then reverts. No modal dialog; a failure is reported inline in
  `danger` instead.
- Undo is not implemented: §8.10.4 leaves the allowed window `[open]` and
  `undo_allowed_duration` has no documented unit in the library.

The tile never talks to the hub itself: it calls `on_activate` and lets the
dashboard run the request off the GUI thread (`req-4`), then reports back via
`show_activated()` / `show_error()`.
"""

from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

import theme
from widgets.icons import render_icon, scene_icon_name

SCENE_MIN_WIDTH = 240
ACTIVATED_MS = 2000
GLYPH_SIZE = 20


class SceneTile(QFrame):
    """Card representing one scene, with an inline activation result."""

    def __init__(
        self,
        scene: Any,
        on_activate: Optional[Callable[["SceneTile"], None]] = None,
        parent=None,
        activated_ms: int = ACTIVATED_MS,
    ):
        super().__init__(parent)
        self.scene = scene
        self._on_activate = on_activate
        self._activated_ms = activated_ms

        info = getattr(scene, "info", None)
        self.full_name = str(
            getattr(info, "name", None) or getattr(scene, "id", "Unknown scene")
        )

        self.setMinimumWidth(SCENE_MIN_WIDTH)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._apply_tile_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SP16, theme.SP16, theme.SP16, theme.SP16)
        layout.setSpacing(theme.SP12)

        # 1. Glyph and name.
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(theme.SP8)

        self.glyph_label = QLabel()
        self.glyph_label.setFixedSize(GLYPH_SIZE, GLYPH_SIZE)
        self.glyph_label.setPixmap(
            render_icon(
                scene_icon_name(getattr(info, "icon", None)), theme.ACCENT, GLYPH_SIZE
            )
        )
        header.addWidget(self.glyph_label, alignment=Qt.AlignmentFlag.AlignTop)

        self.name_label = QLabel(self.full_name)
        self.name_label.setToolTip(self.full_name)
        self.name_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT};
                font-size: {theme.FONT_TITLE}px;
                font-weight: 600;
                background-color: transparent;
            }}
            """)
        header.addWidget(self.name_label, stretch=1)

        layout.addLayout(header)
        layout.addStretch(1)

        # 2. Result line and primary action.
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(theme.SP8)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "caption")
        self.status_label.hide()
        footer.addWidget(self.status_label, stretch=1)

        self.activate_button = QPushButton("Activate")
        self.activate_button.setProperty("buttonVariant", "primary")
        self.activate_button.clicked.connect(self._activate)
        footer.addWidget(self.activate_button)

        layout.addLayout(footer)

        # One reusable single-shot timer drives both the "Activated" and the
        # "Failed" revert (§8.10.3).
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self.reset)

    @property
    def is_activated(self) -> bool:
        """Return True while the transient "Activated" line is showing."""
        return self.status_label.text() == "Activated"

    def _apply_tile_style(self) -> None:
        self.setStyleSheet(f"""
            SceneTile {{
                background-color: {theme.SURFACE};
                border: 1px solid {theme.BORDER};
                border-radius: {theme.RADIUS_CARD}px;
            }}
            """)

    def _activate(self) -> None:
        """Hand the activation to the dashboard; it starts a worker thread."""
        if self._on_activate is not None:
            self._on_activate(self)

    def _show_status(self, text: str, tone: str) -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("tone", tone)
        # Re-polish so the theme's [tone] rules apply to the new property.
        style = self.status_label.style()
        if style is not None:
            style.unpolish(self.status_label)
            style.polish(self.status_label)
        self.status_label.show()

    def set_busy(self, busy: bool) -> None:
        """Disable the button while the request runs, showing progress."""
        self._reset_timer.stop()
        if busy:
            self._show_status("Activating…", "")
            self.activate_button.setEnabled(False)
        else:
            self.reset()

    def show_activated(self) -> None:
        """Show the transient "Activated" confirmation (§8.10.3)."""
        self._show_status("Activated", "ok")
        self.activate_button.setEnabled(False)
        self._reset_timer.start(self._activated_ms)

    def show_error(self, message: str = "") -> None:
        """Report a failed activation inline instead of with a dialog."""
        self._show_status("Failed", "danger")
        self.status_label.setToolTip(message)
        self.activate_button.setEnabled(True)
        self._reset_timer.start(self._activated_ms)

    def reset(self) -> None:
        """Clear the result line and re-enable the button."""
        self._reset_timer.stop()
        self.status_label.clear()
        self.status_label.setToolTip("")
        self.status_label.hide()
        self.activate_button.setEnabled(True)
