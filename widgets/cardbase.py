"""
Shared base of the device card and the energy card.

Both cards have the same frame (design-doc.md §8.1, §8.11): a header with the
name over the type and a status chip, a body the subclass fills, and a footer
caption. This base owns what they share:

- the header, with the name elided to the width the header leaves;
- the card surface, normal or offline, with the room colour edge (req-22);
- the footer state machine: "Sending…" while a command runs, and a command
  error in danger tone for `CARD_ERROR_MS` before the normal text returns.

Subclasses build their body into `card_layout`, call `_init_footer()` last,
and provide `_update_footer()` (the normal footer text) and
`sync_from_device()`. They set `_is_offline` when the device is unreachable
and may override `_offline_footer()` to replace the footer while offline.
"""

from typing import Any, Optional, override

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import theme
from widgets.chip import StatusChip
from widgets.grid import CARD_MIN_WIDTH
from widgets.text import type_label

# How long a command error stays in the footer before the normal text returns.
CARD_ERROR_MS = 8000

PENDING_TEXT = "Sending…"


def label_style(color: str, size: int, weight: Optional[int] = None) -> str:
    """QSS for a transparent label of the given colour, size and weight."""
    weight_rule = f" font-weight: {weight};" if weight is not None else ""
    return (
        f"QLabel {{ color: {color}; font-size: {size}px;{weight_rule}"
        " background-color: transparent; }"
    )


def device_name(device: Any) -> str:
    """The name a card shows: the custom name, else the device id."""
    attrs = getattr(device, "attributes", None)
    return str(
        getattr(attrs, "custom_name", None) or getattr(device, "id", "Unknown Device")
    )


