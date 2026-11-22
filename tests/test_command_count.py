"""A card counts its running commands; "Sending…" lasts until the last ends (t-97)."""

from typing import Any

from conftest import make_device

from widgets.card import DeviceCard
from widgets.energy import EnergyCard


def _lamp() -> DeviceCard:
    return DeviceCard(
        make_device("light", "l1", "Lamp", is_on=True, light_level=40),
    )


def test_set_pending_counts_starts_and_ends(qapp: Any) -> None:
    card = _lamp()
    assert not card.is_pending
    card.set_pending(True)
    card.set_pending(True)
    card.set_pending(False)
    assert card.is_pending
    assert card.footer_label.text() == "Sending…"
    card.set_pending(False)
    assert not card.is_pending
    assert card.footer_label.text() != "Sending…"


def test_extra_end_does_not_go_below_zero(qapp: Any) -> None:
    card = _lamp()
    card.set_pending(False)
    card.set_pending(True)
    assert card.is_pending


def test_refresh_and_resync_keep_sending(qapp: Any) -> None:
    card = _lamp()
    card.set_pending(True)
    card.update_from_device(card.device)
    assert card.footer_label.text() == "Sending…"
    card.sync_from_device()
    assert card.footer_label.text() == "Sending…"
    card.set_pending(False)
    assert card.footer_label.text() != "Sending…"


def test_controls_are_disabled_while_pending(qapp: Any) -> None:
    card = _lamp()
    assert card.brightness_slider.isEnabled()
    card.set_pending(True)
    assert not card.brightness_slider.isEnabled()
    assert not card.switch.isEnabled()
    card.update_from_device(card.device)  # a refresh does not re-enable them
    assert not card.brightness_slider.isEnabled()
    card.set_pending(False)
    assert card.brightness_slider.isEnabled()


def test_offline_card_stays_disabled_after_a_command(qapp: Any) -> None:
    card = _lamp()
    card.device.is_reachable = False
    card.set_pending(True)
    card.set_pending(False)
    card.sync_from_device()
    assert not card.switch.isEnabled()


def test_energy_card_keeps_sending_through_a_refresh(qapp: Any) -> None:
    card = EnergyCard(
        make_device("outlet", "o1", "Kettle", is_on=True, current_active_power=5.0)
    )
    card.set_pending(True)
    card.update_from_device(card.device)
    assert card.footer_label.text() == "Sending…"
    assert not card.reset_button.isEnabled()
    card.set_pending(False)
    assert card.reset_button.isEnabled()
