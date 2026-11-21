"""Automated refresh: in-place card updates (t-19) and polling (t-56)."""

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
