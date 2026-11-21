"""
Energy view and energy cards.

Follows design-doc.md §8.11 and §9.4:
- Energy cards reuse the device-card surface: 1 px border, 10 px radius,
  16 px padding, 280 px minimum width.
- Primary reading: live power in W (`MetricWidget`); the caption line carries
  current in A and voltage in V; the footer shows the total in kWh.
- Devices without metering data get no metric row and a "No energy data"
  footer.
- Cards are grouped by room in the same flow grid as the Rooms view.
- Per-home versus per-room totals is `[open]` in the design doc, so no totals
  are shown yet.

Only outlets and electrical sensors reach this view; the dashboard filters
them before calling `EnergyView.set_rooms()`.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, override

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import theme
from settings import DEFAULT_CURRENCY, DEFAULT_PRICE_PER_KWH
from widgets.cardbase import CardBase, label_style
from widgets.grid import CardGrid
from widgets.metric import MetricWidget
from widgets.text import format_amps, format_kwh, format_volts, usage_text


class EnergyCard(CardBase):
    """Card with the live power reading of one metered device.

    Shares the header, footer and command feedback (`set_pending`,
    `show_error`, `sync_from_device`) with the device card, so a command can
    run through the dashboard's `run_device_command`.
    """

    def __init__(
        self,
        device: Any,
        parent: Optional[QWidget] = None,
        price_per_kwh: float = DEFAULT_PRICE_PER_KWH,
        currency: str = DEFAULT_CURRENCY,
    ) -> None:
        super().__init__(device, parent)
        self.price_per_kwh = price_per_kwh
        self.currency = currency
        attrs = getattr(device, "attributes", None)

        # Metric zone: live power, then the A / V caption line.
        power = getattr(attrs, "current_active_power", None)
        self.power_metric: Optional[MetricWidget] = None
        if power is not None:
            self.power_metric = MetricWidget(
                caption="Power", initial_value=power, unit="W"
            )
            self.card_layout.addWidget(self.power_metric)

        self.caption_label = QLabel(self._format_captions(attrs))
        self.caption_label.setStyleSheet(label_style(theme.TEXT2, theme.FONT_CAPTION))
        # Always in the layout so a refresh can fill it later; hidden while
        # the device reports no current or voltage.
        self.caption_label.setVisible(bool(self.caption_label.text()))
        self.card_layout.addWidget(self.caption_label)

        # Usage since the last reset with its cost; hidden without usage data.
        self.usage_label = QLabel()
        self.usage_label.setStyleSheet(label_style(theme.TEXT2, theme.FONT_CAPTION))
        self.card_layout.addWidget(self.usage_label)
        self._update_usage()

        # Footer: total energy, or an explicit "no data" line.
        self._init_footer()
        self._update_state()

    @property
    def is_metered(self) -> bool:
        """Return True when the device reports live power."""
        return self.power_metric is not None

    def set_price(self, price_per_kwh: float, currency: str) -> None:
        """Use a new price for the usage cost and redraw the usage line."""
        self.price_per_kwh = price_per_kwh
        self.currency = currency
        self._update_usage()

    def _update_usage(self) -> None:
        attrs = getattr(self.device, "attributes", None)
        text = usage_text(
            attrs, self.price_per_kwh, self.currency, datetime.now().date()
        )
        self.usage_label.setText(text or "")
        self.usage_label.setVisible(text is not None)

    def update_from_device(self, device: Any) -> bool:
        """Show the readings of a freshly fetched `device` in place (t-19).

        Returns False when the card cannot follow without being rebuilt,
        i.e. the device started or stopped reporting live power.
        """
        attrs = getattr(device, "attributes", None)
        power = getattr(attrs, "current_active_power", None)
        if (power is not None) != (self.power_metric is not None):
            return False
        self.device = device
        self._redraw()
        return True

    @override
    def sync_from_device(self) -> None:
        """Redraw the card from `self.device`, e.g. after a command."""
        self._redraw()

    def _redraw(self) -> None:
        """Show the readings, footer and state of `self.device`."""
        attrs = getattr(self.device, "attributes", None)
        if self.power_metric is not None:
            self.power_metric.set_value(getattr(attrs, "current_active_power", None))
        text = self._format_captions(attrs)
        self.caption_label.setText(text)
        self.caption_label.setVisible(bool(text))
        self._update_usage()
        self._update_footer()
        self._update_state()

    @override
    def _update_footer(self) -> None:
        attrs = getattr(self.device, "attributes", None)
        self._set_footer(self._format_footer(attrs))

    def _update_state(self) -> None:
        """Card surface and chip: offline, or the outlet's on/off state."""
        offline = getattr(self.device, "is_reachable", True) is False
        self._is_offline = offline
        self._apply_card_style(is_offline=offline)
        if offline:
            self._set_chip("Offline", "neutral")
        else:
            attrs = getattr(self.device, "attributes", None)
            self._update_chip(attrs, getattr(self.device, "device_type", "device"))

    def _update_chip(self, attrs: Any, dtype: str) -> None:
        """Chip for a readable outlet state; nothing otherwise (no invented state)."""
        is_on = getattr(attrs, "is_on", None) if dtype == "outlet" else None
        if is_on is True:
            self._set_chip("On", "ok")
        elif is_on is False:
            self._set_chip("Off", "neutral")
        else:
            self._set_chip("", "neutral")

    @staticmethod
    def _format_captions(attrs: Any) -> str:
        """Return the current/voltage caption line, empty when unreported."""
        parts = [format_amps(attrs), format_volts(attrs)]
        return " · ".join(p for p in parts if p)

    @staticmethod
    def _format_footer(attrs: Any) -> str:
        """Return the total-energy footer; never leave it blank (§8.11)."""
        kwh = format_kwh(attrs)
        return f"Total {kwh}" if kwh else "No energy data"


