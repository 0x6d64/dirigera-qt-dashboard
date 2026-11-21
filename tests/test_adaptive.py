"""Adaptive profile helpers and wiring (t-15)."""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import StubHub, StubScene, make_device, make_profile

import workers
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


# --- fetching profiles with the refresh ---------------------------------------

Wait = Callable[..., None]


@pytest.fixture
def hub(monkeypatch: pytest.MonkeyPatch) -> StubHub:
    stub = StubHub(
        devices=[make_device("light", "l1", "Lamp", is_on=True, light_level=40)],
        scenes=[StubScene("s1", "Evening")],
    )
    stub.profiles = [make_profile("p1", "Day"), make_profile("p2", "Night")]
    monkeypatch.setattr(workers, "Hub", lambda token, ip_address: stub)
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


def test_connect_fetches_profiles_once(connected: Any, hub: StubHub) -> None:
    assert hub.profile_calls == 1
    assert profile_options(connected.adaptive_profiles) == [
        ("p1", "Day"),
        ("p2", "Night"),
    ]


def test_manual_refresh_and_poll_fetch_profiles(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    _refresh(connected, wait_until)
    assert hub.profile_calls == 2
    connected._poll()
    wait_until(lambda: connected._refresh_worker is None)
    assert hub.profile_calls == 3


def test_background_refresh_does_not_fetch_profiles(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    connected._request_background_refresh()
    wait_until(lambda: connected._refresh_worker is None)
    assert hub.profile_calls == 1


def test_failing_profile_fetch_keeps_devices_and_list(
    connected: Any,
    hub: StubHub,
    wait_until: Wait,
    dialogs: list[tuple[str, str]],
) -> None:
    hub.profiles_fail = True
    hub.devices = [make_device("light", "l1", "Lamp", is_on=True, light_level=80)]
    _refresh(connected, wait_until)
    assert hub.profile_calls == 2
    card = connected._room_sections[0][1].cards()[0]
    assert card.brightness_slider.value() == 80
    assert [p.id for p in connected.adaptive_profiles] == ["p1", "p2"]
    assert connected._status_is_failure is False
    assert dialogs == []


def test_signature_sees_adaptive_state_and_profile_names(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    before = connected._signature
    hub.devices = [
        make_device(
            "light", "l1", "Lamp", is_on=True, light_level=40, adaptive=("p1", True)
        )
    ]
    _refresh(connected, wait_until)
    after_state = connected._signature
    assert after_state != before
    assert connected.devices[0].adaptive_profile.id == "p1"

    hub.profiles = [make_profile("p1", "Dawn"), make_profile("p2", "Night")]
    _refresh(connected, wait_until)
    assert connected._signature != after_state
    assert profile_options(connected.adaptive_profiles)[0] == ("p1", "Dawn")
