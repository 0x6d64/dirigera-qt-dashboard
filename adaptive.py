"""Adaptive lighting helpers (t-15, doc/dirigera-api.md §2.5 and §5 item 7).

Pure functions, no Qt: the profile list for the picker, the profile a light
follows, and whether a light gets a picker at all.
"""

from typing import Any, Iterable, List, Optional, Set, Tuple

UNNAMED_PROFILE = "Unnamed profile"
UNKNOWN_PROFILE = "Unknown profile"


def profile_options(profiles: Iterable[Any]) -> List[Tuple[str, str]]:
    """`(id, label)` per profile, in the hub's order.

    Profiles without a non-empty string id and repeated ids are skipped. The
    label is the stripped name, or `UNNAMED_PROFILE` when missing or blank; a
    repeated label gets " (2)", " (3)" appended so the picker stays unambiguous.
    """
    options: List[Tuple[str, str]] = []
    seen_ids: Set[str] = set()
    label_counts: dict[str, int] = {}
    for profile in profiles:
        profile_id = getattr(profile, "id", None)
        if not isinstance(profile_id, str) or not profile_id:
            continue
        if profile_id in seen_ids:
            continue
        seen_ids.add(profile_id)
        name = getattr(profile, "name", None)
        label = name.strip() if isinstance(name, str) else ""
        label = label or UNNAMED_PROFILE
        count = label_counts.get(label, 0) + 1
        label_counts[label] = count
        options.append((profile_id, label if count == 1 else f"{label} ({count})"))
    return options


def active_profile_id(device: Any) -> Optional[str]:
    """The id of the profile the light follows, or `None`.

    The state is the top-level `adaptive_profile` field (not on
    `attributes`); it counts only when `active is True` and the id is a
    non-empty string.
    """
    state = getattr(device, "adaptive_profile", None)
    if state is None or getattr(state, "active", None) is not True:
        return None
    profile_id = getattr(state, "id", None)
    if isinstance(profile_id, str) and profile_id:
        return profile_id
    return None


def supports_adaptive(device: Any) -> bool:
    """Whether a light gets the adaptive picker.

    Observed on the real hub (doc/dirigera-api.md §5 item 7): lights list no
    `adaptiveProfile` capability in `canReceive`, and a light that follows a
    profile has no `colorTemperature` capability either, so capabilities are
    no guide. The rule: a `light` that carries the `adaptive_profile` field
    with a state object (the hub sent the key, even as `{}`), or that already
    reports an active profile. Whether the hub accepts a profile on a light
    reporting `{}` is unknown; a failed activation shows the card error.
    """
    if getattr(device, "device_type", None) != "light":
        return False
    return (
        getattr(device, "adaptive_profile", None) is not None
        or active_profile_id(device) is not None
    )
