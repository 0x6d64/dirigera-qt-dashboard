"""Card text: name elision, offline footer, chips, type captions."""

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest
from conftest import make_device

from widgets.card import DeviceCard, device_sort_key
from widgets.text import (
    energy_totals,
    format_cost,
    relative_time,
    totals_text,
    type_label,
    usage_kwh,
    usage_text,
)


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


def _attrs(**kw: Any) -> Any:
    return make_device("outlet", **kw).attributes


def test_usage_is_the_total_since_the_last_reset() -> None:
    attrs = _attrs(total_energy_consumed=18.4, energy_consumed_at_last_reset=17.1)
    assert usage_kwh(attrs) == pytest.approx(1.3)


def test_usage_without_a_reset_value_is_the_total() -> None:
    attrs = _attrs(total_energy_consumed=18.4)
    assert usage_kwh(attrs) == 18.4


def test_usage_is_none_without_a_total() -> None:
    assert usage_kwh(_attrs(energy_consumed_at_last_reset=1.0)) is None


def test_cost_is_usage_times_price_with_two_decimals() -> None:
    assert format_cost(1.3, 1.54, "RON") == "2.00 RON"
    assert format_cost(18.4, 1.54, "RON") == "28.34 RON"


def test_usage_text_without_a_reset_time() -> None:
    attrs = _attrs(total_energy_consumed=18.4)
    text = usage_text(attrs, 1.54, "RON", date(2026, 11, 21))
    assert text == "Usage 18.40 kWh · 28.34 RON"


def test_usage_text_since_a_reset_this_year() -> None:
    attrs = _attrs(
        total_energy_consumed=18.4,
        energy_consumed_at_last_reset=17.1,
        time_of_last_energy_reset=datetime(2026, 11, 21, 12, 0),
    )
    text = usage_text(attrs, 1.54, "RON", date(2026, 11, 25))
    assert text == "Since 21 Nov: 1.30 kWh · 2.00 RON"


def test_usage_text_adds_the_year_of_an_older_reset() -> None:
    attrs = _attrs(
        total_energy_consumed=18.4,
        energy_consumed_at_last_reset=17.1,
        time_of_last_energy_reset=datetime(2025, 3, 5, 12, 0),
    )
    text = usage_text(attrs, 1.54, "RON", date(2026, 11, 21))
    assert text == "Since 05 Mar 2025: 1.30 kWh · 2.00 RON"


def test_zero_reset_value_still_counts_as_a_reset() -> None:
    attrs = _attrs(
        total_energy_consumed=2.0,
        energy_consumed_at_last_reset=0.0,
        time_of_last_energy_reset=datetime(2026, 11, 21, 12, 0),
    )
    text = usage_text(attrs, 1.0, "EUR", date(2026, 11, 21))
    assert text == "Since 21 Nov: 2.00 kWh · 2.00 EUR"


def test_usage_text_is_none_without_energy_data() -> None:
    assert usage_text(_attrs(), 1.54, "RON", date(2026, 11, 21)) is None


def test_totals_sum_only_what_each_device_reports() -> None:
    devices = [
        make_device("outlet", "a", power=None, total_energy_consumed=None),
        make_device(
            "outlet",
            "b",
            current_active_power=10.0,
            total_energy_consumed=2.0,
            energy_consumed_at_last_reset=1.0,
        ),
        make_device("outlet", "c", current_active_power=5.0, total_energy_consumed=3.0),
    ]
    watts, kwh = energy_totals(devices)
    assert watts == 15.0
    assert kwh == pytest.approx(4.0)


def test_totals_are_none_when_nothing_reports() -> None:
    assert energy_totals([make_device("outlet", "a")]) == (None, None)
    assert energy_totals([]) == (None, None)


def test_totals_text_leaves_out_missing_parts() -> None:
    assert totals_text(45.0, 1.3, 1.54, "RON") == "45 W now · 1.30 kWh · 2.00 RON"
    assert totals_text(45.0, None, 1.54, "RON") == "45 W now"
    assert totals_text(None, 0.0, 1.54, "RON") == "0.00 kWh · 0.00 RON"
    assert totals_text(None, None, 1.54, "RON") is None
