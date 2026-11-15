"""
Width-driven card grid for room sections.

Follows design-doc.md §4.3 and §11:
- Cards are at least 280 px wide with 16 px gaps between them.
- The column count is the largest number of cards that fits in the available
  width, so the grid reflows when the window is resized.
- Grids never reorder their cards; ordering is the caller's responsibility.

`FlowLayout` is a height-for-width layout, which lets a section shrink to a
single column: a plain `QGridLayout` would pin the row to the sum of every
card's minimum width and never reflow.
"""

from typing import List, Optional, override

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QWidget

import theme

CARD_MIN_WIDTH = 280
CARD_GAP = theme.SP16


def grid_columns_for_width(width: int) -> int:
    """Return the largest number of minimum-width cards that fit in `width`."""
    if width <= 0:
        return 1
    return max(1, (width + CARD_GAP) // (CARD_MIN_WIDTH + CARD_GAP))


class FlowLayout(QLayout):
    """Left-to-right layout that wraps into equal-width columns."""

    def __init__(self, parent: Optional[QWidget] = None, gap: int = CARD_GAP):
        super().__init__(parent)
        self._items: List[QLayoutItem] = []
        self._gap = gap
        self.setContentsMargins(0, 0, 0, 0)

    @override
    def addItem(self, item: Optional[QLayoutItem]) -> None:
        if item is not None:
            self._items.append(item)

    @override
    def count(self) -> int:
        return len(self._items)

    @override
    def itemAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    @override
    def takeAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    @override
    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    @override
    def hasHeightForWidth(self) -> bool:
        return True

    @override
    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    @override
    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    @override
    def sizeHint(self) -> QSize:
        return self.minimumSize()

    @override
    def minimumSize(self) -> QSize:
        size = QSize(CARD_MIN_WIDTH, 0)
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        columns = grid_columns_for_width(effective.width())
        column_width = max(
            CARD_MIN_WIDTH,
            (effective.width() - self._gap * (columns - 1)) // columns,
        )

        x = effective.x()
        y = effective.y()
        row_height = 0

        for index, item in enumerate(self._items):
            column = index % columns
            if column == 0 and index > 0:
                y += row_height + self._gap
                row_height = 0
            x = effective.x() + column * (column_width + self._gap)
            height = item.sizeHint().height()
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(column_width, height)))
            row_height = max(row_height, height)

        return y + row_height - rect.y() + margins.bottom()


class CardGrid(QWidget):
    """Grid of cards that reflows to the largest column count that fits."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._flow = FlowLayout(self)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def cards(self) -> List[QWidget]:
        """Return the cards in display order."""
        cards: List[QWidget] = []
        for index in range(self._flow.count()):
            item = self._flow.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                cards.append(widget)
        return cards

    def columns(self) -> int:
        """Return the column count for the current width."""
        return grid_columns_for_width(self.width())

    def set_cards(self, cards: List[QWidget]) -> None:
        """Replace the grid contents, keeping the given order."""
        while self._flow.count():
            self._flow.takeAt(0)
        for card in cards:
            self._flow.addWidget(card)
        self.updateGeometry()

    def clear(self) -> None:
        """Remove every card from the grid and schedule it for deletion."""
        while self._flow.count():
            item = self._flow.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.updateGeometry()

    @override
    def hasHeightForWidth(self) -> bool:
        return True

    @override
    def heightForWidth(self, width: int) -> int:
        return int(self._flow.heightForWidth(width))

    @override
    def sizeHint(self) -> QSize:
        return QSize(CARD_MIN_WIDTH, self._flow.heightForWidth(self.width()))
