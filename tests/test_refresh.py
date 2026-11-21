"""Automated refresh: in-place card updates (t-19) and polling (t-56)."""

import threading
from collections.abc import Callable
from typing import Any

import pytest
from conftest import StubHub, StubScene, make_device

import dashboard
from dashboard import widget_name

Wait = Callable[..., None]


def _devices(level: int = 40, lamp_on: bool = True) -> list[Any]:
    """Fresh device objects, like a new fetch from the hub."""
    return [
        make_device("light", "l1", "Lamp", is_on=lamp_on, light_level=level),
        make_device("outlet", "o1", "Heater", room=("r2", "Bedroom"), is_on=False),
        make_device(
            "electrical_sensor",
            "e1",
            "Meter",
            room=("r2", "Bedroom"),
            current_active_power=5.0,
        ),
    ]


@pytest.fixture
def hub(monkeypatch: pytest.MonkeyPatch) -> StubHub:
    stub = StubHub(devices=_devices(), scenes=[StubScene("s1", "Evening")])
    monkeypatch.setattr(dashboard, "Hub", lambda token, ip_address: stub)
    return stub


@pytest.fixture
def connected(window: Any, hub: StubHub, wait_until: Wait) -> Any:
    window.connection_block.ip_input.setText("10.0.0.2")
    window.connection_block.token_input.setText("tok")
    window.connect_to_hub()
    wait_until(lambda: window.hub is not None and window._refresh_worker is None)
    return window


def _refresh(win: Any, wait_until: Wait) -> None:
    win.refresh_devices()
    wait_until(lambda: win._refresh_worker is None)


def _cards(win: Any) -> dict[str, Any]:
    return {c.device.id: c for _, grid in win._room_sections for c in grid.cards()}


# --- in-place update (t-19) --------------------------------------------------


