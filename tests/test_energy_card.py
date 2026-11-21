"""EnergyCard shares the device card's pending, error and name handling."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from conftest import make_device

from widgets.energy import EnergyCard

Wait = Callable[..., None]


def _card(name: str = "Kettle", **kw: Any) -> EnergyCard:
    device = make_device(
        "outlet",
        "o1",
        name=name,
        is_on=True,
        current_active_power=5.0,
        total_energy_consumed=3.2,
        **kw,
    )
    return EnergyCard(device)


def test_pending_shows_sending_then_the_normal_footer(qapp: Any) -> None:
    card = _card()
    assert card.footer_label.text() == "Total 3.20 kWh"
    card.set_pending(True)
    assert card.footer_label.text() == "Sending…"
    card.set_pending(False)
    assert card.footer_label.text() == "Total 3.20 kWh"


def test_error_shows_in_the_footer_and_clears(qapp: Any, wait_until: Wait) -> None:
    card = _card()
    card._error_timer.setInterval(30)
    card.show_error("Couldn't reset energy: boom")
    assert card.footer_label.text() == "Couldn't reset energy: boom"
    card.sync_from_device()  # a resync keeps the error visible
    assert card.footer_label.text() == "Couldn't reset energy: boom"
    wait_until(lambda: card.footer_label.text() == "Total 3.20 kWh")


def test_sync_from_device_redraws_from_the_stored_device(qapp: Any) -> None:
    card = _card()
    card.device.attributes.total_energy_consumed = 4.5
    card.device.attributes.is_on = False
    card.sync_from_device()
    assert card.footer_label.text() == "Total 4.50 kWh"
    assert card.status_chip.text() == "Off"


def test_long_name_is_elided_with_the_full_name_in_the_tooltip(qapp: Any) -> None:
    name = "A very long outlet name " * 6
    card = _card(name=name)
    card.resize(300, 150)
    card.show()
    assert card.full_name == name
    assert card.name_label.toolTip() == name
    assert card.name_label.text().endswith("…")
    assert len(card.name_label.text()) < len(name)


def test_usage_line_shows_the_cost_since_the_reset(qapp: Any) -> None:
    reset = datetime(datetime.now().year, 11, 21, 12, 0)
    card = _card(energy_consumed_at_last_reset=2.0, time_of_last_energy_reset=reset)
    assert card.usage_label.text() == "Since 21 Nov: 1.20 kWh · 1.85 RON"
    assert card.footer_label.text() == "Total 3.20 kWh"


def test_usage_line_without_a_reset_is_the_total_usage(qapp: Any) -> None:
    card = _card()
    assert card.usage_label.text() == "Usage 3.20 kWh · 4.93 RON"


def test_usage_line_is_empty_without_energy_data(qapp: Any) -> None:
    device = make_device("outlet", "o2", name="Plug", is_on=True)
    card = EnergyCard(device)
    assert card.usage_label.text() == ""
    assert card.footer_label.text() == "No energy data"


def test_new_price_recomputes_the_cost(qapp: Any) -> None:
    card = _card()
    card.set_price(1.0, "EUR")
    assert card.usage_label.text() == "Usage 3.20 kWh · 3.20 EUR"


def test_sync_from_device_updates_the_usage_line(qapp: Any) -> None:
    card = _card()
    card.device.attributes.total_energy_consumed = 4.5
    card.sync_from_device()
    assert card.usage_label.text() == "Usage 4.50 kWh · 6.93 RON"
