"""
Labeled slider widget with debounced/release-based command emission.

Follows design-doc.md §8.4:
- Fixed-width label column on the left (60 px, 13 px label font)
- Fixed-width right-aligned value column on the right (50 px, body size)
- Track 6 px high, rounded; filled part ACCENT; unfilled SUNKEN
- Thumb 18 px white with 2 px ACCENT border
- Minimum height: 24 px (prevents thumb clipping)
- Value label updates live while dragging
- Command signal `released(int)` fires only on slider release (req-6)
- Does NOT use `QSlider:disabled::sub-page` (design-doc.md §13.2 pitfall 2)
"""

from typing import override

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget

import theme


class LabeledSlider(QWidget):
    """Composite slider with aligned label, live value readout, and release-trigger."""

    # Fired on sliderReleased for sending hub commands without flooding ticks (req-6)
    released = pyqtSignal(int)  # type: ignore[call-arg]
    # Fired on every tick for live UI updates
    value_changed = pyqtSignal(int)  # type: ignore[call-arg]

    def __init__(
        self,
        label: str = "",
        minimum: int = 0,
        maximum: int = 100,
        initial_value: int = 0,
        unit: str = "%",
        parent=None,
    ):
        super().__init__(parent)
        self._unit = unit

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SP8)

        # Left label (fixed width for vertical alignment across cards)
        self._label = QLabel(label)
        self._label.setFixedWidth(60)
        self._label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT2};
                font-size: {theme.FONT_LABEL}px;
                background-color: transparent;
            }}
            """)

        # QSlider
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(minimum)
        self._slider.setMaximum(maximum)
        self._slider.setValue(initial_value)
        self._slider.setMinimumHeight(24)

        # Right value readout (fixed width, right-aligned)
        self._value_label = QLabel()
        self._value_label.setFixedWidth(50)
        self._value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._value_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT};
                font-size: {theme.FONT_BODY}px;
                background-color: transparent;
            }}
            """)

        layout.addWidget(self._label)
        layout.addWidget(self._slider)
        layout.addWidget(self._value_label)

        # Wire internal signals
        self._slider.valueChanged.connect(self._on_value_changed)
        self._slider.sliderReleased.connect(self._on_slider_released)

        self._update_value_label(self._slider.value())

    def _on_value_changed(self, value: int) -> None:
        self._update_value_label(value)
        self.value_changed.emit(value)

    def _on_slider_released(self) -> None:
        self.released.emit(self._slider.value())

    def _update_value_label(self, val: int) -> None:
        if self._unit:
            self._value_label.setText(f"{val} {self._unit}".strip())
        else:
            self._value_label.setText(str(val))

    # Public API
    def value(self) -> int:
        return self._slider.value()

    def set_value(self, value: int) -> None:
        self._slider.setValue(value)
        self._update_value_label(self._slider.value())

    def set_minimum(self, min_val: int) -> None:
        self._slider.setMinimum(min_val)

    def set_maximum(self, max_val: int) -> None:
        self._slider.setMaximum(max_val)

    def set_range(self, min_val: int, max_val: int) -> None:
        self._slider.setRange(min_val, max_val)

    def set_label(self, text: str) -> None:
        self._label.setText(text)

    def set_unit(self, unit: str) -> None:
        self._unit = unit
        self._update_value_label(self._slider.value())

    @override
    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self._slider.setEnabled(enabled)
        self._label.setEnabled(enabled)
        self._value_label.setEnabled(enabled)
