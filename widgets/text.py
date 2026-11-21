"""Pure text helpers for cards (no Qt): relative times and type captions."""

import re
from datetime import date, datetime
from typing import Any, Optional

# The library's `device_type` strings, which are camelCase (see
# `.venv/Lib/site-packages/dirigera/hub/hub.py`).
_TYPE_LABELS = {
    "light": "Light",
    "outlet": "Plug",
    "blinds": "Blind",
    "airPurifier": "Air purifier",
    "environmentSensor": "Environment sensor",
    "motionSensor": "Motion sensor",
    "occupancySensor": "Occupancy sensor",
    "openCloseSensor": "Door or window sensor",
    "waterSensor": "Water leak sensor",
    "lightSensor": "Light sensor",
    "electricalSensor": "Energy meter",
}


def relative_time(then: datetime, now: datetime) -> str:
    """Return how long ago `then` was: "just now", "5 min ago", "3 h ago",
    "yesterday", else the date as `%d %b`. Both must be naive or both aware."""
    seconds = (now - then).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    if (now.date() - then.date()).days == 1:
        return "yesterday"
    return then.strftime("%d %b")


def type_label(device_type: str) -> str:
    """Return a sentence-case caption for a `device_type` value.

    Every controller type (`lightController`, `shortcutController`, ...) is a
    "Remote". Unknown types are split at the camelCase boundaries.
    """
    if device_type in _TYPE_LABELS:
        return _TYPE_LABELS[device_type]
    if device_type.endswith("Controller"):
        return "Remote"
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", device_type).replace("_", " ")
    words = words.strip().lower()
    return words[:1].upper() + words[1:] if words else "Device"


def _number(attrs: Any, name: str) -> Optional[float]:
    value = getattr(attrs, name, None)
    return value if isinstance(value, (int, float)) else None


def format_power(attrs: Any) -> Optional[str]:
    """Active power as "12 W", None when unreported."""
    value = _number(attrs, "current_active_power")
    return None if value is None else f"{value:.0f} W"


def format_volts(attrs: Any) -> Optional[str]:
    """Voltage as "230 V", None when unreported."""
    value = _number(attrs, "current_voltage")
    return None if value is None else f"{value:.0f} V"


def format_amps(attrs: Any) -> Optional[str]:
    """Current as "0.05 A", None when unreported."""
    value = _number(attrs, "current_amps")
    return None if value is None else f"{value:.2f} A"


def format_kwh(attrs: Any) -> Optional[str]:
    """Total energy as "1.50 kWh", None when unreported."""
    value = _number(attrs, "total_energy_consumed")
    return None if value is None else f"{value:.2f} kWh"


def usage_kwh(attrs: Any) -> Optional[float]:
    """Energy used since the last reset, in kWh, None when unreported.

    `total_energy_consumed` never resets; the hub keeps the total at the last
    reset in `energy_consumed_at_last_reset`. Without that value the total
    is the usage (docs/dirigera-api.md §5 item 2).
    """
    total = _number(attrs, "total_energy_consumed")
    if total is None:
        return None
    at_reset = _number(attrs, "energy_consumed_at_last_reset")
    return total if at_reset is None else total - at_reset


def format_cost(kwh: float, price_per_kwh: float, currency: str) -> str:
    """The cost of `kwh` at `price_per_kwh`, e.g. "2.00 RON"."""
    return f"{kwh * price_per_kwh:.2f} {currency}"


def usage_text(
    attrs: Any, price_per_kwh: float, currency: str, today: date
) -> Optional[str]:
    """The usage line of an energy card with its cost, None when unreported.

    "Since 21 Nov: 1.30 kWh · 2.00 RON" once a reset time is known (with the
    year when it is not `today`'s), else "Usage 18.40 kWh · 28.34 RON".
    """
    kwh = usage_kwh(attrs)
    if kwh is None:
        return None
    cost = format_cost(kwh, price_per_kwh, currency)
    reset = getattr(attrs, "time_of_last_energy_reset", None)
    has_reset_value = _number(attrs, "energy_consumed_at_last_reset") is not None
    if isinstance(reset, datetime) and has_reset_value:
        # Aware timestamps are shown in local time, naive ones are taken as local.
        day = reset.astimezone().date()
        year = "" if day.year == today.year else f" {day.year}"
        return f"Since {day:%d %b}{year}: {kwh:.2f} kWh · {cost}"
    return f"Usage {kwh:.2f} kWh · {cost}"


def energy_footer(attrs: Any, with_power: bool = False) -> str:
    """The footer of a metered card: volts, amps and total, "·" separated.

    `with_power` puts the live power first, for cards that show no power
    metric of their own. Empty when nothing is reported.
    """
    parts = [format_power(attrs)] if with_power else []
    parts += [format_volts(attrs), format_amps(attrs), format_kwh(attrs)]
    return " · ".join(p for p in parts if p)


def _whole(value: Any) -> Optional[int]:
    """An int that is not a bool, else None (bools are ints in Python)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def filter_text(lifetime: Any, elapsed: Any, alarm: Any) -> Optional[str]:
    """Air purifier filter health from the hub's minutes, None when unknown.

    `lifetime` and `elapsed` are minutes (259200 = 180 days). The text says
    how much filter is left and when to change it. Past its lifetime it says
    by how many whole days the filter is overdue; under a day overdue, or an
    alarm with time left, says the filter is used up.
    """
    total = _whole(lifetime)
    used = _whole(elapsed)
    if total is None or total <= 0 or used is None:
        return None
    overdue_days = (used - total) // 1440
    if overdue_days >= 1:
        unit = "day" if overdue_days == 1 else "days"
        return f"Filter overdue by {overdue_days} {unit} · change now"
    remaining = max(0, total - used)
    if alarm is True or remaining == 0:
        return "Filter used up · change now"
    percent = round(100 * remaining / total)
    days = remaining // 1440
    if days == 0:
        when = "change today"
    elif days == 1:
        when = "change in 1 day"
    else:
        when = f"change in {days} days"
    return f"Filter {percent} % · {when}"
