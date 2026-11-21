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

from typing import Any, Callable, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import theme
from widgets.chip import StatusChip
from widgets.metric import MetricWidget
from widgets.slider import LabeledSlider
from widgets.switch import ToggleSwitch

# Device category sorting weight per design-doc.md §8.1 rule 3
_TYPE_SORT_WEIGHT = {
    "light": 10,
    "outlet": 20,
    "blinds": 30,
    "air_purifier": 40,
    "environment_sensor": 50,
    "electrical_sensor": 60,
    "sensor": 70,
    "open_close_sensor": 80,
    "motion_sensor": 90,
    "controller": 100,
}

# Battery level at or below which the chip warns (design-doc.md §15 item 4).
LOW_BATTERY_PERCENT = 20


def device_sort_key(device: Any) -> Tuple[int, str]:
    """Sort key for devices within a room: category weight then device name."""
    dtype = getattr(device, "device_type", "unknown")
    weight = _TYPE_SORT_WEIGHT.get(dtype, 999)
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
        self._is_offline = False

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
        titles_vbox.addWidget(self.name_label)

        raw_type = getattr(device, "device_type", "device").replace("_", " ")
        self.type_label = QLabel(raw_type.capitalize())
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
        self.footer_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.TEXT2};
                font-size: {theme.FONT_CAPTION}px;
                background-color: transparent;
            }}
            """)
        self._update_footer()
        card_layout.addWidget(self.footer_label)

        # Initial status chip sync
        self._update_status_chip()

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
                    self.brightness_slider.released.connect(
                        lambda val, callback=cb_bright: callback(self, val)
                    )
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
                self.blind_slider.released.connect(
                    lambda val, callback=cb_pos: callback(self, val)
                )
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
                    if self._on_blind_state is not None:
                        cb_state = self._on_blind_state
                        btn.clicked.connect(
                            lambda _, a=action, callback=cb_state: callback(self, a)
                        )
                    btn_row.addWidget(btn)
                    self._controls.append(btn)
                self.control_zone.addLayout(btn_row)

        elif dtype == "electrical_sensor":
            # Power metric display (closes t-13)
            attrs = getattr(self.device, "attributes", None)
            power = getattr(attrs, "current_active_power", None)
            self.power_metric = MetricWidget(
                caption="Active power", initial_value=power, unit="W"
            )
            self.control_zone.addWidget(self.power_metric)

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
                self.status_chip.set_status("On", "ok")
            elif is_on is False:
                self.status_chip.set_status("Off", "neutral")
            else:
                self.status_chip.set_status("Ready", "neutral")
        elif dtype == "blinds":
            lvl = getattr(attrs, "blinds_current_level", None)
            if lvl == 100:
                self.status_chip.set_status("Open", "neutral")
            elif lvl == 0:
                self.status_chip.set_status("Closed", "neutral")
            elif lvl is not None:
                self.status_chip.set_status(f"{lvl}%", "neutral")
            else:
                self.status_chip.set_status("Ready", "neutral")
        else:
            self.status_chip.set_status("Ready", "neutral")

        # A low battery is the one fact that overrides the state chip (§8.1
        # state 4). It lives here, not in the footer, so the order in which
        # chip and footer are refreshed cannot hide it.
        battery = getattr(attrs, "battery_percentage", None)
        if isinstance(battery, (int, float)) and battery <= LOW_BATTERY_PERCENT:
            self.status_chip.set_status("Low battery", "warn")

    def _update_footer(self) -> None:
        attrs = getattr(self.device, "attributes", None)
        dtype = getattr(self.device, "device_type", "unknown")

        # Battery level
        battery = getattr(attrs, "battery_percentage", None)
        if isinstance(battery, (int, float)):
            self.footer_label.setText(f"Battery {int(battery)}%")
            return

        # Electrical sensor secondary metrics
        if dtype == "electrical_sensor":
            v = getattr(attrs, "current_voltage", None)
            a = getattr(attrs, "current_amps", None)
            kwh = getattr(attrs, "total_energy_consumed", None)
            parts = []
            if isinstance(v, (int, float)):
                parts.append(f"{v:.0f} V")
            if isinstance(a, (int, float)):
                parts.append(f"{a:.2f} A")
            if isinstance(kwh, (int, float)):
                parts.append(f"{kwh:.2f} kWh")
            if parts:
                self.footer_label.setText(" · ".join(parts))
                return

        self.footer_label.setText("")

    def set_offline(self, offline: bool) -> None:
        """Mark card offline: sunken background, disabled controls, offline chip."""
        self._is_offline = offline
        self._apply_card_style(is_offline=offline)
        for ctrl in self._controls:
            ctrl.setEnabled(not offline)
        if offline:
            self.status_chip.set_status("Offline", "neutral")
            self.footer_label.setText("Device unreachable")
        else:
            self._update_status_chip()
            self._update_footer()

    def set_pending(self, pending: bool) -> None:
        """Show pending command status in footer."""
        if pending:
            self.footer_label.setText("Sending…")
        else:
            self._update_footer()

    def sync_from_device(self) -> None:
        """Resync every control, the chip and the footer from `self.device`.

        Called after a command finishes: on success the library has already
        written the new value into `device.attributes`; on failure the device
        was reloaded, so the card shows the real state (req-3). Signals are
        blocked so the resync never sends a command of its own.
        """
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
            if isinstance(slider, LabeledSlider) and value is not None:
                slider.blockSignals(True)
                slider.set_value(int(value))
                slider.blockSignals(False)
        self.set_offline(not getattr(self.device, "is_reachable", True))
