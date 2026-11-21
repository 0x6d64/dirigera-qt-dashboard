"""Room helpers: grouping devices by room and labelling the sections.

Pure functions, no Qt. The Rooms and Energy views both use them.
"""

from typing import Any, Dict, List, Optional, Tuple

# Section label for devices that are not assigned to a room.
UNKNOWN_ROOM = "Unknown room"


def format_room_label(room_name: str) -> str:
    """Sentence-case a room name for a section label (design-doc.md §8.9).

    Only the first character is capitalised so acronyms and proper nouns a
    user typed into the IKEA app keep their casing.
    """
    name = room_name.strip()
    if not name:
        return UNKNOWN_ROOM
    return name[0].upper() + name[1:]


def is_energy_device(device: Any) -> bool:
    """Return True for devices that can report energy data (§9.4)."""
    return getattr(device, "device_type", "") in ("outlet", "electricalSensor")


def get_room(device: Any) -> Tuple[str, str]:
    """Return (room id, room name) for a device.

    `device.room` is a pydantic Room model (or None), not a dict. Devices
    without a room share one group under an empty id.
    """
    room = getattr(device, "room", None)
    if room is None:
        return "", UNKNOWN_ROOM
    return str(getattr(room, "id", "") or ""), room.name or UNKNOWN_ROOM


def room_colour_name(device: Any) -> Optional[str]:
    """Return the hub's colour name for a device's room (req-22), if any.

    Stub rooms in tests have no `color`, so it is read with getattr; an empty
    or missing name is None.
    """
    room = getattr(device, "room", None)
    name = getattr(room, "color", None) if room is not None else None
    return name if isinstance(name, str) and name else None


def group_by_room(devices: List[Any]) -> List[Tuple[str, List[Any]]]:
    """Group devices into (room name, devices) pairs in display order.

    Groups are keyed by room id, so two rooms that share a name stay
    separate. Sections sort by name case-insensitively (design-doc.md §14
    item 2: alphabetical), with the id as a stable tie-breaker.
    """
    groups: Dict[str, Tuple[str, List[Any]]] = {}
    for device in devices:
        room_id, room_name = get_room(device)
        groups.setdefault(room_id, (room_name, []))[1].append(device)
    ordered = sorted(groups.items(), key=lambda item: (item[1][0].casefold(), item[0]))
    return [(name, members) for _, (name, members) in ordered]
