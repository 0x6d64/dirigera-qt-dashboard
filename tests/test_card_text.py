"""Card text: name elision, offline footer, chips, type captions."""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from conftest import make_device

from widgets.card import DeviceCard, device_sort_key
from widgets.text import relative_time, type_label


def test_long_name_is_elided_and_keeps_the_card_width(qapp: Any) -> None:
    name = "Living room ceiling lamp " * 8
    card = DeviceCard(make_device("light", name=name, is_on=True, light_level=50))
    card.resize(300, 200)
    card.show()
    qapp.processEvents()
    assert card.width() == 300
    assert card.name_label.text().endswith("…")
    assert len(card.name_label.text()) < len(name)
    assert card.name_label.toolTip() == name
    assert card.full_name == name
    card.hide()


def test_short_name_is_not_elided(qapp: Any) -> None:
    card = DeviceCard(make_device("light", name="Lamp", is_on=True, light_level=50))
    card.resize(300, 200)
    qapp.processEvents()
    assert card.name_label.text() == "Lamp"


def test_offline_footer_says_when_the_device_was_last_seen() -> None:
    card = DeviceCard(make_device("light", reachable=False, is_on=True))
    card.device.last_seen = datetime.now(timezone.utc) - timedelta(minutes=5)
    card.set_offline(True)
    assert card.footer_label.text() == "Last seen 5 min ago"


def test_offline_footer_without_last_seen_says_unreachable() -> None:
    card = DeviceCard(make_device("light", reachable=False, is_on=True))
    assert card.footer_label.text() == "Device unreachable"


@pytest.mark.parametrize(
    "level,chip", [(0, "Closed"), (50, "Partly open"), (100, "Open")]
)
def test_blind_chip_words(level: int, chip: str) -> None:
    card = DeviceCard(make_device("blinds", blinds_current_level=level))
    assert card.status_chip.text() == chip


def test_type_caption_is_a_human_word() -> None:
    card = DeviceCard(make_device("environmentSensor"))
    assert card.type_label.text() == "Environment sensor"


def test_relative_time() -> None:
    now = datetime(2026, 11, 21, 12, 0)
    assert relative_time(now - timedelta(seconds=30), now) == "just now"
    assert relative_time(now - timedelta(minutes=5), now) == "5 min ago"
    assert relative_time(now - timedelta(hours=3), now) == "3 h ago"
    assert relative_time(datetime(2026, 11, 20, 9, 0), now) == "yesterday"
    assert relative_time(datetime(2026, 11, 3, 9, 0), now) == "03 Nov"
    assert relative_time(now + timedelta(minutes=2), now) == "just now"


@pytest.mark.parametrize(
    "raw,label",
    [
        ("light", "Light"),
        ("outlet", "Plug"),
        ("airPurifier", "Air purifier"),
        ("openCloseSensor", "Door or window sensor"),
        ("electricalSensor", "Energy meter"),
        ("shortcutController", "Remote"),
        ("someNewThing", "Some new thing"),
        ("", "Device"),
    ],
)
def test_type_label(raw: str, label: str) -> None:
    assert type_label(raw) == label


def test_sort_uses_real_device_types() -> None:
    kinds = ["lightController", "motionSensor", "environmentSensor", "outlet", "light"]
    devices = [make_device(k, k, name=k) for k in kinds]
    ordered = [d.device_type for d in sorted(devices, key=device_sort_key)]
    assert ordered == [
        "light",
        "outlet",
        "environmentSensor",
        "motionSensor",
        "lightController",
    ]


def test_metering_outlet_shows_the_energy_footer() -> None:
    card = DeviceCard(
        make_device(
            "outlet",
            is_on=True,
            current_active_power=12.0,
            current_voltage=230.0,
            current_amps=0.05,
            total_energy_consumed=1.5,
        )
    )
    assert card.footer_label.text() == "12 W · 230 V · 0.05 A · 1.50 kWh"


def test_plain_outlet_has_no_energy_footer() -> None:
    card = DeviceCard(make_device("outlet", is_on=True, current_active_power=None))
    assert card.footer_label.text() == ""


def test_metering_outlet_footer_follows_a_refresh() -> None:
    card = DeviceCard(make_device("outlet", is_on=True, current_active_power=5.0))
    card.update_from_device(
        make_device("outlet", is_on=True, current_active_power=40.0)
    )
    assert card.footer_label.text() == "40 W"
