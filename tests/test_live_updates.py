"""Live updates: events prompt refreshes, polling is the fallback (t-16)."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from conftest import StubHub, StubScene, make_device

import dashboard
import workers

Wait = Callable[..., None]

EVENT = json.dumps({"type": "deviceStateChanged", "data": {"id": "l1"}})


@pytest.fixture
def hub(monkeypatch: pytest.MonkeyPatch) -> StubHub:
    stub = StubHub(
        devices=[make_device("light", "l1", "Lamp", is_on=True, light_level=40)],
        scenes=[StubScene("s1", "Evening")],
    )
    monkeypatch.setattr(workers, "Hub", lambda token, ip_address: stub)
    monkeypatch.setattr(dashboard, "EVENT_COALESCE_MS", 60)
    return stub


@pytest.fixture
def connected(window: Any, hub: StubHub, wait_until: Wait) -> Any:
    window.connection_block.ip_input.setText("10.0.0.2")
    window.connection_block.token_input.setText("tok")
    window.connect_to_hub()
    wait_until(lambda: window.hub is not None and window._refresh_worker is None)
    wait_until(hub.listener_started.is_set)
    return window


def _count_refreshes(win: Any, monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Record every fetch the window actually starts."""
    started: list[int] = []
    original = win._start_refresh

    def counting(*args: Any, **kwargs: Any) -> None:
        if win._refresh_worker is None:
            started.append(1)
        original(*args, **kwargs)

    monkeypatch.setattr(win, "_start_refresh", counting)
    return started


def _fire(hub: StubHub, message: str = EVENT) -> None:
    hub.listener["on_message"](None, message)


def _open(win: Any, hub: StubHub, wait_until: Wait) -> None:
    hub.listener["on_open"](None)
    wait_until(lambda: win._live)


def test_listener_starts_after_connect_and_polling_stays_until_it_opens(
    connected: Any,
) -> None:
    assert connected._event_worker is not None
    assert connected._live is False
    assert "every 30 s" in connected.update_label.text()


def test_opening_the_socket_goes_live_without_a_second_fetch(
    connected: Any, hub: StubHub, wait_until: Wait, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _count_refreshes(connected, monkeypatch)
    _open(connected, hub, wait_until)
    assert connected.update_label.text().startswith("Live · updated")
    assert connected.refresh_timer.interval() == dashboard.LIVE_POLL_INTERVAL_S * 1000
    assert started == []  # the connect fetch already covers the first open


def test_an_event_refreshes_once_after_the_coalesce_window(
    connected: Any, hub: StubHub, wait_until: Wait, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open(connected, hub, wait_until)
    started = _count_refreshes(connected, monkeypatch)
    hub.devices = [make_device("light", "l1", "Lamp", is_on=False, light_level=40)]
    _fire(hub)
    wait_until(connected._event_timer.isActive)
    assert started == []  # not at once
    wait_until(lambda: len(started) == 1)
    wait_until(lambda: connected._refresh_worker is None)
    card = connected._device_cards["l1"]
    assert card.switch.isChecked() is False  # the change showed without Refresh


def test_a_burst_of_events_is_one_refresh(
    connected: Any,
    hub: StubHub,
    wait_until: Wait,
    pump: Callable[[int], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _open(connected, hub, wait_until)
    started = _count_refreshes(connected, monkeypatch)
    for _ in range(10):
        _fire(hub)
    wait_until(lambda: len(started) == 1)
    wait_until(lambda: connected._refresh_worker is None)
    pump(150)
    assert started == [1]


def test_unreadable_messages_cause_no_refresh(
    connected: Any,
    hub: StubHub,
    pump: Callable[[int], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = _count_refreshes(connected, monkeypatch)
    _fire(hub, "not json")
    pump(200)
    assert started == []


def test_event_during_a_fetch_queues_one_more(
    connected: Any, wait_until: Wait, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _count_refreshes(connected, monkeypatch)
    connected.refresh_devices()  # a fetch is now in flight
    assert connected._refresh_worker is not None
    connected._event_timer.timeout.emit()  # the coalesce window ended meanwhile
    assert connected._refresh_pending is True
    wait_until(lambda: len(started) == 2)
    wait_until(lambda: connected._refresh_worker is None)


def test_no_refresh_for_events_while_minimised(
    connected: Any,
    hub: StubHub,
    pump: Callable[[int], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = _count_refreshes(connected, monkeypatch)
    monkeypatch.setattr(connected, "isMinimized", lambda: True)
    _fire(hub)
    pump(200)
    assert started == []
    assert not connected._event_timer.isActive()


def test_losing_the_socket_returns_to_polling(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    _open(connected, hub, wait_until)
    hub.listener["on_close"](None, 1006, "gone")
    wait_until(lambda: not connected._live)
    assert connected.refresh_timer.interval() == dashboard.POLL_INTERVAL_S * 1000
    assert "every 30 s" in connected.update_label.text()


def test_reopening_after_a_loss_refetches(
    connected: Any, hub: StubHub, wait_until: Wait, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open(connected, hub, wait_until)
    hub.listener["on_close"](None, 1006, "gone")
    wait_until(lambda: not connected._live)
    started = _count_refreshes(connected, monkeypatch)
    _open(connected, hub, wait_until)
    wait_until(lambda: len(started) == 1)  # events in the gap were lost


def test_reconnecting_to_a_hub_replaces_the_listener(
    connected: Any, hub: StubHub, wait_until: Wait, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = connected._event_worker
    second = StubHub(devices=hub.devices, scenes=hub.scenes)
    monkeypatch.setattr(workers, "Hub", lambda token, ip_address: second)
    connected.connect_to_hub()
    wait_until(second.listener_started.is_set)
    assert connected._event_worker is not old
    assert old is not None and old.stop_requested()
    assert hub.listener_stop.is_set()
    wait_until(lambda: not old.isRunning())
    connected._stop_events()  # the second listener blocks until stopped


def test_signals_of_a_stopped_listener_are_ignored(connected: Any, qapp: Any) -> None:
    old = connected._event_worker
    connected._stop_events()
    # A signal the old thread had already queued still arrives later.
    old.opened.emit()
    qapp.processEvents()
    assert connected._live is False


def test_a_failed_connect_stops_the_listener(
    connected: Any, wait_until: Wait, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = connected._event_worker

    def broken(token: str, ip_address: str) -> Any:
        raise RuntimeError("no route")

    monkeypatch.setattr(workers, "Hub", broken)
    connected.connect_to_hub()
    wait_until(lambda: connected._connect_worker is None)
    assert connected._event_worker is None
    assert old is not None and old.stop_requested()
    wait_until(lambda: not old.isRunning())


def test_closing_stops_the_listener_and_waits_for_it(
    connected: Any, wait_until: Wait
) -> None:
    worker = connected._event_worker
    assert worker is not None and worker.isRunning()
    connected.close()  # stops the listener; the thread ends on its own
    wait_until(lambda: not worker.isRunning())
    assert worker.stop_requested()
    assert connected._event_worker is None