class RoomSectionHeader(QWidget):
    """A room's section label, with the room colour dot in front (req-22).

    The dot shows only while the room colour mode is on and the room has a
    known colour. The label itself never changes colour.
    """

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._room_colour: Optional[str] = None
        self._marker_shown = False
        self._dot_colour: Optional[str] = None

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(theme.SP8)

        self.dot = QFrame()
        self.dot.setFixedSize(theme.ROOM_DOT, theme.ROOM_DOT)
        self.dot.hide()
        row.addWidget(self.dot, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.label = QLabel(text)
        self.label.setProperty("role", "section")
        row.addWidget(self.label)
        row.addStretch(1)

    def set_text(self, text: str) -> None:
        self.label.setText(text)

    def text(self) -> str:
        return self.label.text()

    @property
    def dot_colour(self) -> Optional[str]:
        """The colour of the dot on screen, or None while no dot is shown."""
        return self._room_colour if self._marker_shown else None

    def set_room_colour(self, colour: Optional[str]) -> None:
        """Set the room's colour (None for a room without a known colour)."""
        self._room_colour = colour
        self._sync_dot()

    def set_marker_shown(self, shown: bool) -> None:
        """Show or hide the dot (the room colour mode)."""
        self._marker_shown = shown
        self._sync_dot()

    def _sync_dot(self) -> None:
        colour = self.dot_colour
        if colour != self._dot_colour:
            self._dot_colour = colour
            if colour is not None:
                self.dot.setStyleSheet(f"""
                    QFrame {{
                        background-color: {colour};
                        border: none;
                        border-radius: {theme.ROOM_DOT // 2}px;
                    }}
                    """)
        self.dot.setVisible(colour is not None)


class CardBase(QFrame):
    """Frame, header, footer and command feedback shared by the cards."""

    def __init__(
        self,
        device: Any,
        parent: Optional[QWidget] = None,
        min_width: int = CARD_MIN_WIDTH,
    ) -> None:
        super().__init__(parent)
        self.device = device
        self._is_offline = False
        self._room_colour: Optional[str] = None
        self._marker_shown = False
        self._pending = False
        self._error: Optional[str] = None
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.setInterval(CARD_ERROR_MS)
        self._error_timer.timeout.connect(self._clear_error)

        self.setMinimumWidth(min_width)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._apply_card_style(is_offline=False)

        self.card_layout = QVBoxLayout(self)
        self.card_layout.setContentsMargins(
            theme.SP16, theme.SP16, theme.SP16, theme.SP16
        )
        self.card_layout.setSpacing(theme.SP12)

        # Header row: name over type on the left, status chip on the right.
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(theme.SP8)

        titles_vbox = QVBoxLayout()
        titles_vbox.setContentsMargins(0, 0, 0, 0)
        titles_vbox.setSpacing(2)

        raw_name = device_name(device)
        self.full_name = raw_name
        self.name_label = QLabel(raw_name)
        self.name_label.setStyleSheet(label_style(theme.TEXT, theme.FONT_TITLE, 600))
        self.name_label.setToolTip(raw_name)
        # Ignored: the full name must never widen the card; it is elided to
        # the room the header leaves (§8.1).
        self.name_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        titles_vbox.addWidget(self.name_label)

        self.type_label = QLabel(type_label(getattr(device, "device_type", "device")))
        self.type_label.setStyleSheet(label_style(theme.TEXT2, theme.FONT_CAPTION))
        titles_vbox.addWidget(self.type_label)

        header_layout.addLayout(titles_vbox, stretch=1)

        self.status_chip = StatusChip(text="", variant="neutral")
        header_layout.addWidget(self.status_chip, alignment=Qt.AlignmentFlag.AlignTop)
        self.card_layout.addLayout(header_layout)

        self.footer_label = QLabel()
        self.footer_label.setWordWrap(True)
        self._style_footer(danger=False)

    def _init_footer(self) -> None:
        """Add the footer as the last row; call once the body is built."""
        self._update_footer()
        self.card_layout.addWidget(self.footer_label)

    def _update_footer(self) -> None:
        """Show the normal footer text (through `_set_footer`)."""
        raise NotImplementedError

    def sync_from_device(self) -> None:
        """Redraw the card from `self.device`, sending nothing."""
        raise NotImplementedError

    def _offline_footer(self) -> Optional[str]:
        """Footer text while offline, or None to keep the normal text."""
        return None

    def _elide_name(self) -> None:
        """Show `full_name` cut with an ellipsis to the width the header has.

        The width is derived from the card, not from the label, so it is right
        before the first layout pass and cannot feed back into the card size.
        """
        self.name_label.ensurePolished()
        available = (
            self.width()
            - 2 * theme.SP16
            - theme.SP8
            - (
                0
                if self.status_chip.isHidden()
                else self.status_chip.sizeHint().width()
            )
        )
        text = str(self.full_name)
        if available > 0:
            text = self.name_label.fontMetrics().elidedText(
                text, Qt.TextElideMode.ElideRight, available
            )
        if self.name_label.text() != text:
            self.name_label.setText(text)

    def _set_name(self, name: str) -> None:
        """Adopt a changed device name (label text and tooltip)."""
        if name != self.full_name:
            self.full_name = name
            self.name_label.setToolTip(name)
            self._elide_name()

    @override
    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        super().resizeEvent(event)
        self._elide_name()

    @property
    def edge_colour(self) -> Optional[str]:
        """The room colour on the card's left edge, or None while none is shown."""
        return self._room_colour if self._marker_shown else None

    def set_room_colour(self, colour: Optional[str]) -> None:
        """Set the card's room colour (None for a room without a known colour)."""
        before = self.edge_colour
        self._room_colour = colour
        if self.edge_colour != before:
            self._apply_card_style(is_offline=self._is_offline)

    def set_marker_shown(self, shown: bool) -> None:
        """Show or hide the room colour edge (the room colour mode)."""
        before = self.edge_colour
        self._marker_shown = shown
        if self.edge_colour != before:
            self._apply_card_style(is_offline=self._is_offline)

    def _apply_card_style(self, is_offline: bool) -> None:
        bg = theme.SUNKEN if is_offline else theme.SURFACE
        edge = self.edge_colour
        edge_rule = (
            f"border-left: {theme.ROOM_EDGE}px solid {edge};"
            if edge is not None
            else ""
        )
        self.setStyleSheet(f"""
            {type(self).__name__} {{
                background-color: {bg};
                border: 1px solid {theme.BORDER};
                {edge_rule}
                border-radius: {theme.RADIUS_CARD}px;
            }}
            """)

    def _set_chip(self, text: str, variant: str) -> None:
        """Show the state chip, or hide it when there is no state to show."""
        self.status_chip.set_status(text, variant)
        self.status_chip.setVisible(bool(text))

    def _style_footer(self, danger: bool) -> None:
        color = theme.DANGER if danger else theme.TEXT2
        self.footer_label.setStyleSheet(label_style(color, theme.FONT_CAPTION))

    def _set_footer(self, text: str) -> None:
        """Show `text`, unless a command error is being shown (danger tone)."""
        if self._error is not None and text != PENDING_TEXT:
            self.footer_label.setText(self._error)
            self._style_footer(danger=True)
        else:
            self.footer_label.setText(text)
            self._style_footer(danger=False)

    def _refresh_footer(self) -> None:
        """Show the offline or the normal footer, whichever applies."""
        offline_text = self._offline_footer() if self._is_offline else None
        if offline_text is not None:
            self._set_footer(offline_text)
        else:
            self._update_footer()

    def show_error(self, message: str) -> None:
        """Show `message` in the footer in danger tone for CARD_ERROR_MS."""
        self._error = message
        self._error_timer.start()
        if self._pending:
            return
        self._refresh_footer()

    def _clear_error(self) -> None:
        self._error = None
        if self._pending:
            return
        self._refresh_footer()

    def set_pending(self, pending: bool) -> None:
        """Show pending command status in footer."""
        if pending:
            self._set_footer(PENDING_TEXT)
        else:
            self._update_footer()
