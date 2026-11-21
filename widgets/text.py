"""Pure text helpers for cards (no Qt): relative times and type captions."""

import re
from datetime import datetime

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