def test_refresh_updates_the_same_cards_in_place(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    before = _cards(connected)
    assert before["l1"].brightness_slider.value() == 40
    hub.devices = _devices(level=80, lamp_on=False)
    _refresh(connected, wait_until)
    after = _cards(connected)
    assert all(after[i] is before[i] for i in before)  # identity, not recreated
    assert after["l1"].brightness_slider.value() == 80
    assert after["l1"].switch.isChecked() is False
    assert after["l1"].status_chip.text() == "Off"
    assert after["l1"].device is hub.devices[0]


def test_new_device_adds_a_card_and_vanished_one_removes_it(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    before = _cards(connected)
    hub.devices = _devices() + [make_device("light", "l2", "Hall", is_on=False)]
    _refresh(connected, wait_until)
    after = _cards(connected)
    assert set(after) == {"l1", "l2", "o1", "e1"}
    assert after["l1"] is before["l1"]

    hub.devices = [d for d in _devices() if d.id != "o1"]
    _refresh(connected, wait_until)
    assert set(_cards(connected)) == {"l1", "e1"}


def test_vanished_room_removes_its_section(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    assert len(connected._room_sections) == 2
    hub.devices = [d for d in _devices() if d.id == "l1"]
    _refresh(connected, wait_until)
    assert len(connected._room_sections) == 1
    assert list(_cards(connected)) == ["l1"]


def test_scene_tiles_are_kept_and_new_scenes_added(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    tile = connected.scenes_grid.cards()[0]
    hub.scenes = [StubScene("s1", "Evening"), StubScene("s2", "Morning")]
    _refresh(connected, wait_until)
    tiles = connected.scenes_grid.cards()
    assert [widget_name(t) for t in tiles] == ["Evening", "Morning"]
    assert tiles[0] is tile
    assert tile.scene is hub.scenes[0]


def test_slider_being_dragged_keeps_its_value(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    card = _cards(connected)["l1"]
    slider = card.brightness_slider
    slider._slider.setSliderDown(True)
    slider._slider.setValue(65)  # the user is dragging
    hub.devices = _devices(level=10)
    _refresh(connected, wait_until)
    assert slider.value() == 65
    slider._slider.setSliderDown(False)
    hub.devices = _devices(level=20)
    _refresh(connected, wait_until)
    assert slider.value() == 20


def test_identical_data_leaves_the_widgets_and_caption_alone(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    caption = connected.status_label.text()
    assert caption.startswith("Found 3 devices")
    connected.set_status_text("marker")  # would be replaced by a rebuild
    before = _cards(connected)
    hub.devices = _devices()  # new objects, same content
    _refresh(connected, wait_until)
    assert connected.status_label.text() == "marker"
    assert _cards(connected) == before


def test_energy_cards_update_in_place(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    card = next(c for c in connected.energy_view.cards() if c.device.id == "e1")
    assert card.power_metric.value_text == "5"
    hub.devices = _devices()
    hub.devices[2].attributes.current_active_power = 42.0
    _refresh(connected, wait_until)
    same = next(c for c in connected.energy_view.cards() if c.device.id == "e1")
    assert same is card
    assert card.power_metric.value_text == "42"


def test_filter_survives_an_in_place_refresh(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    connected.search_input.setText("lamp")
    hub.devices = _devices(level=70) + [make_device("light", "l2", "Hall")]
    _refresh(connected, wait_until)
    visible = [
        widget_name(c)
        for _, grid in connected._room_sections
        for c in grid.cards()
        if not c.isHidden()
    ]
    assert visible == ["Lamp"]


# --- periodic refresh (t-56) -------------------------------------------------


def test_timer_runs_every_30_seconds_once_connected(
    window: Any, connected: Any
) -> None:
    assert window.refresh_timer.isActive()
    assert window.refresh_timer.interval() == 30_000
    assert "every 30 s" in window.update_label.text()
    assert window.update_label.text().startswith("Updated ")


def test_timer_is_idle_without_a_hub(window: Any) -> None:
    assert not window.refresh_timer.isActive()
    window._poll()  # no hub: nothing happens
    assert window._refresh_worker is None


def test_poll_during_an_in_flight_refresh_starts_no_second_worker(
    connected: Any, wait_until: Wait
) -> None:
    connected.refresh_devices()
    worker = connected._refresh_worker
    assert worker is not None
    connected._poll()
    assert connected._refresh_worker is worker
    wait_until(lambda: connected._refresh_worker is None)


def test_poll_refreshes_when_idle(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    hub.devices = _devices(level=90)
    connected._poll()
    assert connected._refresh_worker is not None
    wait_until(lambda: connected._refresh_worker is None)
    assert _cards(connected)["l1"].brightness_slider.value() == 90


def test_poll_while_minimised_does_nothing(
    connected: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(connected, "isMinimized", lambda: True)
    connected._poll()
    assert connected._refresh_worker is None


def test_minimising_pauses_the_timer_and_restoring_polls_at_once(
    connected: Any, monkeypatch: pytest.MonkeyPatch, wait_until: Wait
) -> None:
    from PyQt6.QtCore import QEvent

    event = QEvent(QEvent.Type.WindowStateChange)
    monkeypatch.setattr(connected, "isMinimized", lambda: True)
    connected.changeEvent(event)
    assert not connected.refresh_timer.isActive()

    monkeypatch.setattr(connected, "isMinimized", lambda: False)
    connected.changeEvent(event)
    assert connected.refresh_timer.isActive()
    assert connected._refresh_worker is not None  # the catch-up poll
    wait_until(lambda: connected._refresh_worker is None)


def test_failed_background_refresh_shows_no_dialog_but_marks_stale_data(
    connected: Any, hub: StubHub, dialogs: list, wait_until: Wait
) -> None:
    before = list(_cards(connected))
    hub.fail = True
    connected._poll()
    wait_until(lambda: connected._refresh_worker is None)
    assert dialogs == []
    assert connected.status_label.text().startswith("Refresh failed")
    assert not connected.stale_label.isHidden()
    assert connected.stale_label.text().startswith("Showing data from")
    assert list(_cards(connected)) == before


def test_failed_manual_refresh_reports_inline(
    connected: Any, hub: StubHub, dialogs: list, wait_until: Wait
) -> None:
    hub.fail = True
    _refresh(connected, wait_until)
    assert dialogs == []
    assert connected.status_label.text().startswith("Refresh failed")
    assert not connected.stale_label.isHidden()


def test_recovery_with_unchanged_data_clears_the_failure_caption(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    summary = connected.status_label.text()
    hub.fail = True
    connected._poll()
    wait_until(lambda: connected._refresh_worker is None)
    hub.fail = False
    connected._poll()
    wait_until(lambda: connected._refresh_worker is None)
    assert connected.status_label.text() == summary
    assert connected.stale_label.isHidden()


def test_update_caption_warns_when_older_than_two_intervals(
    connected: Any,
) -> None:
    from datetime import datetime, timedelta

    connected._last_refresh = datetime.now() - timedelta(seconds=61)
    connected._update_caption()
    assert connected.update_label.property("tone") == "warn"
    connected._last_refresh = datetime.now()
    connected._update_caption()
    assert not connected.update_label.property("tone")


def test_close_stops_the_timer(connected: Any) -> None:
    connected.close()
    assert not connected.refresh_timer.isActive()


# --- refresh after a scene activation (t-79) ----------------------------------


def _activate(win: Any, wait_until: Wait) -> Any:
    """Activate the first scene tile and wait for its inline result."""
    tile = win.scenes_grid.cards()[0]
    win.trigger_scene(tile)
    wait_until(lambda: tile.status_label.text() in ("Activated", "Failed"))
    return tile


def test_successful_activation_refreshes_once_and_shows_new_state(
    connected: Any,
    hub: StubHub,
    monkeypatch: pytest.MonkeyPatch,
    wait_until: Wait,
) -> None:
    monkeypatch.setattr(dashboard, "SCENE_REFRESH_DELAY_MS", 10)
    scene = connected.scenes_grid.cards()[0].scene

    def trigger_changes_hub() -> None:
        scene.triggered += 1
        hub.devices = _devices(level=99)  # the hub applies the scene

    monkeypatch.setattr(scene, "trigger", trigger_changes_hub)
    before = len(hub.calls)
    _activate(connected, wait_until)
    wait_until(lambda: len(hub.calls) > before and connected._refresh_worker is None)
    assert len(hub.calls) == before + 1
    assert _cards(connected)["l1"].brightness_slider.value() == 99


def test_quick_activations_cause_one_fetch(
    connected: Any,
    hub: StubHub,
    monkeypatch: pytest.MonkeyPatch,
    wait_until: Wait,
    pump: Callable[[int], None],
) -> None:
    monkeypatch.setattr(dashboard, "SCENE_REFRESH_DELAY_MS", 300)
    tile = connected.scenes_grid.cards()[0]
    before = len(hub.calls)
    connected.trigger_scene(tile)
    connected.trigger_scene(tile)
    wait_until(lambda: tile.scene.triggered == 2)
    wait_until(lambda: len(hub.calls) > before and connected._refresh_worker is None)
    pump(450)  # long enough for a second, uncoalesced fetch to have started
    assert len(hub.calls) == before + 1


def test_activation_during_a_fetch_refreshes_again_after_it(
    connected: Any,
    hub: StubHub,
    monkeypatch: pytest.MonkeyPatch,
    wait_until: Wait,
) -> None:
    monkeypatch.setattr(dashboard, "SCENE_REFRESH_DELAY_MS", 0)
    gate = threading.Event()
    fetches: list[int] = []
    original = hub.get_all_devices

    def gated_fetch() -> list[Any]:
        fetches.append(1)
        if len(fetches) == 1:
            gate.wait(5)  # hold the first fetch in flight
        return original()

    monkeypatch.setattr(hub, "get_all_devices", gated_fetch)
    connected.refresh_devices()
    connected.trigger_scene(connected.scenes_grid.cards()[0])
    wait_until(lambda: connected._refresh_pending)
    gate.set()
    wait_until(lambda: len(fetches) == 2 and connected._refresh_worker is None)
    assert not connected._refresh_pending


def test_failed_activation_schedules_no_fetch(
    connected: Any,
    hub: StubHub,
    monkeypatch: pytest.MonkeyPatch,
    wait_until: Wait,
    pump: Callable[[int], None],
) -> None:
    monkeypatch.setattr(dashboard, "SCENE_REFRESH_DELAY_MS", 10)
    tile = connected.scenes_grid.cards()[0]
    tile.scene.fail = True
    before = len(hub.calls)
    connected.trigger_scene(tile)
    wait_until(lambda: tile.status_label.text() == "Failed")
    pump(100)  # well past the 10 ms delay
    assert len(hub.calls) == before
    assert connected._refresh_worker is None


def test_failed_scene_refresh_records_no_dialog(
    connected: Any,
    hub: StubHub,
    dialogs: list,
    monkeypatch: pytest.MonkeyPatch,
    wait_until: Wait,
) -> None:
    monkeypatch.setattr(dashboard, "SCENE_REFRESH_DELAY_MS", 10)
    hub.fail = True
    before = len(hub.calls)
    _activate(connected, wait_until)
    wait_until(lambda: len(hub.calls) > before and connected._refresh_worker is None)
    assert connected.status_label.text().startswith("Refresh failed")
    assert dialogs == []
