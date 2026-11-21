"""
Device card component.

Follows design-doc.md §8.1:
- Minimum width: 280 px; height determined by content
- Border 1 px BORDER, radius 10 px (RADIUS_CARD), background SURFACE
- Padding: 16 px (SP16); Gap between zones: 12 px (SP12)
- Anatomy:
  1. Header row: Name (16 px bold, truncated with tooltip) over Type (12 px, TEXT2)
     on the left; StatusChip on the right.
  2. Control zone: 0 to 3 controls depending on device type.
  3. Footer row: Caption line (battery, energy, or "Last seen...").
- States: Normal, Offline (SUNKEN background, chip "Offline", controls disabled),
  Pending command (footer "Sending...").
- Device sorting helper to guarantee stable room ordering:
  lights -> outlets -> blinds -> air/environment -> sensors -> remotes.
"""

from datetime import datetime
from typing import Any, Callable, Optional, Tuple, override

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import theme
from widgets.chip import StatusChip
from widgets.metric import MetricWidget
from widgets.slider import LabeledSlider
from widgets.switch import ToggleSwitch
from widgets.text import energy_footer, relative_time, type_label

# Device category sorting weight per design-doc.md §8.1 rule 3
# (keys are the library's camelCase `device_type` values; every controller
# type ends in "Controller").
_TYPE_SORT_WEIGHT = {
    "light": 10,
    "outlet": 20,
    "blinds": 30,
    "airPurifier": 40,
    "environmentSensor": 50,
    "electricalSensor": 60,
    "lightSensor": 70,
    "waterSensor": 71,
    "openCloseSensor": 80,
    "occupancySensor": 85,
    "motionSensor": 90,
}
_CONTROLLER_WEIGHT = 100

# Read-only readings per device type: (caption, unit, attribute). Units the
# library does not document are left empty rather than guessed
# (dirigera-api.md §1 finding 7). Only values that are not None are shown.
_READINGS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "environmentSensor": (
        ("Temperature", "°C", "current_temperature"),
        ("Humidity", "%", "current_r_h"),
        ("PM2.5", "", "current_p_m25"),
        ("CO₂", "ppm", "current_c_o2"),
        ("VOC index", "", "voc_index"),
    ),
    "lightSensor": (("Illuminance", "", "illuminance"),),
    "airPurifier": (
        ("PM2.5", "", "current_p_m25"),
        ("Fan mode", "", "fan_mode"),
    ),
}

# Readings shown side by side before the next row starts (§8.5.3).
READINGS_PER_ROW = 3

# Battery level at or below which the chip warns (design-doc.md §14 item 4).
LOW_BATTERY_PERCENT = 20

# How long a command error stays in the footer before the normal text returns.
CARD_ERROR_MS = 8000


def device_sort_key(device: Any) -> Tuple[int, str]:
    """Sort key for devices within a room: category weight then device name."""
    dtype = getattr(device, "device_type", "unknown")
    weight = _TYPE_SORT_WEIGHT.get(dtype, 999)
    if dtype.endswith("Controller"):
        weight = _CONTROLLER_WEIGHT
    raw_name = getattr(device.attributes, "custom_name", None) or getattr(
        device, "id", ""
    )
    name_str = str(raw_name) if raw_name is not None else ""
    return (weight, name_str.lower())


