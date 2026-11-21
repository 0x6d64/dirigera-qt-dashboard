"""Dashboard behaviour against a stub hub: the requirements, not the layout."""

import threading
from collections.abc import Callable
from typing import Any

import pytest
from conftest import StubHub, StubLight, StubScene, make_device
from PyQt6.QtWidgets import QApplication

import dashboard
from dashboard import widget_name

Wait = Callable[..., None]


@pytest.fixture
def hub(monkeypatch: pytest.MonkeyPatch) -> StubHub:
    stub = StubHub(
        devices=[
            make_device("light", "l1", "Lamp", is_on=True, light_level=40),
            make_device("outlet", "o1", "Heater", room=("r2", "Bedroom"), is_on=False),
        ],
        scenes=[StubScene("s1", "Evening")],
    )
    monkeypatch.setattr(dashboard, "Hub", lambda token, ip_address: stub)
    return stub


def _enter_credentials(win: Any) -> None:
    win.connection_block.ip_input.setText("10.0.0.2")
    win.connection_block.token_input.setText("tok")


def _connect(win: Any, wait_until: Wait) -> None:
    _enter_credentials(win)
    win.connect_to_hub()
    wait_until(lambda: win.hub is not None and win._refresh_worker is None)


def _card_names(win: Any) -> list[str]:
    return [widget_name(c) for _, grid in win._room_sections for c in grid.cards()]


def test_connect_verifies_with_a_hub_call_off_the_gui_thread(
    window: Any, hub: StubHub, wait_until: Wait
) -> None:
    _connect(window, wait_until)
    assert window.hub is hub
    assert hub.calls and all(t is not threading.main_thread() for t in hub.calls)


def test_failed_connect_is_not_reported_as_connected(
    window: Any, hub: StubHub, dialogs: list, wait_until: Wait
) -> None:
    hub.fail = True  # req-1: the live probe decides, not Hub()
    _enter_credentials(window)
    window.connect_to_hub()
    wait_until(lambda: window._connect_worker is None)
    assert window.hub is None
    assert any(kind == "critical" for kind, _ in dialogs)


def test_missing_credentials_do_not_start_a_worker(window: Any, dialogs: list) -> None:
    window.connect_to_hub()
    assert window._connect_worker is None
    assert dialogs


def test_refresh_builds_cards_and_scenes(
    window: Any, hub: StubHub, wait_until: Wait
) -> None:
    _connect(window, wait_until)
    assert sorted(_card_names(window)) == ["Heater", "Lamp"]
    assert [widget_name(t) for t in window.scenes_grid.cards()] == ["Evening"]


def test_failed_refresh_keeps_the_current_view(
    window: Any, hub: StubHub, dialogs: list, wait_until: Wait
) -> None:
    _connect(window, wait_until)
    before = _card_names(window)
    hub.fail = True  # req-2
    window.refresh_devices()
    wait_until(lambda: window._refresh_worker is None)
    assert _card_names(window) == before
    assert window.refresh_button.isEnabled()
    assert dialogs == []
    assert window.status_label.text().startswith("Refresh failed")


def test_filter_hides_non_matching_cards_and_empty_sections(
    window: Any, hub: StubHub, wait_until: Wait
) -> None:
    _connect(window, wait_until)
    window.filter_devices("lam")
    visible = [
        widget_name(c)
        for _, grid in window._room_sections
        for c in grid.cards()
        if not c.isHidden()
    ]
    assert visible == ["Lamp"]
    assert sum(not s.isHidden() for s, _ in window._room_sections) == 1
    window.filter_devices("")
    assert all(not s.isHidden() for s, _ in window._room_sections)


# --- device commands (req-3, req-4) -----------------------------------------


def _card(win: Any, lamp: StubLight) -> Any:
    card = win.create_device_widget(lamp)
    card.show()
    return card


def test_command_runs_off_the_gui_thread_and_updates_card(
    window: Any, wait_until: Wait
) -> None:
    lamp = StubLight()
    card = _card(window, lamp)
    window.toggle_device_power(card, True)
    wait_until(lambda: card.status_chip.text() == "On")
    assert lamp.threads and lamp.threads[0] is not threading.main_thread()


def test_failed_command_resyncs_card_and_reports(
    window: Any, dialogs: list, wait_until: Wait
) -> None:
    lamp = StubLight(fail=True)
    card = _card(window, lamp)
    card.switch.setChecked(True)  # the user flips the switch; the hub refuses
    wait_until(lambda: "hub said no" in card.footer_label.text())
    assert card.switch.isChecked() is False  # shows the real state
    assert card.footer_label.text().startswith("Couldn't")
    assert dialogs == []


def test_card_error_clears_after_its_timeout(
    window: Any, monkeypatch: pytest.MonkeyPatch, wait_until: Wait
) -> None:
    from widgets import card as card_module

    monkeypatch.setattr(card_module, "CARD_ERROR_MS", 30)
    card = _card(window, StubLight())
    card._error_timer.setInterval(30)
    card.show_error("Couldn't toggle light: boom")
    assert card.footer_label.text() == "Couldn't toggle light: boom"
    card.sync_from_device()  # a resync keeps the error visible
    assert card.footer_label.text() == "Couldn't toggle light: boom"
    wait_until(lambda: "boom" not in card.footer_label.text())


# --- scenes ------------------------------------------------------------------


def test_scene_failure_is_inline_not_modal(
    window: Any, hub: StubHub, dialogs: list, wait_until: Wait
) -> None:
    hub.scenes = [StubScene("s1", "Evening", fail=True)]
    _connect(window, wait_until)
    window.trigger_scene(window.scenes_grid.cards()[0])
    wait_until(lambda: not window._scene_workers[0].isRunning())
    QApplication.processEvents()
    assert dialogs == []


def test_scene_lookup_survives_a_refresh(
    window: Any, hub: StubHub, wait_until: Wait
) -> None:
    _connect(window, wait_until)
    hub.scenes = [StubScene("s1", "Evening")]  # new objects, same id
    window.refresh_devices()
    wait_until(lambda: window._refresh_worker is None)
    new_tile = window.scenes_grid.cards()[0]
    assert window._scene_tile_for(StubScene("s1")) is new_tile


# --- closing (req-14) --------------------------------------------------------


def test_close_waits_for_running_worker(
    window: Any, wait_until: Wait, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    lamp = StubLight()
    original = lamp.set_light

    def slow(lamp_on: bool) -> None:
        release.wait(5)
        original(lamp_on)

    lamp.set_light = slow  # type: ignore[method-assign]
    quits: list[bool] = []
    monkeypatch.setattr(QApplication, "quit", staticmethod(lambda: quits.append(True)))

    card = _card(window, lamp)
    window.toggle_device_power(card, True)
    assert window._running_workers()
    window.close()
    assert window._close_pending and window.isHidden()  # hidden, not destroyed
    release.set()
    wait_until(lambda: bool(quits))
    assert not window._running_workers()
