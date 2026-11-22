"""A pending close starts no new refresh, and ends when the last worker does (t-100)."""

import threading
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import StubHub, StubScene, make_device
from PyQt6.QtWidgets import QApplication

import workers
from widgets.energy import EnergyCard

Wait = Callable[..., None]


@pytest.fixture
def hub(monkeypatch: pytest.MonkeyPatch) -> StubHub:
    stub = StubHub(
        devices=[make_device("light", "l1", "Lamp", is_on=True, light_level=40)],
        scenes=[StubScene("s1", "Evening")],
    )
    monkeypatch.setattr(workers, "Hub", lambda token, ip_address: stub)
    return stub


@pytest.fixture
def connected(window: Any, hub: StubHub, wait_until: Wait) -> Any:
    window.connection_block.ip_input.setText("10.0.0.2")
    window.connection_block.token_input.setText("tok")
    window.connect_to_hub()
    wait_until(lambda: window.hub is not None and window._refresh_worker is None)
    return window


@pytest.fixture
def quits(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    seen: list[bool] = []
    monkeypatch.setattr(QApplication, "quit", staticmethod(lambda: seen.append(True)))
    return seen


def test_close_with_a_refresh_queued_starts_no_second_fetch(
    connected: Any,
    hub: StubHub,
    monkeypatch: pytest.MonkeyPatch,
    wait_until: Wait,
    pump: Callable[[int], None],
    quits: list[bool],
) -> None:
    gate = threading.Event()
    fetches: list[int] = []
    original = hub.get_all_devices

    def gated_fetch() -> list[Any]:
        fetches.append(1)
        gate.wait(5)
        return original()

    monkeypatch.setattr(hub, "get_all_devices", gated_fetch)
    connected.refresh_devices()
    connected._request_background_refresh()
    assert connected._refresh_pending
    connected.close()
    assert connected._close_pending
    gate.set()
    wait_until(lambda: bool(quits))
    pump(50)
    assert fetches == [1]
    assert connected._refresh_worker is None


def test_close_right_after_a_reset_starts_no_refresh(
    connected: Any,
    hub: StubHub,
    wait_until: Wait,
    pump: Callable[[int], None],
    quits: list[bool],
) -> None:
    gate = threading.Event()

    class Client:
        def patch(self, route: str, data: list[dict[str, Any]]) -> str:
            gate.wait(5)
            return ""

    device = make_device(
        "outlet", "o9", "Kettle", is_on=True, total_energy_consumed=1.0
    )
    device.capabilities = SimpleNamespace(can_receive=["energyConsumedAtLastReset"])
    device.dirigera_client = Client()
    card = EnergyCard(device)
    fetches = len(hub.calls)
    connected.reset_energy(card)
    connected.close()
    assert connected._close_pending
    gate.set()
    wait_until(lambda: bool(quits))
    pump(50)
    assert len(hub.calls) == fetches
    assert connected._refresh_worker is None


def test_timers_started_while_closing_do_nothing(
    connected: Any, hub: StubHub, pump: Callable[[int], None], quits: list[bool]
) -> None:
    lamp = make_device("light", "l2", "Lamp", is_on=True, light_level=40)
    card = connected.create_device_widget(lamp)
    release = threading.Event()
    worker = connected.run_device_command(card, lambda: release.wait(5), "wait")
    connected.close()
    connected._schedule_adaptive_refresh()
    connected._on_scene_triggered(connected.scenes_grid.cards()[0].scene)
    connected._on_hub_event(None)
    assert not connected._adaptive_refresh_timer.isActive()
    assert not connected._scene_refresh_timer.isActive()
    assert not connected._event_timer.isActive()
    release.set()
    worker.wait(5000)
