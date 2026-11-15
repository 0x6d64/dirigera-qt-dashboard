"""
Custom animated toggle switch widget.

Follows design-doc.md §8.3:
- Size: 44 × 24 px
- Thumb: 18 px diameter, white, 3 px inset
- Track on: ACCENT; Track off: OFF; Disabled: muted tones
- Thumb animation: 120 ms, out-cubic easing
- Property name: `thumb` (never `pos`, which clashes with QWidget.pos)
- Focus: 2 px accent ring
- Implemented as a QAbstractButton subclass with accessible name
"""

from typing import Optional, override

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QAbstractButton

import theme


class ToggleSwitch(QAbstractButton):
    """An animated toggle switch with calm styling and accessibility support."""

    def __init__(self, accessible_name: str = "Switch", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(False)
        self.setAccessibleName(accessible_name)

        # Thumb X offset ranges from 3.0 (off) to 23.0 (on: 44 - 18 - 3 = 23)
        self._thumb_offset: float = 3.0

        # Animation setup
        self._anim = QPropertyAnimation(self, b"thumb", self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @override
    def sizeHint(self) -> QSize:
        return QSize(44, 24)

    @override
    def minimumSizeHint(self) -> QSize:
        return QSize(44, 24)

    def _get_thumb(self) -> float:
        return self._thumb_offset

    def _set_thumb(self, val: float) -> None:
        self._thumb_offset = val
        self.update()

    thumb = pyqtProperty(float, fget=_get_thumb, fset=_set_thumb)

    @override
    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        target = 23.0 if checked else 3.0
        self._thumb_offset = target
        self.update()

    @override
    def nextCheckState(self) -> None:
        super().nextCheckState()
        target = 23.0 if self.isChecked() else 3.0
        self._anim.stop()
        self._anim.setStartValue(self._thumb_offset)
        self._anim.setEndValue(target)
        self._anim.start()

    @override
    def paintEvent(self, a0: Optional[QPaintEvent]) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = 44.0
        h = 24.0
        radius = h / 2.0  # 12.0 px for full round capsule

        # Determine colors
        is_enabled = self.isEnabled()
        is_checked = self.isChecked()

        if is_enabled:
            track_color = QColor(theme.ACCENT) if is_checked else QColor(theme.OFF)
            thumb_color = QColor(theme.SURFACE)
        else:
            track_color = (
                QColor(theme.ACCENT_SOFT) if is_checked else QColor(theme.SUNKEN)
            )
            thumb_color = QColor(theme.BORDER)

        # Draw track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(QRectF(0.0, 0.0, w, h), radius, radius)

        # Draw focus ring if focused
        if self.hasFocus():
            focus_pen = QPen(QColor(theme.ACCENT), 2.0)
            painter.setPen(focus_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                QRectF(1.0, 1.0, w - 2.0, h - 2.0), radius - 1.0, radius - 1.0
            )

        # Draw thumb (18 px diameter, 3 px inset vertically)
        thumb_diameter = 18.0
        thumb_y = 3.0
        thumb_x = self._thumb_offset

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(thumb_color)
        painter.drawEllipse(QRectF(thumb_x, thumb_y, thumb_diameter, thumb_diameter))
