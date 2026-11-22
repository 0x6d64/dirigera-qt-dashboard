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


def test_second_command_on_a_pending_card_is_ignored(
    window: Any, wait_until: Any
) -> None:
    import threading

    card = window.create_device_widget(make_device("light", "l1", "Lamp", is_on=True))
    release = threading.Event()
    sent: list[str] = []
    first = window.run_device_command(card, lambda: release.wait(5), "first")
    second = window.run_device_command(card, lambda: sent.append("second"), "second")
    assert first is not None
    assert second is None
    assert card.footer_label.text() == "Sending…"
    release.set()
    wait_until(lambda: not card.is_pending)
    first.wait(5000)
    assert sent == []
    # Once the card is free again a new command runs.
    third = window.run_device_command(card, lambda: sent.append("third"), "third")
    assert third is not None
    third.wait(5000)
    wait_until(lambda: not card.is_pending)
    assert sent == ["third"]


def test_ignored_slider_command_snaps_the_slider_back(window: Any) -> None:
    card = window.create_device_widget(
        make_device("light", "l1", "Lamp", is_on=True, light_level=40)
    )
    card.set_pending(True)
    card.brightness_slider.set_value(90)  # the user's value, not on the device
    window.set_light_brightness(card, 90)
    assert card.brightness_slider.value() == 40
    card.set_pending(False)


def test_double_reset_sends_one_patch(window: Any, wait_until: Any) -> None:
    from test_energy_reset import StubEnergyClient, _outlet

    client = StubEnergyClient()
    window._on_refreshed([_outlet(client)], [])
    (card,) = window.energy_view.cards()
    window.reset_energy(card)
    window.reset_energy(card)
    wait_until(lambda: not card.is_pending)
    assert len(client.calls) == 1
