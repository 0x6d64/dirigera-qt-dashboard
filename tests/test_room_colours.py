"""Room colours: hub colour names, marker colours and the toggle (req-22, t-86)."""

from typing import Any

import pytest
from conftest import make_device
from test_theme_contrast import contrast

import theme
from dashboard import DirigeraDashboard
from rooms import room_colour_name
from widgets.cardbase import RoomSectionHeader


@pytest.mark.parametrize(
    "name, hue",
    [
        ("ikea_green_no_65", "green"),
        ("ikea_blue_no_63", "blue"),
        ("ikea_lilac_no_1", "lilac"),
        ("Turquoise", "turquoise"),
    ],
)
def test_hub_colour_names_map_to_their_hue(name: str, hue: str) -> None:
    assert theme.room_colour(name) == theme.ROOM_COLOURS[hue]


def test_the_first_known_hue_word_wins() -> None:
    assert theme.room_colour("red_blue") == theme.ROOM_COLOURS["red"]


@pytest.mark.parametrize("name", [None, "", "ikea_unknown_no_1", "ikea"])
def test_unknown_or_missing_names_stay_neutral(name: Any) -> None:
    assert theme.room_colour(name) is None


@pytest.mark.parametrize("colour", sorted(theme.ROOM_COLOURS))
def test_every_room_colour_is_visible_on_window_and_surface(colour: str) -> None:
    value = theme.ROOM_COLOURS[colour]
    assert contrast(value, theme.WINDOW) >= 3.0
    assert contrast(value, theme.SURFACE) >= 3.0


def test_room_colour_name_reads_the_hub_room_colour() -> None:
    device = make_device("light")
    device.room.color = "ikea_green_no_65"
    assert room_colour_name(device) == "ikea_green_no_65"


def test_room_colour_name_is_none_for_stub_rooms_without_a_colour() -> None:
    assert room_colour_name(make_device("light")) is None


def test_room_colour_name_is_none_for_a_device_without_a_room() -> None:
    assert room_colour_name(make_device("light", room=None)) is None


# --- the Rooms and Energy views with the toggle (t-86) -----------------------

GREEN = theme.ROOM_COLOURS["green"]
BLUE = theme.ROOM_COLOURS["blue"]


def _in_room(device: Any, colour: str | None = None) -> Any:
    """Put a stub device in a room that has the hub colour `colour`."""
    if colour is not None:
        device.room.color = colour
    return device


def _light(id_: str, room: str, room_name: str, colour: str | None = None) -> Any:
    device = make_device(
        "light", id_, room_name, room=(room, room_name), is_on=False, light_level=50
    )
    return _in_room(device, colour)


def _card(win: Any, device_id: str) -> Any:
    return win._device_cards[device_id]


def _header(win: Any, room_id: str) -> Any:
    return win._sections[room_id][2]


def _energy_card(win: Any, device_id: str) -> Any:
    return next(c for c in win.energy_view.cards() if c.device.id == device_id)


def test_room_colours_are_off_by_default(window: Any) -> None:
    window._on_refreshed([_light("l1", "r1", "Kitchen", "ikea_green_no_65")], [])
    assert window.room_colours_switch.isChecked() is False
    assert _card(window, "l1").edge_colour is None
    assert _header(window, "r1").dot_colour is None


def test_toggle_marks_rooms_with_a_known_colour(window: Any) -> None:
    window._on_refreshed(
        [
            _light("l1", "r1", "Kitchen", "ikea_green_no_65"),
            _light("l2", "r2", "Office", "ikea_blue_no_63"),
            _light("l3", "r3", "Hall"),
        ],
        [],
    )
    window.room_colours_switch.click()

    kitchen = _card(window, "l1")
    assert kitchen.edge_colour == GREEN
    assert f"border-left: {theme.ROOM_EDGE}px solid {GREEN}" in kitchen.styleSheet()
    assert _header(window, "r1").dot_colour == GREEN
    assert not _header(window, "r1").dot.isHidden()
    assert _card(window, "l2").edge_colour == BLUE
    assert _header(window, "r2").dot_colour == BLUE

    # A room without a colour stays neutral.
    assert _card(window, "l3").edge_colour is None
    assert _header(window, "r3").dot_colour is None
    assert _header(window, "r3").dot.isHidden()


def test_unknown_colour_names_stay_neutral(window: Any) -> None:
    window._on_refreshed(
        [_light("l1", "r1", "Kitchen", "ikea_unknown_no_1")],
        [],
    )
    window.room_colours_switch.click()
    assert _card(window, "l1").edge_colour is None
    assert _header(window, "r1").dot_colour is None


def test_toggle_restyles_in_place_and_sends_no_command(window: Any) -> None:
    window._on_refreshed([_light("l1", "r1", "Kitchen", "ikea_green_no_65")], [])
    card = _card(window, "l1")
    header = _header(window, "r1")
    name_style = card.name_label.styleSheet()
    type_style = card.type_label.styleSheet()

    window.room_colours_switch.click()
    assert _card(window, "l1") is card
    assert _header(window, "r1") is header
    assert card.name_label.styleSheet() == name_style
    assert card.type_label.styleSheet() == type_style

    window.room_colours_switch.click()
    assert card.edge_colour is None
    assert header.dot_colour is None
    assert window._command_workers == []
    assert window._scene_workers == []


def test_refresh_keeps_the_mode_and_follows_room_changes(window: Any) -> None:
    window._on_refreshed([_light("l1", "r1", "Kitchen", "ikea_green_no_65")], [])
    window.room_colours_switch.click()

    # The room is recoloured in the app; the next refresh shows it.
    window._on_refreshed([_light("l1", "r1", "Kitchen", "ikea_blue_no_63")], [])
    assert window.room_colours_switch.isChecked() is True
    assert _card(window, "l1").edge_colour == BLUE
    assert _header(window, "r1").dot_colour == BLUE

    # A device that appears later in the room is marked as well.
    window._on_refreshed(
        [
            _light("l1", "r1", "Kitchen", "ikea_blue_no_63"),
            _light("l4", "r1", "Kitchen", "ikea_blue_no_63"),
        ],
        [],
    )
    assert _card(window, "l4").edge_colour == BLUE


def test_the_room_colours_choice_persists_into_a_new_window(window: Any) -> None:
    window._on_refreshed([_light("l1", "r1", "Kitchen", "ikea_green_no_65")], [])
    window.room_colours_switch.click()

    later = DirigeraDashboard()
    try:
        assert later.room_colours_switch.isChecked() is True
        later._on_refreshed([_light("l1", "r1", "Kitchen", "ikea_green_no_65")], [])
        assert _card(later, "l1").edge_colour == GREEN
        assert _header(later, "r1").dot_colour == GREEN
    finally:
        later.hide()
        later.deleteLater()


def test_energy_view_follows_the_room_colour_mode(window: Any) -> None:
    plug = make_device(
        "outlet",
        "o1",
        "Plug",
        room=("r1", "Kitchen"),
        is_on=False,
        current_active_power=5.0,
    )
    window._on_refreshed([_in_room(plug, "ikea_green_no_65")], [])
    card = _energy_card(window, "o1")
    assert card.edge_colour is None

    window.room_colours_switch.click()
    assert _energy_card(window, "o1") is card
    assert card.edge_colour == GREEN
    headers = window.energy_view.content.findChildren(RoomSectionHeader)
    assert [h.dot_colour for h in headers] == [GREEN]

    window.room_colours_switch.click()
    assert card.edge_colour is None
    assert [h.dot_colour for h in headers] == [None]
