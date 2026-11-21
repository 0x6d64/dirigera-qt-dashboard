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


def test_environment_sensor_shows_the_pm25_band_word() -> None:
    card = DeviceCard(make_device("environmentSensor", current_p_m25=7))
    metric = card._readings["current_p_m25"]
    assert metric.unit_text == "µg/m³"
    assert metric.note_text == "Good"
    assert metric.note_colour == theme.OK


def test_pm25_band_follows_each_refresh() -> None:
    card = DeviceCard(make_device("environmentSensor", current_p_m25=7))
    metric = card._readings["current_p_m25"]
    card.update_from_device(make_device("environmentSensor", current_p_m25=20))
    assert metric.note_text == "Moderate"
    assert metric.note_colour == theme.WARN
    card.update_from_device(make_device("environmentSensor", current_p_m25=50))
    assert metric.note_text == "Poor"
    assert metric.note_colour == theme.DANGER


def test_purifier_shows_the_pm25_band_word() -> None:
    card = DeviceCard(make_device("airPurifier", current_p_m25=12))
    metric = card._readings["current_p_m25"]
    assert metric.note_text == "Good"
    assert metric.unit_text == "µg/m³"


def test_readings_without_a_band_have_no_note() -> None:
    card = DeviceCard(make_device("environmentSensor", current_c_o2=612))
    assert card._readings["current_c_o2"].note_text == ""
