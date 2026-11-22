"""Energy counter reset: capability, inline two-step confirm, one PATCH (req-18).

The hub is a stub: `patch` records its route, data and thread, so the tests
show the PATCH runs off the GUI thread without touching a real hub.
"""

import threading
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from conftest import make_device
from PyQt6.QtWidgets import QApplication

from widgets.energy import EnergyCard

RESET = "energyConsumedAtLastReset"
Wait = Callable[..., None]


class StubEnergyClient:
    """Stands in for the `dirigera` hub client; `fail` simulates a refusal."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, list[dict[str, Any]], threading.Thread]] = []

    def patch(self, route: str, data: list[dict[str, Any]]) -> str:
        self.calls.append((route, data, threading.current_thread()))
        if self.fail:
            raise RuntimeError("hub said no")
        return ""


def _outlet(client: StubEnergyClient, capable: bool = True) -> Any:
    device = make_device(
        "outlet",
        "o1",
        name="Kettle",
        is_on=True,
        current_active_power=5.0,
        total_energy_consumed=3.2,
    )
    device.capabilities = SimpleNamespace(can_receive=[RESET] if capable else [])
    device.dirigera_client = client
    return device


def test_reset_is_offered_only_with_the_capability(qapp: QApplication) -> None:
    capable = EnergyCard(_outlet(StubEnergyClient()))
    plain = EnergyCard(_outlet(StubEnergyClient(), capable=False))
    assert capable.can_reset
    assert not capable.reset_zone.isHidden()
    assert not plain.can_reset
    assert plain.reset_zone.isHidden()


def test_first_click_asks_and_sends_nothing(qapp: QApplication) -> None:
    client = StubEnergyClient()
    sent: list[EnergyCard] = []
    card = EnergyCard(_outlet(client), on_reset=sent.append)
    card.reset_button.click()
    assert not card.confirm_button.isHidden()
    assert not card.cancel_button.isHidden()
    assert card.reset_button.isHidden()
    assert client.calls == []
    assert sent == []


def test_cancel_returns_to_reset_and_sends_nothing(qapp: QApplication) -> None:
    client = StubEnergyClient()
    sent: list[EnergyCard] = []
    card = EnergyCard(_outlet(client), on_reset=sent.append)
    card.reset_button.click()
    card.cancel_button.click()
    assert not card.reset_button.isHidden()
    assert card.confirm_button.isHidden()
    assert client.calls == []
    assert sent == []


def test_timeout_returns_to_reset_and_sends_nothing(
    qapp: QApplication, wait_until: Wait
) -> None:
    client = StubEnergyClient()
    sent: list[EnergyCard] = []
    card = EnergyCard(_outlet(client), on_reset=sent.append)
    card._confirm_timer.setInterval(30)
    card.reset_button.click()
    wait_until(lambda: not card.reset_button.isHidden())
    assert client.calls == []
    assert sent == []


def test_confirm_hands_the_reset_to_the_callback_once(qapp: QApplication) -> None:
    sent: list[EnergyCard] = []
    card = EnergyCard(_outlet(StubEnergyClient()), on_reset=sent.append)
    card.reset_button.click()
    card.confirm_button.click()
    assert sent == [card]
    assert not card.reset_button.isHidden()
    assert card.confirm_button.isHidden()


def test_confirmed_reset_sends_one_patch_off_the_gui_thread(
    window: Any,
    wait_until: Wait,
    dialogs: list[tuple[str, str]],
    monkeypatch: Any,
) -> None:
    client = StubEnergyClient()
    refreshes: list[bool] = []
    monkeypatch.setattr(
        window, "_request_background_refresh", lambda: refreshes.append(True)
    )
    window._on_refreshed([_outlet(client)], [])
    (card,) = window.energy_view.cards()

    card.reset_button.click()
    assert client.calls == []
    card.confirm_button.click()

    wait_until(lambda: refreshes == [True])
    assert len(client.calls) == 1
    route, data, thread = client.calls[0]
    assert route == "/devices/o1"
    assert data == [{"attributes": {RESET: 0}}]
    assert thread is not threading.main_thread()
    assert dialogs == []


def test_failed_reset_shows_the_error_and_does_not_refresh(
    window: Any,
    wait_until: Wait,
    dialogs: list[tuple[str, str]],
    monkeypatch: Any,
) -> None:
    client = StubEnergyClient(fail=True)
    refreshes: list[bool] = []
    monkeypatch.setattr(
        window, "_request_background_refresh", lambda: refreshes.append(True)
    )
    window._on_refreshed([_outlet(client)], [])
    (card,) = window.energy_view.cards()

    card.reset_button.click()
    card.confirm_button.click()

    wait_until(lambda: card.footer_label.text() == "Couldn't reset energy: hub said no")
    assert refreshes == []
    assert dialogs == []


def test_reset_is_blocked_while_a_command_runs(qapp: QApplication) -> None:
    card = EnergyCard(_outlet(StubEnergyClient()))
    card.reset_button.click()
    card.set_pending(True)
    assert not card.confirm_button.isEnabled()
    assert card.confirm_button.isHidden()  # the open confirm step is withdrawn
    assert not card.reset_button.isEnabled()
    card.sync_from_device()  # a resync does not end the command
    assert not card.reset_button.isEnabled()
    card.set_pending(False)
    assert card.reset_button.isEnabled()


def test_reset_is_blocked_while_offline(qapp: QApplication) -> None:
    device = _outlet(StubEnergyClient())
    device.is_reachable = False
    card = EnergyCard(device)
    assert not card.reset_button.isEnabled()
    device.is_reachable = True
    card.sync_from_device()
    assert card.reset_button.isEnabled()
