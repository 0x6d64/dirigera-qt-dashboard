"""Adaptive profile helpers and wiring (t-15)."""

from types import SimpleNamespace
from typing import Any

import pytest

from adaptive import (
    UNNAMED_PROFILE,
    active_profile_id,
    profile_options,
    supports_adaptive,
)


def prof(id_: Any, name: Any = None) -> SimpleNamespace:
    return SimpleNamespace(id=id_, name=name)


def light(state: Any = "absent", device_type: str = "light") -> SimpleNamespace:
    dev = SimpleNamespace(device_type=device_type)
    if state != "absent":
        dev.adaptive_profile = state
    return dev


def test_options_labels_and_order() -> None:
    got = profile_options([prof("a", " Day "), prof("b"), prof("c", "   ")])
    assert got == [
        ("a", "Day"),
        ("b", UNNAMED_PROFILE),
        ("c", f"{UNNAMED_PROFILE} (2)"),
    ]


def test_options_duplicate_names_and_ids() -> None:
    got = profile_options(
        [prof("a", "Day"), prof("b", "Day"), prof("a", "Other"), prof("c", "Day")]
    )
    assert got == [("a", "Day"), ("b", "Day (2)"), ("c", "Day (3)")]


@pytest.mark.parametrize("bad", [None, "", 5, b"x"])
def test_options_skip_bad_ids(bad: Any) -> None:
    assert profile_options([prof(bad, "X"), prof("ok", "Y")]) == [("ok", "Y")]


def test_options_empty() -> None:
    assert profile_options([]) == []


@pytest.mark.parametrize(
    "state,expected",
    [
        (None, None),
        ("absent", None),
        (SimpleNamespace(id="p", active=False), None),
        (SimpleNamespace(id="p", active=None), None),
        (SimpleNamespace(id=None, active=True), None),
        (SimpleNamespace(id="", active=True), None),
        (SimpleNamespace(id=3, active=True), None),
        (SimpleNamespace(id="p", active=True), "p"),
    ],
)
def test_active_profile_id(state: Any, expected: Any) -> None:
    assert active_profile_id(light(state)) == expected


@pytest.mark.parametrize(
    "dev,expected",
    [
        (light(SimpleNamespace(id="p", active=True)), True),  # follows, off or on
        (light(SimpleNamespace(id=None, active=None)), True),  # hub sent `{}`
        (light(None), False),  # key not sent
        (light("absent"), False),
        (light(SimpleNamespace(id="p", active=True), "outlet"), False),
    ],
)
def test_supports_adaptive(dev: Any, expected: bool) -> None:
    assert supports_adaptive(dev) is expected
