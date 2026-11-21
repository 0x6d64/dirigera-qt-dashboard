"""
Metric display component for numeric sensor readings.

Follows design-doc.md §8.5:
- Value at metric size (28 px, semibold)
- Unit beside it at caption size (12 px, text-2), baseline-aligned
- Caption beneath the value naming the reading ("Power", "Voltage", etc.)
- Fixed-format numbers (1 decimal place for floats, "–" when None)
"""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

import theme


class MetricWidget(QWidget):
    """Composite widget presenting a primary numeric reading with unit and label."""

    def __init__(
        self,
        caption: str = "",
        initial_value: Optional[float | str] = None,
        unit: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._caption_text = caption
        self._unit_text = unit

        # Outer vertical layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(theme.SP4)

        # Top row: Value + Unit (baseline aligned)
        value_row = QWidget()
        value_layout = QHBoxLayout(value_row)
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setSpacing(theme.SP4)
        value_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBaseline
        )

        self._value_label = QLabel()
        self._value_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT};
                font-size: {theme.FONT_METRIC}px;
                font-weight: 600;
                background-color: transparent;
            }}
            """)

        self._unit_label = QLabel(unit)
        self._unit_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT2};
                font-size: {theme.FONT_CAPTION}px;
                background-color: transparent;
            }}
            """)

        value_layout.addWidget(self._value_label)
        value_layout.addWidget(self._unit_label)
        value_layout.addStretch()

        # Bottom row: Caption label
        self._caption_label = QLabel(caption)
        self._caption_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT2};
                font-size: {theme.FONT_CAPTION}px;
                background-color: transparent;
            }}
            """)

        outer_layout.addWidget(value_row)
        outer_layout.addWidget(self._caption_label)

        self.set_value(initial_value, unit)

    def set_value(
        self, value: Optional[float | str], unit: Optional[str] = None
    ) -> None:
        """Update the displayed numeric value and optional unit string."""
        if unit is not None:
            self._unit_text = unit
            self._unit_label.setText(unit)

        if value is None:
            self._value_label.setText("–")
        elif isinstance(value, (int, float)):
            # Whole float or integer formatted without decimals, else 1 dp
            if isinstance(value, int) or value.is_integer():
                self._value_label.setText(f"{int(value)}")
            else:
                self._value_label.setText(f"{value:.1f}")
        else:
            self._value_label.setText(str(value))

    def set_caption(self, caption: str) -> None:
        """Update the caption beneath the reading."""
        self._caption_text = caption
        self._caption_label.setText(caption)

    @property
    def value_text(self) -> str:
        return self._value_label.text()

    @property
    def unit_text(self) -> str:
        return self._unit_label.text()

    @property
    def caption_text(self) -> str:
        return self._caption_label.text()
