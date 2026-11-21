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


# --- the picker on a light card -------------------------------------------------

OPTIONS = [("p1", "Day"), ("p2", "Night")]


def _lamp(
    adaptive: tuple[str, bool] | None = None,
    id_: str = "l1",
    is_on: bool = True,
) -> SimpleNamespace:
    dev = make_device("light", id_, "Lamp", is_on=is_on, light_level=40)
    if adaptive is not None:
        dev.adaptive_profile = SimpleNamespace(id=adaptive[0], active=adaptive[1])
    return dev


def _empty_state(dev: SimpleNamespace) -> SimpleNamespace:
    """The hub sent `adaptiveProfile: {}`: a state object with nothing in it."""
    dev.adaptive_profile = SimpleNamespace(id=None, active=None)
    return dev


def _texts(box: Any) -> list[str]:
    return [box.itemText(i) for i in range(box.count())]


def _card(
    qapp: Any,
    dev: Any,
    options: list[tuple[str, str]] = OPTIONS,
    calls: list[Any] | None = None,
) -> Any:
    from widgets.card import DeviceCard

    sink = calls if calls is not None else []
    return DeviceCard(
        dev, on_profile=lambda card, pid: sink.append(pid), profiles=options
    )


def test_row_only_on_supported_lights_with_profiles(qapp: Any) -> None:
    from widgets.card import DeviceCard

    assert not hasattr(_card(qapp, _lamp()), "profile_box")  # key not sent
    assert not hasattr(
        DeviceCard(make_device("outlet", "o1", "Plug", is_on=True)), "profile_box"
    )
    assert _card(qapp, _empty_state(_lamp()), options=[])._profile_row.isHidden()
    assert not _card(qapp, _empty_state(_lamp()))._profile_row.isHidden()


def test_box_texts_for_the_two_real_states(qapp: Any) -> None:
    # A switched-off light that follows a profile (the hub reports it).
    following = _card(qapp, _lamp(adaptive=("p2", True), is_on=False))
    box = following.profile_box
    assert _texts(box) == ["Off", "Day", "Night"]
    assert box.currentText() == "Night"
    assert box.model().item(0).isEnabled() is False
    assert "stop following" in box.toolTip()
    # A light reporting `{}`: picker shown, "Off" selected and enabled.
    idle = _card(qapp, _empty_state(_lamp()))
    assert idle.profile_box.currentText() == "Off"
    assert idle.profile_box.model().item(0).isEnabled() is True
    assert idle.profile_box.toolTip() == ""


def test_unknown_profile_is_shown_and_not_selectable(qapp: Any) -> None:
    card = _card(qapp, _lamp(adaptive=("gone", True)))
    box = card.profile_box
    assert box.currentText() == "Unknown profile"
    assert box.model().item(box.currentIndex()).isEnabled() is False
    card.update_from_device(_lamp(adaptive=("p1", True)))
    assert _texts(box) == ["Off", "Day", "Night"]
    assert box.currentText() == "Day"


def test_refresh_updates_the_box_without_a_command(qapp: Any) -> None:
    calls: list[Any] = []
    card = _card(qapp, _empty_state(_lamp()), calls=calls)
    card.update_from_device(_lamp(adaptive=("p1", True)))
    assert card.profile_box.currentText() == "Day"
    card.set_profiles([("p1", "Dawn"), ("p2", "Night")])
    assert card.profile_box.currentText() == "Dawn"
    card.update_from_device(_empty_state(_lamp()))
    assert card.profile_box.currentText() == "Off"
    assert calls == []


