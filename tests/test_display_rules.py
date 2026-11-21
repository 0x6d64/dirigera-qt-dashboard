"""Display rules: PM2.5 bands, hidden devices and automatic scenes (t-88 to t-90)."""

from typing import Any

import pytest
from conftest import make_device

import theme
from widgets.card import DeviceCard
from widgets.text import pm25_band


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, ("Good", "ok")),
        (15, ("Good", "ok")),
        (15.1, ("Moderate", "warn")),
        (35, ("Moderate", "warn")),
        (35.5, ("Poor", "danger")),
        (36, ("Poor", "danger")),
        (None, None),
        (True, None),
        ("12", None),
    ],
)
def test_pm25_band_boundaries(value: Any, expected: Any) -> None:
    assert pm25_band(value) == expected


def test_environment_sensor_shows_the_pm25_band_word(qapp: Any) -> None:
    card = DeviceCard(make_device("environmentSensor", current_p_m25=7))
    metric = card._readings["current_p_m25"]
    assert metric.unit_text == "µg/m³"
    assert metric.note_text == "Good"
    assert metric.note_colour == theme.OK


def test_pm25_band_follows_each_refresh(qapp: Any) -> None:
    card = DeviceCard(make_device("environmentSensor", current_p_m25=7))
    metric = card._readings["current_p_m25"]
    card.update_from_device(make_device("environmentSensor", current_p_m25=20))
    assert metric.note_text == "Moderate"
    assert metric.note_colour == theme.WARN
    card.update_from_device(make_device("environmentSensor", current_p_m25=50))
    assert metric.note_text == "Poor"
    assert metric.note_colour == theme.DANGER


def test_purifier_shows_the_pm25_band_word(qapp: Any) -> None:
    card = DeviceCard(make_device("airPurifier", current_p_m25=12))
    metric = card._readings["current_p_m25"]
    assert metric.note_text == "Good"
    assert metric.unit_text == "µg/m³"


def test_readings_without_a_band_have_no_note(qapp: Any) -> None:
    card = DeviceCard(make_device("environmentSensor", current_c_o2=612))
    assert card._readings["current_c_o2"].note_text == ""


# --- hidden devices (t-89) ---------------------------------------------------


def _hidden(device: Any, hidden: bool = True) -> Any:
    """Mark a stub device the way the hub does (`is_hidden` on the device)."""
    device.is_hidden = hidden
    return device


def _card_ids(win: Any) -> set[str]:
    return {c.device.id for _, grid in win._room_sections for c in grid.cards()}


def test_hidden_device_gets_no_card_and_is_not_counted(window: Any) -> None:
    visible = make_device("light", "l1", "Lamp", is_on=False)
    hidden = _hidden(make_device("light", "l2", "Secret", is_on=False))
    window._on_refreshed([visible, hidden], [])
    assert _card_ids(window) == {"l1"}
    assert window.status_label.text() == ("Found 1 devices in 1 rooms and 0 scenes")


def test_hidden_energy_device_gets_no_energy_card(window: Any) -> None:
    meter = _hidden(
        make_device("electricalSensor", "e1", "Meter", current_active_power=5.0)
    )
    window._on_refreshed([meter], [])
    assert [c.device.id for c in window.energy_view.cards()] == []


def test_device_that_becomes_visible_again_gets_a_card(window: Any) -> None:
    window._on_refreshed([_hidden(make_device("light", "l1", "Lamp", is_on=False))], [])
    assert _card_ids(window) == set()
    window._on_refreshed([make_device("light", "l1", "Lamp", is_on=False)], [])
    assert _card_ids(window) == {"l1"}
    assert window.status_label.text() == ("Found 1 devices in 1 rooms and 0 scenes")
