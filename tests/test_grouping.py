"""Pure helpers: room grouping, labels, sort order."""

from types import SimpleNamespace

from conftest import make_device

from rooms import (
    UNKNOWN_ROOM,
    format_room_label,
    group_by_room,
    is_energy_device,
)
from widgets.card import device_sort_key


def test_same_room_name_with_different_ids_stays_separate() -> None:
    a = make_device("light", "a", room=("1", "Hall"))
    b = make_device("light", "b", room=("2", "Hall"))
    groups = group_by_room([a, b])
    assert [name for name, _ in groups] == ["Hall", "Hall"]
    assert [members for _, members in groups] == [[a], [b]]


def test_rooms_sort_case_insensitively_and_keep_unassigned_group() -> None:
    devices = [
        make_device("light", "a", room=("1", "bedroom")),
        make_device("light", "b", room=None),
        make_device("light", "c", room=("2", "Attic")),
    ]
    names = [name for name, _ in group_by_room(devices)]
    assert names == ["Attic", "bedroom", UNKNOWN_ROOM]


def test_format_room_label_only_capitalises_first_letter() -> None:
    assert format_room_label("  living room ") == "Living room"
    assert format_room_label("TV room") == "TV room"
    assert format_room_label("   ") == UNKNOWN_ROOM


def test_energy_devices() -> None:
    assert is_energy_device(SimpleNamespace(device_type="outlet"))
    assert is_energy_device(SimpleNamespace(device_type="electricalSensor"))
    assert not is_energy_device(SimpleNamespace(device_type="light"))


def test_device_sort_puts_lights_before_sensors_then_by_name() -> None:
    sensor = make_device("environmentSensor", "s", name="Air")
    lamp_b = make_device("light", "b", name="b lamp")
    lamp_a = make_device("light", "a", name="A lamp")
    ordered = sorted([sensor, lamp_b, lamp_a], key=device_sort_key)
    assert ordered == [lamp_a, lamp_b, sensor]
