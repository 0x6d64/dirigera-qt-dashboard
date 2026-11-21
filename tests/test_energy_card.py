"""EnergyCard shares the device card's pending, error and name handling."""

from collections.abc import Callable
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