class EnergyView(QWidget):
    """Scrollable energy view: one card grid per room (§9.4)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        # PyQt6 stubs mis-type the first argument of QWidget.__init__ here.
        super().__init__(parent)  # type: ignore[arg-type]
        self._shape: List[Tuple[str, List[Any]]] = []
        self.price_per_kwh = DEFAULT_PRICE_PER_KWH
        self.currency = DEFAULT_CURRENCY

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(
            theme.SP24, theme.SP20, theme.SP24, theme.SP24
        )
        self.content_layout.setSpacing(theme.SP24)
        self.content_layout.addStretch()
        self.scroll_area.setWidget(self.content)
        outer.addWidget(self.scroll_area, 1)

        # Shown instead of the grid when nothing reports energy data.
        self.empty_label = QLabel("No energy data")
        self.empty_label.setProperty("role", "caption")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        outer.addWidget(self.empty_label, 1)

    def set_price(self, price_per_kwh: float, currency: str) -> None:
        """Set the price the usage costs are computed from (req-19)."""
        self.price_per_kwh = price_per_kwh
        self.currency = currency
        for card in self.cards():
            card.set_price(price_per_kwh, currency)

    def update_rooms(self, rooms: List[Tuple[str, List[Any]]]) -> None:
        """Show (room label, devices) pairs, updating cards in place (t-19).

        When the rooms and their devices are unchanged, the existing cards
        take the new readings and nothing is recreated. Otherwise the view is
        rebuilt and its scroll position is kept.
        """
        shape = [
            (label, [getattr(d, "id", None) for d in devs]) for label, devs in rooms
        ]
        if shape == self._shape:
            cards = self.cards_by_id()
            if all(
                getattr(device, "id", None) in cards
                and cards[getattr(device, "id", None)].update_from_device(device)
                for _, devices in rooms
                for device in devices
            ):
                return
        bar = self.scroll_area.verticalScrollBar()
        value = bar.value() if bar is not None else 0
        self.set_rooms(rooms)
        if bar is not None and value:
            # The new sections are laid out on the next event-loop turn.
            QTimer.singleShot(0, lambda: bar.setValue(value))

    def cards_by_id(self) -> Dict[Any, EnergyCard]:
        """Return the energy cards keyed by device id."""
        return {getattr(card.device, "id", None): card for card in self.cards()}

    def set_rooms(self, rooms: List[Tuple[str, List[Any]]]) -> None:
        """Rebuild the view from (room label, devices) pairs."""
        self.clear()
        self._shape = [
            (label, [getattr(d, "id", None) for d in devs]) for label, devs in rooms
        ]

        has_rooms = bool(rooms)
        self.scroll_area.setVisible(has_rooms)
        self.empty_label.setVisible(not has_rooms)

        for label_text, devices in rooms:
            section = QWidget()
            layout = QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(theme.SP12)  # label-to-grid gap (§4.3)

            label = QLabel(label_text)
            label.setProperty("role", "section")
            layout.addWidget(label)

            grid = CardGrid()
            grid.set_cards(
                [
                    EnergyCard(
                        device, price_per_kwh=self.price_per_kwh, currency=self.currency
                    )
                    for device in devices
                ]
            )
            layout.addWidget(grid)

            self.content_layout.insertWidget(self.content_layout.count() - 1, section)

    def clear(self) -> None:
        """Remove every room section, keeping the trailing stretch."""
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

    def cards(self) -> List[EnergyCard]:
        """Return every energy card in display order."""
        found: List[EnergyCard] = list(self.content.findChildren(EnergyCard))
        return found