class DeviceCard(QFrame):
    """Calm, structured card representation of a single smart home device."""

    def __init__(
        self,
        device: Any,
        on_toggle: Optional[Callable[["DeviceCard", bool], None]] = None,
        on_brightness: Optional[Callable[["DeviceCard", int], None]] = None,
        on_blind_position: Optional[Callable[["DeviceCard", int], None]] = None,
        on_blind_state: Optional[Callable[["DeviceCard", str], None]] = None,
        parent=None,
    ):
        """Build the card. Every callback receives the card itself, so the
        handler can reach `card.device` and resync the card afterwards with
        `sync_from_device()`."""
        super().__init__(parent)
        self.device = device
        self._on_toggle = on_toggle
        self._on_brightness = on_brightness
        self._on_blind_position = on_blind_position
        self._on_blind_state = on_blind_state

        self._controls: list[QWidget] = []
        self._readings_box: Optional[QWidget] = None
        self._readings: dict[str, MetricWidget] = {}
        self._is_offline = False
        self._pending = False
        self._error: Optional[str] = None
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.setInterval(CARD_ERROR_MS)
        self._error_timer.timeout.connect(self._clear_error)

        self.setMinimumWidth(280)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._apply_card_style(is_offline=False)

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(theme.SP16, theme.SP16, theme.SP16, theme.SP16)
        card_layout.setSpacing(theme.SP12)

        # 1. Header row
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(theme.SP8)

        titles_vbox = QVBoxLayout()
        titles_vbox.setContentsMargins(0, 0, 0, 0)
        titles_vbox.setSpacing(2)

        raw_name = getattr(device.attributes, "custom_name", None) or getattr(
            device, "id", "Unknown Device"
        )
        self.full_name = raw_name
        self.name_label = QLabel(raw_name)
        self.name_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT};
                font-size: {theme.FONT_TITLE}px;
                font-weight: 600;
                background-color: transparent;
            }}
            """)
        self.name_label.setToolTip(raw_name)
        # Ignored: the full name must never widen the card; it is elided to
        # the room the header leaves (§8.1).
        self.name_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        titles_vbox.addWidget(self.name_label)

        self.type_label = QLabel(type_label(getattr(device, "device_type", "device")))
        self.type_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT2};
                font-size: {theme.FONT_CAPTION}px;
                background-color: transparent;
            }}
            """)
        titles_vbox.addWidget(self.type_label)

        header_layout.addLayout(titles_vbox, stretch=1)

        self.status_chip = StatusChip(text="", variant="neutral")
        header_layout.addWidget(self.status_chip, alignment=Qt.AlignmentFlag.AlignTop)

        card_layout.addLayout(header_layout)

        # 2. Control zone
        self.control_zone = QVBoxLayout()
        self.control_zone.setContentsMargins(0, 0, 0, 0)
        self.control_zone.setSpacing(theme.SP8)
        self._build_controls()
        if self.control_zone.count() > 0:
            card_layout.addLayout(self.control_zone)

        # 3. Footer row
        self.footer_label = QLabel()
        self.footer_label.setWordWrap(True)
        self._style_footer(danger=False)
        self._update_footer()
        card_layout.addWidget(self.footer_label)

        # Initial status chip sync
        self._update_status_chip()
        self._elide_name()

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

    @override
    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        super().resizeEvent(event)
        self._elide_name()

    def _apply_card_style(self, is_offline: bool) -> None:
        bg = theme.SUNKEN if is_offline else theme.SURFACE
        self.setStyleSheet(f"""
            DeviceCard {{
                background-color: {bg};
                border: 1px solid {theme.BORDER};
                border-radius: {theme.RADIUS_CARD}px;
            }}
            """)

    def _build_controls(self) -> None:
        dtype = getattr(self.device, "device_type", "unknown")

        if dtype == "light":
            # On/Off switch row
            switch_row = QHBoxLayout()
            switch_row.setContentsMargins(0, 0, 0, 0)
            switch_label = QLabel("Power")
            switch_label.setStyleSheet(
                f"color: {theme.TEXT2}; font-size: {theme.FONT_LABEL}px;"
            )
            switch_row.addWidget(switch_label)
            switch_row.addStretch()

            is_on = bool(getattr(self.device.attributes, "is_on", False))
            self.switch = ToggleSwitch(accessible_name=f"{self.full_name} power")
            self.switch.setChecked(is_on)
            if self._on_toggle is not None:
                cb = self._on_toggle
                self.switch.toggled.connect(
                    lambda chk, callback=cb: callback(self, chk)
                )
            switch_row.addWidget(self.switch)
            self._controls.append(self.switch)
            self.control_zone.addLayout(switch_row)

            # Brightness slider, only for dimmable lights. `light_level` is an
            # Optional pydantic field, so hasattr() is always true; a light
            # without dimming reports None.
            lvl = getattr(self.device.attributes, "light_level", None)
            if lvl is not None:
                self.brightness_slider = LabeledSlider(
                    label="Level",
                    minimum=1,
                    maximum=100,
                    initial_value=lvl,
                    unit="%",
                )
                if self._on_brightness is not None:
                    cb_bright = self._on_brightness
                    self.brightness_slider.committed.connect(
                        lambda val, callback=cb_bright: callback(self, val)
                    )
                self.brightness_slider.setAccessibleName(f"{self.full_name} brightness")
                self._controls.append(self.brightness_slider)
                self.control_zone.addWidget(self.brightness_slider)

        elif dtype == "outlet":
            # Power toggle switch
            switch_row = QHBoxLayout()
            switch_row.setContentsMargins(0, 0, 0, 0)
            switch_label = QLabel("Power")
            switch_label.setStyleSheet(
                f"color: {theme.TEXT2}; font-size: {theme.FONT_LABEL}px;"
            )
            switch_row.addWidget(switch_label)
            switch_row.addStretch()

            is_on = bool(getattr(self.device.attributes, "is_on", False))
            self.switch = ToggleSwitch(accessible_name=f"{self.full_name} power")
            self.switch.setChecked(is_on)
            if self._on_toggle is not None:
                cb_toggle = self._on_toggle
                self.switch.toggled.connect(
                    lambda chk, callback=cb_toggle: callback(self, chk)
                )
            switch_row.addWidget(self.switch)
            self._controls.append(self.switch)
            self.control_zone.addLayout(switch_row)

        elif dtype == "blinds":
            # Position slider
            pos = getattr(self.device.attributes, "blinds_current_level", 0) or 0
            self.blind_slider = LabeledSlider(
                label="Open",
                minimum=0,
                maximum=100,
                initial_value=pos,
                unit="%",
            )
            if self._on_blind_position is not None:
                cb_pos = self._on_blind_position
                self.blind_slider.committed.connect(
                    lambda val, callback=cb_pos: callback(self, val)
                )
            self.blind_slider.setAccessibleName(f"{self.full_name} position")
            self._controls.append(self.blind_slider)
            self.control_zone.addWidget(self.blind_slider)

            # Up / Down / Stop action buttons if supported
            can_receive = getattr(
                getattr(self.device, "capabilities", None), "can_receive", []
            )
            # pydantic models always expose the field, so hasattr() would be
            # true even without support — check for an actual value instead.
            supports_state = (
                getattr(self.device.attributes, "blinds_state", None) is not None
            )
            if "blindsState" in can_receive or supports_state:
                btn_row = QHBoxLayout()
                btn_row.setContentsMargins(0, 0, 0, 0)
                btn_row.setSpacing(theme.SP8)
                for action in ("Up", "Down", "Stop"):
                    btn = QPushButton(action)
                    btn.setFixedHeight(28)
                    btn.setAccessibleName(f"{self.full_name} {action.lower()}")
                    if self._on_blind_state is not None:
                        cb_state = self._on_blind_state
                        btn.clicked.connect(
                            lambda _, a=action, callback=cb_state: callback(self, a)
                        )
                    btn_row.addWidget(btn)
                    self._controls.append(btn)
                self.control_zone.addLayout(btn_row)

        elif dtype in _READINGS:
            self._readings_box = QWidget()
            self.control_zone.addWidget(self._readings_box)
            self._fill_readings()

        elif dtype == "electricalSensor":
            # Power metric display (closes t-13)
            attrs = getattr(self.device, "attributes", None)
            power = getattr(attrs, "current_active_power", None)
            self.power_metric = MetricWidget(
                caption="Active power", initial_value=power, unit="W"
            )
            self.control_zone.addWidget(self.power_metric)

    def _reading_values(self) -> dict[str, Any]:
        """The non-None readings of this device, keyed by attribute name."""
        attrs = getattr(self.device, "attributes", None)
        values: dict[str, Any] = {}
        for _caption, _unit, attr in _READINGS.get(
            getattr(self.device, "device_type", ""), ()
        ):
            value = getattr(attrs, attr, None)
            if value is None:
                continue
            if attr == "fan_mode":
                # An enum in the library; show the word ("Auto").
                value = str(getattr(value, "value", value)).capitalize()
            values[attr] = value
        return values

    def _fill_readings(self) -> None:
        """(Re)build the metric grid for the readings the device reports."""
        box = self._readings_box
        if box is None:
            return
        values = self._reading_values()
        old = box.layout()
        if old is not None:
            while old.count():
                item = old.takeAt(0)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    widget.deleteLater()
            QWidget().setLayout(old)  # detach the old layout from the box
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(theme.SP16)
        grid.setVerticalSpacing(theme.SP12)
        self._readings = {}
        dtype = getattr(self.device, "device_type", "")
        for caption, unit, attr in _READINGS.get(dtype, ()):
            if attr not in values:
                continue
            metric = MetricWidget(caption=caption, initial_value=None, unit=unit)
            metric.set_value(values[attr])
            index = len(self._readings)
            grid.addWidget(metric, index // READINGS_PER_ROW, index % READINGS_PER_ROW)
            self._readings[attr] = metric
        for column in range(READINGS_PER_ROW):
            grid.setColumnStretch(column, 1)
        box.setVisible(bool(self._readings))

    def _sync_readings(self) -> None:
        """Update the readings in place; rebuild only if the set changed."""
        if self._readings_box is None:
            return
        values = self._reading_values()
        if set(values) != set(self._readings):
            self._fill_readings()
            return
        for attr, metric in self._readings.items():
            metric.set_value(values[attr])

    def _set_chip(self, text: str, variant: str) -> None:
        """Show the state chip, or hide it when there is no state to show."""
        self.status_chip.set_status(text, variant)
        self.status_chip.setVisible(bool(text))

    def _update_status_chip(self) -> None:
        attrs = getattr(self.device, "attributes", None)
        dtype = getattr(self.device, "device_type", "unknown")

        # Reachability
        is_reachable = getattr(self.device, "is_reachable", True)
        if not is_reachable:
            self.set_offline(True)
            return

        # On / Off states
        if dtype in ("light", "outlet"):
            is_on = getattr(attrs, "is_on", None)
            if is_on is True:
                self._set_chip("On", "ok")
            elif is_on is False:
                self._set_chip("Off", "neutral")
            else:
                self._set_chip("", "neutral")
        elif dtype == "blinds":
            lvl = getattr(attrs, "blinds_current_level", None)
            if lvl == 100:
                self._set_chip("Open", "neutral")
            elif lvl == 0:
                self._set_chip("Closed", "neutral")
            elif lvl is not None:
                self._set_chip("Partly open", "neutral")
            else:
                self._set_chip("", "neutral")
        elif dtype in ("motionSensor", "occupancySensor"):
            detected = getattr(attrs, "is_detected", None)
            if detected is True:
                self._set_chip("Motion", "ok")
            elif detected is False:
                self._set_chip("Clear", "neutral")
            else:
                self._set_chip("", "neutral")
        elif dtype == "openCloseSensor":
            is_open = getattr(attrs, "is_open", None)
            if is_open is None:
                self._set_chip("", "neutral")
            else:
                self._set_chip("Open" if is_open else "Closed", "neutral")
        elif dtype == "waterSensor":
            leak = getattr(attrs, "water_leak_detected", None)
            if leak is True:
                self._set_chip("Leak", "danger")
            elif leak is False:
                self._set_chip("Dry", "neutral")
            else:
                self._set_chip("", "neutral")
        else:
            # No readable state (remotes, air quality sensors): no chip
            # rather than an invented one (design-doc.md §1 principle 1).
            self._set_chip("", "neutral")

        # A low battery is the one fact that overrides the state chip (§8.1
        # state 4). It lives here, not in the footer, so the order in which
        # chip and footer are refreshed cannot hide it.
        battery = getattr(attrs, "battery_percentage", None)
        if isinstance(battery, (int, float)) and battery <= LOW_BATTERY_PERCENT:
            self._set_chip("Low battery", "warn")

    def _style_footer(self, danger: bool) -> None:
        color = theme.DANGER if danger else theme.TEXT2
        self.footer_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: {theme.FONT_CAPTION}px;
                background-color: transparent;
            }}
            """)

    def _set_footer(self, text: str) -> None:
        """Show `text`, unless a command error is being shown (danger tone)."""
        if self._error is not None and text != "Sending…":
            self.footer_label.setText(self._error)
            self._style_footer(danger=True)
        else:
            self.footer_label.setText(text)
            self._style_footer(danger=False)

    def show_error(self, message: str) -> None:
        """Show `message` in the footer in danger tone for CARD_ERROR_MS."""
        self._error = message
        self._error_timer.start()
        if self._pending:
            return
        if self._is_offline:
            self._set_footer(self._offline_text())
        else:
            self._update_footer()

    def _clear_error(self) -> None:
        self._error = None
        if self._pending:
            return
        if self._is_offline:
            self._set_footer(self._offline_text())
        else:
            self._update_footer()

    def _offline_text(self) -> str:
        """Footer of an offline card: when it was last seen, if known."""
        seen = getattr(self.device, "last_seen", None)
        if not isinstance(seen, datetime):
            return "Device unreachable"
        return f"Last seen {relative_time(seen, datetime.now(seen.tzinfo))}"

    def _update_footer(self) -> None:
        if self._pending:
            self._set_footer("Sending…")
            return
        attrs = getattr(self.device, "attributes", None)
        dtype = getattr(self.device, "device_type", "unknown")

        # Battery level
        battery = getattr(attrs, "battery_percentage", None)
        if isinstance(battery, (int, float)):
            self._set_footer(f"Battery {int(battery)}%")
            return

        # Electrical sensors and metering outlets: the energy readings. An
        # outlet has no power metric on its card, so its footer leads with W.
        power = getattr(attrs, "current_active_power", None)
        if dtype == "electricalSensor" or (dtype == "outlet" and power is not None):
            text = energy_footer(attrs, with_power=dtype == "outlet")
            if text:
                self._set_footer(text)
                return

        self._set_footer("")

    def set_offline(self, offline: bool) -> None:
        """Mark card offline: sunken background, disabled controls, offline chip."""
        self._is_offline = offline
        self._apply_card_style(is_offline=offline)
        for ctrl in self._controls:
            ctrl.setEnabled(not offline)
        if offline:
            self._set_chip("Offline", "neutral")
            if not self._pending:
                self._set_footer(self._offline_text())
        else:
            self._update_status_chip()
            self._update_footer()

    def set_pending(self, pending: bool) -> None:
        """Show pending command status in footer."""
        if pending:
            self._set_footer("Sending…")
        else:
            self._update_footer()

    def sync_from_device(self) -> None:
        """Resync every control, the chip and the footer from `self.device`.

        Called after a command finishes: on success the library has already
        written the new value into `device.attributes`; on failure the device
        was reloaded, so the card shows the real state (req-3). Signals are
        blocked so the resync never sends a command of its own.
        """
        self._sync(protect_user=False)

    def update_from_device(self, device: Any) -> None:
        """Adopt a freshly fetched `device` and resync the existing controls.

        Used by automated refreshes (t-19): no widget is recreated, and a
        slider the user is dragging or has focused keeps its value (req-13).
        """
        self.device = device
        raw_name = getattr(device.attributes, "custom_name", None) or getattr(
            device, "id", "Unknown Device"
        )
        if raw_name != self.full_name:
            self.full_name = raw_name
            self.name_label.setToolTip(raw_name)
            self._elide_name()
        self._sync(protect_user=True)

    def _sync(self, protect_user: bool) -> None:
        attrs = getattr(self.device, "attributes", None)
        switch = getattr(self, "switch", None)
        if isinstance(switch, ToggleSwitch):
            switch.blockSignals(True)
            switch.setChecked(bool(getattr(attrs, "is_on", False)))
            switch.blockSignals(False)
        for name, attr in (
            ("brightness_slider", "light_level"),
            ("blind_slider", "blinds_current_level"),
        ):
            slider = getattr(self, name, None)
            value = getattr(attrs, attr, None)
            if not isinstance(slider, LabeledSlider) or value is None:
                continue
            if protect_user and slider.is_user_active():
                continue
            slider.blockSignals(True)
            slider.set_value(int(value))
            slider.blockSignals(False)
        self._sync_readings()
        metric = getattr(self, "power_metric", None)
        if isinstance(metric, MetricWidget):
            metric.set_value(getattr(attrs, "current_active_power", None))
        self.set_offline(not getattr(self.device, "is_reachable", True))
        self._elide_name()  # the chip text may have changed width