def test_running_timer_protects_the_choice(
    qapp: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import widgets.card as card_module

    monkeypatch.setattr(card_module, "PROFILE_COMMIT_MS", 10_000)
    card = _card(qapp, _empty_state(_lamp()))
    box = card.profile_box
    box.setCurrentIndex(2)
    box.activated.emit(2)
    card.update_from_device(_empty_state(_lamp()))
    assert box.currentText() == "Night"  # the user's pick survives a refresh
    card.sync_from_device()  # a command resync is not protected
    assert box.currentText() == "Off"


def test_offline_disables_the_box(qapp: Any) -> None:
    card = _card(qapp, _empty_state(_lamp()))
    card.set_offline(True)
    assert card.profile_box.isEnabled() is False
    card.set_offline(False)
    assert card.profile_box.isEnabled() is True


def test_picking_calls_back_once_with_the_id(
    qapp: Any, monkeypatch: pytest.MonkeyPatch, wait_until: Wait
) -> None:
    import widgets.card as card_module

    monkeypatch.setattr(card_module, "PROFILE_COMMIT_MS", 0)
    calls: list[Any] = []
    card = _card(qapp, _empty_state(_lamp()), calls=calls)
    box = card.profile_box
    box.setCurrentIndex(1)
    box.activated.emit(1)
    box.setCurrentIndex(2)  # quick second click: the last choice wins
    box.activated.emit(2)
    wait_until(lambda: calls)
    wait_until(lambda: not card._profile_timer.isActive())
    assert calls == ["p2"]


def test_picking_the_active_profile_calls_nothing(
    qapp: Any, monkeypatch: pytest.MonkeyPatch, wait_until: Wait
) -> None:
    import widgets.card as card_module

    monkeypatch.setattr(card_module, "PROFILE_COMMIT_MS", 0)
    calls: list[Any] = []
    card = _card(qapp, _lamp(adaptive=("p1", True)), calls=calls)
    card.profile_box.activated.emit(1)
    wait_until(lambda: not card._profile_timer.isActive())
    assert calls == []


def test_wheel_does_not_change_the_profile(qapp: Any) -> None:
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QWheelEvent

    card = _card(qapp, _empty_state(_lamp()))
    box = card.profile_box
    event = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    qapp.sendEvent(box, event)
    assert box.currentIndex() == 0


def test_dashboard_card_gets_profiles_and_search_still_matches(
    connected: Any, hub: StubHub, wait_until: Wait
) -> None:
    hub.devices = [_empty_state(_lamp(id_="l2"))]  # a new card, built with the row
    _refresh(connected, wait_until)
    card = connected._room_sections[0][1].cards()[0]
    assert _texts(card.profile_box) == ["Off", "Day", "Night"]
    hub.profiles = [make_profile("p1", "Dawn")]
    _refresh(connected, wait_until)
    assert _texts(card.profile_box) == ["Off", "Dawn"]
    connected.search_input.setText("lamp")
    assert card.isHidden() is False
    connected.search_input.setText("zzz")
    assert card.isHidden() is True


# --- activating a profile and the delayed refresh ------------------------------


def _stub_lamp(adaptive: tuple[str, bool] | None = None, fail: bool = False) -> Any:
    from conftest import StubLight

    lamp = StubLight(fail=fail)
    lamp.attributes.is_on = True
    lamp.adaptive_profile = (
        SimpleNamespace(id=adaptive[0], active=adaptive[1])
        if adaptive
        else SimpleNamespace(id=None, active=None)
    )
    return lamp


def _card_of(win: Any) -> Any:
    return win._room_sections[0][1].cards()[0]


def _pick(card: Any, index: int) -> None:
    card.profile_box.setCurrentIndex(index)
    card.profile_box.activated.emit(index)


@pytest.fixture
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    import dashboard
    import widgets.card as card_module

    monkeypatch.setattr(dashboard, "ADAPTIVE_REFRESH_DELAY_MS", 10)
    monkeypatch.setattr(card_module, "PROFILE_COMMIT_MS", 0)


def test_choosing_a_profile_activates_it_then_refreshes_from_the_hub(
    connected: Any,
    hub: StubHub,
    wait_until: Wait,
    fast: None,
    dialogs: list[tuple[str, str]],
) -> None:
    import threading

    lamp = _stub_lamp()
    gate = threading.Event()
    activate = lamp.activate_adaptive_profile

    def slow(profile_id: str) -> None:
        gate.wait(5)  # hold the command so "Sending…" can be observed
        activate(profile_id)

    lamp.activate_adaptive_profile = slow
    hub.devices = [lamp]
    _refresh(connected, wait_until)
    card = _card_of(connected)
    fetches = len(hub.calls)

    _pick(card, 1)
    wait_until(lambda: card.footer_label.text() == "Sending…")
    assert card.footer_label.text() == "Sending…"
    gate.set()
    wait_until(lambda: card.footer_label.text() != "Sending…")
    assert lamp.sent == [("profile", "p1")]
    assert lamp.threads[0] is not threading.main_thread()
    assert card.profile_box.currentText() == "Day"

    # What the hub really did, a few seconds later: level and warmth followed.
    hub.devices = [
        make_device(
            "light", "l1", "Lamp", is_on=True, light_level=70, adaptive=("p1", True)
        )
    ]
    wait_until(lambda: len(hub.calls) == fetches + 1)
    wait_until(lambda: connected._refresh_worker is None)
    card = _card_of(connected)
    assert card.profile_box.currentText() == "Day"
    assert card.brightness_slider.value() == 70
    assert len(hub.calls) == fetches + 1  # exactly one follow-up refresh
    assert dialogs == []


def test_failed_activation_shows_the_error_and_schedules_nothing(
    connected: Any, hub: StubHub, wait_until: Wait, fast: None
) -> None:
    lamp = _stub_lamp(fail=True)
    hub.devices = [lamp]
    _refresh(connected, wait_until)
    card = _card_of(connected)
    fetches = len(hub.calls)
    _pick(card, 2)
    wait_until(lambda: "hub said no" in card.footer_label.text())
    assert card.footer_label.text().startswith("Couldn't set adaptive profile")
    assert card.profile_box.currentText() == "Off"
    assert connected._adaptive_refresh_timer.isActive() is False
    assert len(hub.calls) == fetches


def test_off_is_not_sent(connected: Any, hub: StubHub, wait_until: Wait) -> None:
    lamp = _stub_lamp()
    hub.devices = [lamp]
    _refresh(connected, wait_until)
    connected.set_adaptive_profile(_card_of(connected), None)
    assert lamp.sent == []
    assert connected._command_workers == []


def test_level_change_on_an_adaptive_light_schedules_one_refresh(
    connected: Any, hub: StubHub, wait_until: Wait, fast: None
) -> None:
    lamp = _stub_lamp(adaptive=("p1", True))
    hub.devices = [lamp]
    _refresh(connected, wait_until)
    fetches = len(hub.calls)
    connected.set_light_brightness(_card_of(connected), 30)
    wait_until(lambda: len(hub.calls) == fetches + 1)
    wait_until(lambda: connected._refresh_worker is None)
    assert lamp.sent == [("level", 30)]
    assert len(hub.calls) == fetches + 1


def test_level_change_on_a_plain_light_schedules_none(
    connected: Any, hub: StubHub, wait_until: Wait, fast: None, pump: Any
) -> None:
    lamp = _stub_lamp()
    hub.devices = [lamp]
    _refresh(connected, wait_until)
    fetches = len(hub.calls)
    connected.set_light_brightness(_card_of(connected), 30)
    wait_until(lambda: lamp.sent == [("level", 30)])
    wait_until(lambda: not any(w.isRunning() for w in connected._command_workers))
    pump(60)
    assert connected._adaptive_refresh_timer.isActive() is False
    assert len(hub.calls) == fetches
