"""Icons: device glyphs are keyed by the library's real `device_type`."""

from typing import Any

import pytest

from widgets.icons import render_icon

DEVICE_TYPES = [
    "light",
    "outlet",
    "blinds",
    "airPurifier",
    "environmentSensor",
    "electricalSensor",
    "motionSensor",
    "openCloseSensor",
    "occupancySensor",
    "waterSensor",
    "lightSensor",
    "lightController",
    "shortcutController",
]


@pytest.mark.parametrize("device_type", DEVICE_TYPES)
def test_every_device_type_has_a_glyph(qapp: Any, device_type: str) -> None:
    assert not render_icon(device_type, "#000000").isNull()


def test_unknown_name_renders_nothing(qapp: Any) -> None:
    assert render_icon("noSuchThing", "#000000").isNull()
