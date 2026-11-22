"""
Device card component.

Follows design-doc.md §8.1 (header, footer and error handling live in
`widgets/cardbase.py`):
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

import functools
from datetime import datetime
from typing import Any, Callable, Optional, Sequence, Tuple, cast, override

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QStandardItemModel, QWheelEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import theme
from adaptive import UNKNOWN_PROFILE, active_profile_id, supports_adaptive
from widgets.cardbase import CardBase, device_name, label_style
from widgets.metric import MetricWidget
from widgets.segments import SegmentedControl
from widgets.slider import LabeledSlider
from widgets.switch import ToggleSwitch
from widgets.text import energy_footer, filter_text, pm25_band, relative_time

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

# PM2.5 is in µg/m³; its reading also gets a band word (t-88).
PM25_UNIT = "µg/m³"

# Read-only readings per device type: (caption, unit, attribute). Units the
# library does not document are left empty rather than guessed
# (dirigera-api.md §1 finding 7). Only values that are not None are shown.
_READINGS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "environmentSensor": (
        ("Temperature", "°C", "current_temperature"),
        ("Humidity", "%", "current_r_h"),
        ("PM2.5", PM25_UNIT, "current_p_m25"),
        ("CO₂", "ppm", "current_c_o2"),
        ("VOC index", "", "voc_index"),
    ),
    "lightSensor": (("Illuminance", "", "illuminance"),),
    "airPurifier": (("PM2.5", PM25_UNIT, "current_p_m25"),),
}

# Fan segments of the air purifier card (req-15): the labels, and the
# `motorState` each one sends (0 off, 1 auto, 10 to 50 speeds 1 to 5).
FAN_SPEED_LABELS = ("Off", "Auto", "1", "2", "3", "4", "5")
FAN_MOTOR_STATES = (0, 1, 10, 20, 30, 40, 50)

# Adaptive profile row of a light card (t-15, design-doc.md §8.1).
ADAPTIVE_LABEL = "Adaptive"
OFF_LABEL = "Off"
LEAVE_HINT = "Change brightness or warmth to stop following the profile"
# Quiet time after the last pick before the profile is sent; read when the
# timer starts, so tests can change it.
PROFILE_COMMIT_MS = 300

# Readings shown side by side before the next row starts (§8.5.3).
READINGS_PER_ROW = 3

# Battery level at or below which the chip warns (design-doc.md §14 item 4).
LOW_BATTERY_PERCENT = 20


def _const(value: Any, *_ignored: Any) -> Any:
    """Return `value`, whatever the signal passes (binds a button's action)."""
    return value


def _bound_to_kelvin(bound: int) -> int:
    """Normalise a colour temperature bound to Kelvin the way the library does.

    Some bulbs report their bounds in mireds (153 to 454); no Kelvin value is
    below 1000 and no mired value above it.
    """
    if 0 < bound < 1000:
        return round(1_000_000 / bound)
    return bound


def kelvin_bounds(attrs: Any) -> Optional[Tuple[int, int]]:
    """(lowest, highest) Kelvin the light accepts, or None when unknown."""
    low = getattr(attrs, "color_temperature_min", None)
    high = getattr(attrs, "color_temperature_max", None)
    if not isinstance(low, int) or not isinstance(high, int):
        return None
    bounds = (_bound_to_kelvin(low), _bound_to_kelvin(high))
    lower, upper = min(bounds), max(bounds)
    return (lower, upper) if lower < upper else None


def _set_reading(metric: MetricWidget, attr: str, value: Any) -> None:
    """Show a reading; PM2.5 also gets its band word and tone (t-88)."""
    metric.set_value(value)
    band = pm25_band(value) if attr == "current_p_m25" else None
    if band is None:
        metric.set_note()
    else:
        metric.set_note(*band)


def fan_speed_index(motor_state: Any, fan_mode: Any) -> Optional[int]:
    """The FAN_SPEED_LABELS index of a purifier's fan setting, None if unknown.

    Auto is `fan_mode` "auto" or `motor_state` 1. While in auto the hub reports
    the speed it picked (e.g. 30) in `motor_state`, so auto wins over the
    number. Off is `motor_state` 0 or `fan_mode` "off". Otherwise the speed
    is `motor_state` / 10, clamped to 1 to 5. `fan_mode` may be the library's
    enum or its string value.
    """
    mode = getattr(fan_mode, "value", fan_mode)
    state = (
        motor_state
        if isinstance(motor_state, int) and not isinstance(motor_state, bool)
        else None
    )
    if mode == "auto" or state == 1:
        return 1
    if state == 0 or mode == "off":
        return 0
    if state is None:
        return None
    return min(5, max(1, round(state / 10))) + 1


def _can_receive(device: Any) -> list[str]:
    return list(getattr(getattr(device, "capabilities", None), "can_receive", []))


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


class ProfileBox(QComboBox):
    """The adaptive profile picker; the mouse wheel never changes it.

    Cards sit in a scroll area: a wheel turn over a card must scroll the
    page, not switch a light's profile (doc/qt-gotchas.md).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Profile names are user-chosen: never let them widen the card.
        self.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.setMinimumContentsLength(8)

    @override
    def wheelEvent(self, e: Optional[QWheelEvent]) -> None:
        if e is not None:
            e.ignore()


class DeviceCard(CardBase):
    """Calm, structured card representation of a single smart home device."""

    def __init__(
        self,
        device: Any,
        on_toggle: Optional[Callable[["DeviceCard", bool], None]] = None,
        on_brightness: Optional[Callable[["DeviceCard", int], None]] = None,
        on_blind_position: Optional[Callable[["DeviceCard", int], None]] = None,
        on_temperature: Optional[Callable[["DeviceCard", int], None]] = None,
        on_blind_state: Optional[Callable[["DeviceCard", str], None]] = None,
        on_colour: Optional[Callable[["DeviceCard", float, float], None]] = None,
        on_fan_speed: Optional[Callable[["DeviceCard", int], None]] = None,
        on_profile: Optional[Callable[["DeviceCard", Optional[str]], None]] = None,
        profiles: Sequence[Tuple[str, str]] = (),
        parent=None,
    ):
        """Build the card. Every callback receives the card itself, so the
        handler can reach `card.device` and resync the card afterwards with
        `sync_from_device()`."""
        super().__init__(device, parent)
        self._on_toggle = on_toggle
        self._on_brightness = on_brightness
        self._on_blind_position = on_blind_position
        self._on_temperature = on_temperature
        self._on_colour = on_colour
        self._on_blind_state = on_blind_state
        self._on_fan_speed = on_fan_speed
        self._on_profile = on_profile
        self._profile_opts: Tuple[Tuple[str, str], ...] = tuple(profiles)
        self._profile_timer = QTimer(self)
        self._profile_timer.setSingleShot(True)
        self._profile_timer.timeout.connect(self._commit_profile)

        self._controls: list[QWidget] = []
        self._readings_box: Optional[QWidget] = None
        self._fan_box: Optional[QWidget] = None
        self._readings: dict[str, MetricWidget] = {}

        # Control zone: 0 to 3 controls depending on device type.
        self.control_zone = QVBoxLayout()
        self.control_zone.setContentsMargins(0, 0, 0, 0)
        self.control_zone.setSpacing(theme.SP8)
        self._build_controls()
        if self.control_zone.count() > 0:
            self.card_layout.addLayout(self.control_zone)

        # Footer row, then the initial status chip sync.
        self._init_footer()
        self._update_status_chip()
        self._elide_name()

    def _connect_callback(
        self,
        signal: Any,
        callback: Optional[Callable[..., None]],
        convert: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        """Call `callback(card, value)` when `signal` fires, if there is a callback.

        `convert` maps the signal's argument to the value passed on.
        """
        if callback is None:
            return
        signal.connect(
            lambda value, cb=callback: cb(
                self, convert(value) if convert is not None else value
            )
        )

    def _power_row(self) -> None:
        """A "Power" label with an on/off switch, shared by lights and outlets."""
        switch_row = QHBoxLayout()
        switch_row.setContentsMargins(0, 0, 0, 0)
        switch_label = QLabel("Power")
        switch_label.setStyleSheet(label_style(theme.TEXT2, theme.FONT_LABEL))
        switch_row.addWidget(switch_label)
        switch_row.addStretch()

        is_on = bool(getattr(self.device.attributes, "is_on", False))
        self.switch = ToggleSwitch(accessible_name=f"{self.full_name} power")
        self.switch.setChecked(is_on)
        self._connect_callback(self.switch.toggled, self._on_toggle)
        switch_row.addWidget(self.switch)
        self._controls.append(self.switch)
        self.control_zone.addLayout(switch_row)

    def _build_controls(self) -> None:
        dtype = getattr(self.device, "device_type", "unknown")

        if dtype == "light":
            self._power_row()

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
                self._connect_callback(
                    self.brightness_slider.committed, self._on_brightness
                )
                self.brightness_slider.setAccessibleName(f"{self.full_name} brightness")
                self._controls.append(self.brightness_slider)
                self.control_zone.addWidget(self.brightness_slider)

            # Colour temperature, only where the light accepts it (§1 finding 1).
            bounds = kelvin_bounds(self.device.attributes)
            if "colorTemperature" in _can_receive(self.device) and bounds:
                kelvin = getattr(self.device.attributes, "color_temperature", None)
                self.temperature_slider = LabeledSlider(
                    label="Warmth",
                    minimum=bounds[0],
                    maximum=bounds[1],
                    initial_value=kelvin if isinstance(kelvin, int) else bounds[0],
                    unit="K",
                    gradient=(theme.TEMP_WARM, theme.TEMP_COOL),
                )
                self._connect_callback(
                    self.temperature_slider.committed, self._on_temperature
                )
                self.temperature_slider.setAccessibleName(
                    f"{self.full_name} colour temperature"
                )
                self._controls.append(self.temperature_slider)
                self.control_zone.addWidget(self.temperature_slider)

            if supports_adaptive(self.device):
                self._build_profile_row()

            if {"colorHue", "colorSaturation"} <= set(_can_receive(self.device)):
                self._build_colour_controls()

        elif dtype == "outlet":
            self._power_row()

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
            self._connect_callback(self.blind_slider.committed, self._on_blind_position)
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
                    self._connect_callback(
                        btn.clicked,
                        self._on_blind_state,
                        functools.partial(_const, action),
                    )
                    btn_row.addWidget(btn)
                    self._controls.append(btn)
                self.control_zone.addLayout(btn_row)

        elif dtype in _READINGS:
            if dtype == "airPurifier":
                self._build_fan_control()
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

    def _build_profile_row(self) -> None:
        """An "Adaptive" label with a picker: Off, then the hub's profiles.

        Hidden while the hub has no profiles (t-15). Choosing sends once, after
        a short quiet time, like the sliders (req-6).
        """
        self._profile_row = QWidget()
        row = QHBoxLayout(self._profile_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(theme.SP8)
        label = QLabel(ADAPTIVE_LABEL)
        label.setStyleSheet(label_style(theme.TEXT2, theme.FONT_LABEL))
        row.addWidget(label)
        self.profile_box = ProfileBox()
        self.profile_box.setAccessibleName(f"{self.full_name} adaptive profile")
        self.profile_box.activated.connect(self._on_profile_picked)
        row.addWidget(self.profile_box, stretch=1)
        self._controls.append(self.profile_box)
        self.control_zone.addWidget(self._profile_row)
        self._fill_profiles()

    def set_profiles(self, options: Sequence[Tuple[str, str]]) -> None:
        """Adopt the hub's `(id, label)` profile list; sends nothing."""
        options = tuple(options)
        if options == self._profile_opts:
            return
        self._profile_opts = options
        self._fill_profiles()

    def _fill_profiles(self) -> None:
        box = getattr(self, "profile_box", None)
        if not isinstance(box, ProfileBox):
            return
        box.blockSignals(True)
        box.clear()
        box.addItem(OFF_LABEL, None)
        for profile_id, text in self._profile_opts:
            box.addItem(text, profile_id)
        box.blockSignals(False)
        self._profile_row.setVisible(bool(self._profile_opts))
        self._sync_profile(protect_user=False)

    def _sync_profile(self, protect_user: bool) -> None:
        """Show the profile the light follows; sends nothing.

        "Off" cannot be chosen while a profile is active: the library has no
        way to leave adaptive mode (dirigera-api.md §5 item 7), the hint says
        what ends it. A profile missing from the list shows as unknown.
        """
        box = getattr(self, "profile_box", None)
        if not isinstance(box, ProfileBox):
            return
        if protect_user and (self._profile_timer.isActive() or self._popup_open(box)):
            return
        active = active_profile_id(self.device)
        box.blockSignals(True)
        if box.count() > len(self._profile_opts) + 1:  # a stale unknown item
            box.removeItem(box.count() - 1)
        model = cast(QStandardItemModel, box.model())
        if active is None:
            box.setCurrentIndex(0)
        else:
            index = box.findData(active)
            if index < 0:
                box.addItem(UNKNOWN_PROFILE, active)
                index = box.count() - 1
                unknown = model.item(index)
                if unknown is not None:
                    unknown.setEnabled(False)
            box.setCurrentIndex(index)
        off_item = model.item(0)
        if off_item is not None:
            off_item.setEnabled(active is None)
        box.setToolTip("" if active is None else LEAVE_HINT)
        box.blockSignals(False)

    @staticmethod
    def _popup_open(box: QComboBox) -> bool:
        view = box.view()
        return view is not None and view.isVisible()

    def _on_profile_picked(self, _index: int) -> None:
        self._profile_timer.start(PROFILE_COMMIT_MS)

    def _commit_profile(self) -> None:
        """Send the last pick, unless it is what the light already follows."""
        data = self.profile_box.currentData()
        if data != active_profile_id(self.device) and self._on_profile is not None:
            self._on_profile(self, data)

    def _build_colour_controls(self) -> None:
        """A "Colour" button that reveals hue and saturation sliders.

        Hidden by default so the card stays calm (dirigera-api.md §3 row 1).
        """
        attrs = self.device.attributes
        hue = getattr(attrs, "color_hue", None)
        sat = getattr(attrs, "color_saturation", None)
        self.colour_button = QPushButton("Colour")
        self.colour_button.setCheckable(True)
        self.colour_button.setFixedHeight(28)
        self.colour_button.setAccessibleName(f"{self.full_name} colour controls")
        self.hue_slider = LabeledSlider(
            label="Hue",
            minimum=0,
            maximum=360,
            initial_value=round(hue) if hue is not None else 0,
            unit="°",
        )
        self.hue_slider.setAccessibleName(f"{self.full_name} hue")
        self.saturation_slider = LabeledSlider(
            label="Sat.",
            minimum=0,
            maximum=100,
            initial_value=round(sat * 100) if sat is not None else 0,
            unit="%",
        )
        self.saturation_slider.setAccessibleName(f"{self.full_name} saturation")
        self.colour_box = QWidget()
        box_layout = QVBoxLayout(self.colour_box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(theme.SP8)
        box_layout.addWidget(self.hue_slider)
        box_layout.addWidget(self.saturation_slider)
        self.colour_box.setVisible(False)
        self.colour_button.toggled.connect(self.colour_box.setVisible)
        for slider in (self.hue_slider, self.saturation_slider):
            slider.committed.connect(self._commit_colour)
        self._controls += [self.colour_button, self.hue_slider, self.saturation_slider]
        self.control_zone.addWidget(self.colour_button)
        self.control_zone.addWidget(self.colour_box)

    def _commit_colour(self, _value: int) -> None:
        """Send both current values; the hub takes hue and saturation together."""
        if self._on_colour is not None:
            self._on_colour(
                self,
                float(self.hue_slider.value()),
                self.saturation_slider.value() / 100,
            )

    def _build_fan_control(self) -> None:
        """A "Fan" label over Off, Auto and speeds 1 to 5 (req-15).

        Hidden while the device reports no fan setting, rather than showing
        a segment that would be invented.
        """
        self._fan_box = QWidget()
        box_layout = QVBoxLayout(self._fan_box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(theme.SP4)
        fan_label = QLabel("Fan")
        fan_label.setStyleSheet(label_style(theme.TEXT2, theme.FONT_LABEL))
        box_layout.addWidget(fan_label)
        self.fan_speed = SegmentedControl(list(FAN_SPEED_LABELS))
        self.fan_speed.setAccessibleName(f"{self.full_name} fan speed")
        self._connect_callback(
            self.fan_speed.current_changed,
            self._on_fan_speed,
            lambda index: FAN_MOTOR_STATES[index],
        )
        box_layout.addWidget(self.fan_speed)
        self._controls.append(self.fan_speed)
        self.control_zone.addWidget(self._fan_box)
        self._sync_fan_speed()

    def _sync_fan_speed(self) -> None:
        """Select the segment for the device's fan setting, without a command."""
        control = getattr(self, "fan_speed", None)
        if not isinstance(control, SegmentedControl):
            return
        attrs = getattr(self.device, "attributes", None)
        index = fan_speed_index(
            getattr(attrs, "motor_state", None), getattr(attrs, "fan_mode", None)
        )
        control.blockSignals(True)
        if index is not None:
            control.set_current(index)
        control.blockSignals(False)
        if self._fan_box is not None:
            self._fan_box.setVisible(index is not None)

    def _reading_values(self) -> dict[str, Any]:
        """The non-None readings of this device, keyed by attribute name."""
        attrs = getattr(self.device, "attributes", None)
        values: dict[str, Any] = {}
        for _caption, _unit, attr in _READINGS.get(
            getattr(self.device, "device_type", ""), ()
        ):
            value = getattr(attrs, attr, None)
            if value is not None:
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
            _set_reading(metric, attr, values[attr])
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
            _set_reading(metric, attr, values[attr])

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
        elif dtype == "airPurifier":
            # Only the filter alarm is a state worth a chip (req-20).
            if getattr(attrs, "filter_alarm_status", None) is True:
                self._set_chip("Change filter", "warn")
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

    @override
    def _offline_footer(self) -> Optional[str]:
        return self._offline_text()

    def _offline_text(self) -> str:
        """Footer of an offline card: when it was last seen, if known."""
        seen = getattr(self.device, "last_seen", None)
        if not isinstance(seen, datetime):
            return "Device unreachable"
        return f"Last seen {relative_time(seen, datetime.now(seen.tzinfo))}"

    @override
    def _update_footer(self) -> None:
        attrs = getattr(self.device, "attributes", None)
        dtype = getattr(self.device, "device_type", "unknown")

        # Battery level
        battery = getattr(attrs, "battery_percentage", None)
        if isinstance(battery, (int, float)):
            self._set_footer(f"Battery {int(battery)}%")
            return

        # Air purifier: filter life left (req-20).
        if dtype == "airPurifier":
            text = filter_text(
                getattr(attrs, "filter_lifetime", None),
                getattr(attrs, "filter_elapsed_time", None),
                getattr(attrs, "filter_alarm_status", None),
            )
            if text is not None:
                self._set_footer(text)
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
        self._apply_controls_enabled()
        if offline:
            self._set_chip("Offline", "neutral")
            self._set_footer(self._offline_text())
        else:
            self._update_status_chip()
            self._update_footer()

    def _apply_controls_enabled(self) -> None:
        """Controls work while the card is online and no command runs."""
        enabled = not self._is_offline and not self.is_pending
        for ctrl in self._controls:
            ctrl.setEnabled(enabled)

    @override
    def _on_pending_changed(self) -> None:
        self._apply_controls_enabled()

    def refresh_offline_footer(self) -> None:
        """Recompute "Last seen ..." (it ages while the data stays the same)."""
        if self._is_offline:
            self._set_footer(self._offline_text())

    @override
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
        self._set_name(device_name(device))
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
            ("temperature_slider", "color_temperature"),
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
        for name, attr, scale in (
            ("hue_slider", "color_hue", 1),
            ("saturation_slider", "color_saturation", 100),
        ):
            slider = getattr(self, name, None)
            value = getattr(attrs, attr, None)
            if not isinstance(slider, LabeledSlider) or value is None:
                continue
            if protect_user and slider.is_user_active():
                continue
            slider.blockSignals(True)
            slider.set_value(round(value * scale))
            slider.blockSignals(False)
        self._sync_profile(protect_user)
        self._sync_fan_speed()
        self._sync_readings()
        metric = getattr(self, "power_metric", None)
        if isinstance(metric, MetricWidget):
            metric.set_value(getattr(attrs, "current_active_power", None))
        self.set_offline(not getattr(self.device, "is_reachable", True))
        self._elide_name()  # the chip text may have changed width
