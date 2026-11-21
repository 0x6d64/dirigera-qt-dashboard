"""Discovery from the user's side: one scan at a time, cancel is cooperative
(req-10, req-11). The network is never touched; the scan is a stub that waits
for the stop flag."""

import threading
from collections.abc import Callable
from typing import Any

import pytest

import dashboard


@pytest.fixture
def stub_scan(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace the network scan with one that runs until told to stop."""
    state: dict[str, Any] = {"calls": 0, "release": threading.Event(), "hubs": []}

    def fake(
        max_workers: int = 50,
        timeout_per_ip: float = 1.0,
        should_stop: Callable[[], bool] | None = None,
    ) -> list[Any]:
        state["calls"] += 1
        assert should_stop is not None
        # Bounded wait: never hang the suite.
        for _ in range(500):
            if should_stop() or state["release"].is_set():
                break
            threading.Event().wait(0.01)
        hubs: list[Any] = state["hubs"]
        return hubs

    monkeypatch.setattr(dashboard, "discover_dirigera_hubs", fake)
    return state


def test_second_discover_click_starts_no_second_scan(
    window: Any, stub_scan: dict[str, Any], wait_until: Callable[..., None]
) -> None:
    window.discover_hubs()
    first = window.discovery_thread
    assert not window.connection_block.discover_button.isEnabled()
    window.discover_hubs()
    assert window.discovery_thread is first
    wait_until(lambda: stub_scan["calls"] == 1)
    window.on_discovery_canceled()
    wait_until(lambda: not first.isRunning())
    assert stub_scan["calls"] == 1


def test_cancel_returns_at_once_and_drops_the_result(
    window: Any,
    stub_scan: dict[str, Any],
    dialogs: list[tuple[str, str]],
    wait_until: Callable[..., None],
) -> None:
    stub_scan["hubs"] = [("192.168.1.9", None)]
    window.discover_hubs()
    thread = window.discovery_thread
    wait_until(lambda: stub_scan["calls"] == 1)

    window.on_discovery_canceled()  # must not block
    wait_until(lambda: not thread.isRunning())
    wait_until(lambda: window.connection_block.discover_button.isEnabled())

    assert dialogs == []
    assert window.connection_block.ip_input.text() == ""
    assert window.connection_block.message_label.isHidden()


def test_finished_scan_fills_in_the_hub(
    window: Any,
    stub_scan: dict[str, Any],
    dialogs: list[tuple[str, str]],
    wait_until: Callable[..., None],
) -> None:
    stub_scan["hubs"] = [("192.168.1.9", None)]
    stub_scan["release"].set()
    window.discover_hubs()
    wait_until(lambda: window.connection_block.discover_button.isEnabled())
    assert window.connection_block.ip_input.text() == "192.168.1.9"
    assert dialogs == []
    assert "192.168.1.9" in window.connection_block.message_label.text()


def test_scan_without_hubs_hints_at_manual_entry_inline(
    window: Any,
    stub_scan: dict[str, Any],
    dialogs: list[tuple[str, str]],
    wait_until: Callable[..., None],
) -> None:
    stub_scan["hubs"] = []
    stub_scan["release"].set()
    window.discover_hubs()
    wait_until(lambda: window.connection_block.discover_button.isEnabled())
    assert dialogs == []
    assert "manually" in window.connection_block.message_label.text()


def test_failing_scan_says_so_instead_of_no_hubs(
    window: Any,
    monkeypatch: pytest.MonkeyPatch,
    dialogs: list[tuple[str, str]],
    wait_until: Callable[..., None],
) -> None:
    def boom(**kwargs: Any) -> list[Any]:
        raise RuntimeError("no network adapter")

    monkeypatch.setattr(dashboard, "discover_dirigera_hubs", boom)
    window.discover_hubs()
    wait_until(lambda: window.connection_block.discover_button.isEnabled())
    text = window.connection_block.message_label.text()
    assert text.startswith("Discovery failed:")
    assert "no network adapter" in text
    assert "No hubs found" not in text
    assert dialogs == []


def test_close_stops_a_running_scan_and_still_closes(
    window: Any, stub_scan: dict[str, Any], wait_until: Callable[..., None]
) -> None:
    window.discover_hubs()
    thread = window.discovery_thread
    wait_until(lambda: stub_scan["calls"] == 1)
    window.close()
    assert window._close_pending and window.isHidden()
    wait_until(lambda: not thread.isRunning())
    wait_until(lambda: not window._running_workers())
