"""
Segmented control for view switching.

Follows design-doc.md §8.6:
- Segments are joined; only the outer corners are rounded.
- The selected segment uses `accent-soft` background and `accent` text/border.
- Selection is exclusive.
- Left/Right arrows move the selection when a segment has focus.

The selected state is expressed as a `selected` dynamic property so the colours
come from the theme stylesheet instead of per-widget styling.
"""

from typing import List, Optional, Sequence, override

from PyQt6.QtCore import QEvent, QObject, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QWidget,
)


class SegmentedControl(QFrame):
    """A row of joined, mutually exclusive segment buttons."""

    current_changed = pyqtSignal(int)  # type: ignore[call-arg]

    def __init__(self, labels: Sequence[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "segmented")
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._buttons: List[QPushButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        last = len(labels) - 1
        for index, label in enumerate(labels):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("segment", "true")
            button.setProperty("first", "true" if index == 0 else "false")
            button.setProperty("last", "true" if index == last else "false")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(button, index)
            layout.addWidget(button)
            self._buttons.append(button)

        for button in self._buttons:
            button.installEventFilter(self)  # type: ignore[arg-type]
        self._group.idClicked.connect(self._on_clicked)
        if self._buttons:
            self.set_current(0)

    def buttons(self) -> List[QPushButton]:
        """Return the segment buttons in order."""
        return list(self._buttons)

    def button(self, index: int) -> QPushButton:
        """Return the segment button at `index`."""
        return self._buttons[index]

    def current_index(self) -> int:
        """Return the selected segment index, or -1 when nothing is selected."""
        for index, button in enumerate(self._buttons):
            if button.isChecked():
                return index
        return -1

    def set_current(self, index: int) -> None:
        """Select a segment without emitting `current_changed`."""
        if not 0 <= index < len(self._buttons):
            return
        self._buttons[index].setChecked(True)
        self._apply_selection(index)

    @override
    def eventFilter(self, a0: Optional[QObject], a1: Optional[QEvent]) -> bool:
        """Left/Right move the selection like a click, without wrapping."""
        if (
            a1 is not None
            and a1.type() == QEvent.Type.KeyPress
            and isinstance(a1, QKeyEvent)
            and a1.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right)
            and a0 in self._buttons
        ):
            step = -1 if a1.key() == Qt.Key.Key_Left else 1
            target = self._buttons.index(a0) + step  # type: ignore[arg-type]
            if 0 <= target < len(self._buttons):
                self._buttons[target].setChecked(True)
                self._buttons[target].setFocus()
                self._on_clicked(target)
            return True
        return super().eventFilter(a0, a1)  # type: ignore[arg-type]

    def _on_clicked(self, index: int) -> None:
        self._apply_selection(index)
        self.current_changed.emit(index)

    def _apply_selection(self, index: int) -> None:
        for position, button in enumerate(self._buttons):
            button.setProperty("selected", "true" if position == index else "false")
            style = button.style()
            if style is not None:
                style.unpolish(button)
                style.polish(button)
