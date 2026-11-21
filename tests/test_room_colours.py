"""Room colours: hub colour names, marker colours and the toggle (req-22, t-86)."""

from typing import Any

import pytest
from conftest import make_device
from test_theme_contrast import contrast

import theme
from rooms import room_colour_name


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
