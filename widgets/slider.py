"""
Labeled slider widget with debounced/release-based command emission.

Follows design-doc.md §8.4:
- Fixed-width label column on the left (60 px, 13 px label font)
- Fixed-width right-aligned value column on the right (50 px, body size)
- Track 6 px high, rounded; filled part ACCENT; unfilled SUNKEN
- Thumb 18 px white with 2 px ACCENT border
- Minimum height: 24 px (prevents thumb clipping)
- Value label updates live while dragging
- Command signal `committed(int)` (req-6): fires once on release after a drag,
  and after a short pause for every other user change — track clicks, arrow
  and Page keys, mouse wheel — so no input path leaves a value unsent.
  Programmatic `set_value()` never fires it.
- Does NOT use `QSlider:disabled::sub-page` (doc/qt-gotchas.md item 4)
"""

from typing import override

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget

import theme

# Pause after a non-drag change before the value is committed (req-6).
COMMIT_DELAY_MS = 300


class LabeledSlider(QWidget):
    """Composite slider with aligned label, live value readout, and release-trigger."""

    # Fired once per user change, for sending hub commands (req-6)
    committed = pyqtSignal(int)  # type: ignore[call-arg]
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
        self._programmatic = False

        # Coalesces bursts of key, wheel or click steps into one command.
        self._commit_timer = QTimer(self)
        self._commit_timer.setSingleShot(True)
        self._commit_timer.setInterval(COMMIT_DELAY_MS)
        self._commit_timer.timeout.connect(self._commit)

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
        # The value the hub is believed to hold; commits only send changes.
        self._committed_value = self._slider.value()

    def _on_value_changed(self, value: int) -> None:
        self._update_value_label(value)
        self.value_changed.emit(value)
        # During a drag the release commits; any other user change commits
        # after a pause, so the latest value wins.
        if not self._programmatic and not self._slider.isSliderDown():
            self._commit_timer.start()

    def _on_slider_released(self) -> None:
        self._commit()

    def _commit(self) -> None:
        self._commit_timer.stop()
        value = self._slider.value()
        # A click on the handle without moving it sends nothing.
        if value != self._committed_value:
            self._committed_value = value
            self.committed.emit(value)

    def _update_value_label(self, val: int) -> None:
        if self._unit:
            self._value_label.setText(f"{val} {self._unit}".strip())
        else:
            self._value_label.setText(str(val))

    # Public API
    def value(self) -> int:
        return self._slider.value()

    def is_user_active(self) -> bool:
        """Return True while the user is dragging or has keyboard focus here.

        Automated refreshes leave such a slider alone (req-13).
        """
        return self._slider.isSliderDown() or self._slider.hasFocus()

    def set_value(self, value: int) -> None:
        """Show `value` without committing it (used for resyncs)."""
        self._programmatic = True
        try:
            self._slider.setValue(value)
        finally:
            self._programmatic = False
        self._committed_value = self._slider.value()
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
