"""Sensor, purifier and remote cards show real readings, not invented state."""

from enum import Enum
from typing import Any

import pytest
from conftest import make_device

from widgets.card import DeviceCard, device_sort_key


def readings(card: DeviceCard) -> dict[str, tuple[str, str]]:
    """Caption -> (value text, unit text) of every metric on the card."""
    return {
        m.caption_text: (m.value_text, m.unit_text) for m in card._readings.values()
    }


def test_environment_sensor_shows_only_reported_values() -> None:
    card = DeviceCard(
        make_device(
            "environmentSensor",
            current_temperature=21.5,
            current_r_h=40,
            current_p_m25=7,
            current_c_o2=None,
            voc_index=None,
            battery_percentage=80,
        )
    )
    assert readings(card) == {
        "Temperature": ("21.5", "°C"),
        "Humidity": ("40", "%"),
        "PM2.5": ("7", ""),
    }
    assert card.status_chip.text() == ""
    assert card.status_chip.isHidden()
    assert card.footer_label.text() == "Battery 80%"


def test_environment_sensor_with_co2_and_voc() -> None:
    card = DeviceCard(make_device("environmentSensor", current_c_o2=612, voc_index=120))
    assert readings(card)["CO₂"] == ("612", "ppm")
    assert readings(card)["VOC index"] == ("120", "")


def test_environment_refresh_updates_the_same_metrics_in_place() -> None:
    card = DeviceCard(
        make_device("environmentSensor", current_temperature=20.0, current_r_h=40)
    )
    metric = card._readings["current_temperature"]
    card.update_from_device(
        make_device("environmentSensor", current_temperature=22.5, current_r_h=41)
    )
    assert card._readings["current_temperature"] is metric
    assert metric.value_text == "22.5"
    assert readings(card)["Humidity"][0] == "41"


def test_a_reading_that_appears_later_is_added() -> None:
    card = DeviceCard(make_device("environmentSensor", current_temperature=20.0))
    assert set(readings(card)) == {"Temperature"}
    card.update_from_device(
        make_device("environmentSensor", current_temperature=20.0, current_r_h=33)
    )
    assert set(readings(card)) == {"Temperature", "Humidity"}


@pytest.mark.parametrize("dtype", ["motionSensor", "occupancySensor"])
def test_motion_and_occupancy_chip(dtype: str) -> None:
    assert DeviceCard(make_device(dtype, is_detected=True)).status_chip.text() == (
        "Motion"
    )
    assert DeviceCard(make_device(dtype, is_detected=False)).status_chip.text() == (
        "Clear"
    )


def test_motion_refresh_changes_the_chip_on_the_same_card() -> None:
    card = DeviceCard(make_device("motionSensor", is_detected=False))
    card.update_from_device(make_device("motionSensor", is_detected=True))
    assert card.status_chip.text() == "Motion"


@pytest.mark.parametrize("is_open,word", [(True, "Open"), (False, "Closed")])
def test_open_close_chip(is_open: bool, word: str) -> None:
    card = DeviceCard(make_device("openCloseSensor", is_open=is_open))
    assert card.status_chip.text() == word


def test_water_sensor_leak_is_danger() -> None:
    leak = DeviceCard(make_device("waterSensor", water_leak_detected=True))
    assert leak.status_chip.text() == "Leak"
    assert leak.status_chip.variant == "danger"
    dry = DeviceCard(make_device("waterSensor", water_leak_detected=False))
    assert dry.status_chip.text() == "Dry"
    assert dry.status_chip.variant != "danger"


def test_light_sensor_shows_illuminance() -> None:
    card = DeviceCard(make_device("lightSensor", illuminance=320))
    assert readings(card) == {"Illuminance": ("320", "")}
    assert card.status_chip.isHidden()


class Fan(Enum):
    AUTO = "auto"


def test_air_purifier_shows_pm25_and_fan_mode_word() -> None:
    card = DeviceCard(make_device("airPurifier", current_p_m25=12, fan_mode=Fan.AUTO))
    assert readings(card) == {"PM2.5": ("12", ""), "Fan mode": ("Auto", "")}
    assert card.status_chip.isHidden()
    card.update_from_device(
        make_device("airPurifier", current_p_m25=3, fan_mode=Fan.AUTO)
    )
    assert readings(card)["PM2.5"][0] == "3"


def test_controller_has_no_controls_chip_or_invented_state() -> None:
    card = DeviceCard(make_device("lightController", battery_percentage=64, is_on=None))
    assert card.control_zone.count() == 0
    assert card.status_chip.text() == ""
    assert card.status_chip.text() != "Ready"
    assert card.footer_label.text() == "Battery 64%"


def test_low_battery_overrides_a_sensor_chip() -> None:
    card = DeviceCard(
        make_device("openCloseSensor", is_open=True, battery_percentage=10)
    )
    assert card.status_chip.text() == "Low battery"
    assert not card.status_chip.isHidden()


def test_offline_sensor_shows_offline_chip() -> None:
    card = DeviceCard(make_device("motionSensor", reachable=False, is_detected=True))
    assert card.status_chip.text() == "Offline"
    assert not card.status_chip.isHidden()


@pytest.mark.parametrize(
    "dtype",
    [
        "environmentSensor",
        "motionSensor",
        "occupancySensor",
        "openCloseSensor",
        "waterSensor",
        "lightSensor",
        "airPurifier",
        "lightController",
    ],
)
def test_no_type_shows_a_ready_chip(dtype: str) -> None:
    attrs: dict[str, Any] = {"is_open": True, "water_leak_detected": False}
    card = DeviceCard(make_device(dtype, **attrs))
    assert card.status_chip.text() != "Ready"


def test_sort_order_follows_the_design() -> None:
    order = [
        "light",
        "outlet",
        "blinds",
        "airPurifier",
        "environmentSensor",
        "electricalSensor",
        "lightSensor",
        "waterSensor",
        "openCloseSensor",
        "occupancySensor",
        "motionSensor",
        "shortcutController",
    ]
    devices = [make_device(t, name="x") for t in reversed(order)]
    result = [d.device_type for d in sorted(devices, key=device_sort_key)]
    assert result == order
