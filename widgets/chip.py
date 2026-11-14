"""
Status chip component.

Follows design-doc.md §8.2:
- Fixed height: 20 px
- Padding: 2 px vertical, 9 px horizontal
- Font: Caption, 12 px
- Fully rounded border-radius: 9 px
- Variants: 'ok', 'warn', 'danger', 'neutral'
"""

from typing import Dict, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

import theme

# Variant -> (text_color, background_color)
_VARIANT_COLORS: Dict[str, Tuple[str, str]] = {
    "ok": (theme.OK, theme.OK_BG),
    "warn": (theme.WARN, theme.WARN_BG),
    "danger": (theme.DANGER, theme.DANGER_BG),
    "neutral": (theme.TEXT2, theme.SUNKEN),
}


class StatusChip(QLabel):
    """A compact, fully rounded status chip displaying a state word."""

    def __init__(self, text: str = "", variant: str = "neutral", parent=None):
        super().__init__(text, parent)
        self._variant = variant if variant in _VARIANT_COLORS else "neutral"

        self.setFixedHeight(20)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_style()

    @property
    def variant(self) -> str:
        return self._variant

    def set_variant(self, variant: str) -> None:
        """Update chip variant ('ok', 'warn', 'danger', 'neutral') and refresh style."""
        if variant not in _VARIANT_COLORS:
            variant = "neutral"
        if self._variant != variant:
            self._variant = variant
            self._apply_style()

    def set_status(self, text: str, variant: str) -> None:
        """Convenience method to set both text and variant at once."""
        self.setText(text)
        self.set_variant(variant)

    def _apply_style(self) -> None:
        text_color, bg_color = _VARIANT_COLORS.get(
            self._variant, _VARIANT_COLORS["neutral"]
        )
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                font-size: {theme.FONT_CAPTION}px;
                font-weight: 500;
                border-radius: {theme.RADIUS_CHIP}px;
                padding: 2px 9px;
            }}
            """)
