"""Small design gaps: scene grid width, refresh feedback, keyboard, names."""

import threading
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from conftest import StubHub, StubScene, make_device
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QPushButton

import workers
from widgets.grid import CardGrid
from widgets.scene import SCENE_MIN_WIDTH

Wait = Callable[..., None]


def test_scene_grid_fits_more_columns_than_device_grid(qapp) -> None:
    devices = CardGrid()
    scenes = CardGrid(min_width=SCENE_MIN_WIDTH)
    for grid in (devices, scenes):
        grid.resize(800, 400)
    assert scenes.columns() > devices.columns()


class GatedHub(StubHub):
    """A hub whose device fetch waits until the test releases it."""

    def __init__(self) -> None:
        super().__init__(devices=[make_device("light", "l1", "Lamp", is_on=True)])
        self.gate = threading.Event()

    def get_all_devices(self) -> list[Any]:
        self.gate.wait(timeout=5)
        return super().get_all_devices()


@pytest.fixture
def gated(window: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[GatedHub]:
    hub = GatedHub()
    monkeypatch.setattr(workers, "Hub", lambda token, ip_address: hub)
    window.connection_block.ip_input.setText("10.0.0.2")
    window.connection_block.token_input.setText("tok")
    window.connect_to_hub()
    yield hub
    hub.gate.set()  # never leave the worker waiting


def test_refresh_button_shows_progress_until_the_fetch_ends(
    window: Any, gated: GatedHub, wait_until: Wait
) -> None:
    wait_until(lambda: window._refresh_worker is not None)
    assert window.refresh_button.text() == "Refreshing…"
    assert not window.refresh_button.isEnabled()
    gated.gate.set()
    wait_until(lambda: window._refresh_worker is None)
    assert window.refresh_button.text() == "Refresh"
    assert window.refresh_button.isEnabled()


def test_skeleton_cards_show_until_the_first_refresh(
    window: Any, gated: GatedHub, wait_until: Wait
) -> None:
    wait_until(lambda: window._refresh_worker is not None)
    assert window.skeleton is not None
    assert len(window.skeleton.cards()) > 0
    gated.gate.set()
    wait_until(lambda: window._refresh_worker is None)
    assert window.skeleton is None
    assert window._device_cards


def test_energy_card_without_readable_state_has_no_chip(qapp) -> None:
    from widgets.energy import EnergyCard

    sensor = make_device("electricalSensor", "e1", "Meter", current_active_power=5.0)
    assert EnergyCard(sensor).status_chip.isHidden()
    outlet = make_device("outlet", "o1", "Heater", is_on=True)
    card = EnergyCard(outlet)
    assert card.status_chip.text() == "On" and not card.status_chip.isHidden()
    card.update_from_device(make_device("outlet", "o1", "Heater", is_on=None))
    assert card.status_chip.isHidden()


def test_arrow_keys_switch_the_view(window: Any) -> None:
    window.show_views()
    switcher = window.view_switcher
    assert switcher.current_index() == 0
    QTest.keyClick(switcher.button(0), Qt.Key.Key_Right)  # type: ignore[call-overload]
    assert switcher.current_index() == 1
    assert window.tab_widget.currentIndex() == 1
    QTest.keyClick(switcher.button(1), Qt.Key.Key_Left)  # type: ignore[call-overload]
    assert window.tab_widget.currentIndex() == 0


def test_accessible_names_on_cards_and_scene_tiles(qapp) -> None:
    from widgets.card import DeviceCard
    from widgets.scene import SceneTile

    light = DeviceCard(make_device("light", "l1", "Lamp", is_on=True, light_level=40))
    assert light.switch.accessibleName() == "Lamp power"
    assert light.brightness_slider.accessibleName() == "Lamp brightness"

    blind = make_device("blinds", "b1", "Shade", blinds_current_level=50)
    blind.capabilities.can_receive = ["blindsState"]
    card = DeviceCard(blind)
    assert card.blind_slider.accessibleName() == "Shade position"
    names = {b.accessibleName() for b in card.findChildren(QPushButton)}
    assert {"Shade up", "Shade stop", "Shade down"} <= names

    tile = SceneTile(StubScene("s1", "Evening"))
    assert tile.activate_button.accessibleName() == "Activate Evening"
