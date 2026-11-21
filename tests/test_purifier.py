"""Air purifier card: filter health (req-20) and fan speed (req-15)."""

import threading
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import make_device
from dirigera.devices.air_purifier import FanModeEnum

from widgets.card import FAN_MOTOR_STATES, DeviceCard, fan_speed_index
from widgets.text import filter_text

Wait = Callable[..., None]

LIFETIME = 259200  # 180 days, in minutes, as the hub reports it


@pytest.mark.parametrize(
    ("elapsed", "alarm", "expected"),
    [
        (0, False, "Filter 100 % · change in 180 days"),
        (LIFETIME // 2, False, "Filter 50 % · change in 90 days"),
        (LIFETIME - 1440 - 5, False, "Filter 1 % · change in 1 day"),
        (LIFETIME - 300, False, "Filter 0 % · change today"),
        (LIFETIME, True, "Filter used up · change now"),
        (LIFETIME + 100, False, "Filter used up · change now"),
        (LIFETIME, False, "Filter used up · change now"),
        (LIFETIME + 1440, True, "Filter overdue by 1 day · change now"),
        (LIFETIME + 2 * 1440 - 1, True, "Filter overdue by 1 day · change now"),
        # The real hub's purifier (2026-11-21): 353271 minutes elapsed.
        (353271, True, "Filter overdue by 65 days · change now"),
    ],
)
def test_filter_text_states(elapsed: int, alarm: bool, expected: str) -> None:
    assert filter_text(LIFETIME, elapsed, alarm) == expected


def test_alarm_alone_means_used_up() -> None:
    assert filter_text(LIFETIME, 1000, True) == "Filter used up · change now"


@pytest.mark.parametrize(
    ("lifetime", "elapsed"),
    [
        (None, 0),
        (LIFETIME, None),
        (0, 0),
        (-5, 0),
        (1.5, 0),
        ("259200", 0),
        (True, 0),
        (LIFETIME, "10"),
    ],
)
def test_filter_text_is_none_without_usable_numbers(
    lifetime: object, elapsed: object
) -> None:
    assert filter_text(lifetime, elapsed, False) is None


def test_fresh_purifier_footer_and_no_chip() -> None:
    card = DeviceCard(
        make_device(
            "airPurifier",
            filter_lifetime=LIFETIME,
            filter_elapsed_time=0,
            filter_alarm_status=False,
        )
    )
    assert card.footer_label.text() == "Filter 100 % · change in 180 days"
    assert card.status_chip.isHidden()


def test_purifier_without_filter_data_has_no_footer_text() -> None:
    card = DeviceCard(make_device("airPurifier", current_p_m25=5))
    assert card.footer_label.text() == ""
    assert card.status_chip.isHidden()


def test_filter_alarm_shows_warning_chip_and_used_up_footer() -> None:
    card = DeviceCard(
        make_device(
            "airPurifier",
            filter_lifetime=LIFETIME,
            filter_elapsed_time=LIFETIME + 3 * 1440,
            filter_alarm_status=True,
        )
    )
    assert card.status_chip.text() == "Change filter"
    assert not card.status_chip.isHidden()
    assert card.footer_label.text() == "Filter overdue by 3 days · change now"


def test_filter_refresh_clears_the_alarm_chip() -> None:
    card = DeviceCard(
        make_device(
            "airPurifier",
            filter_lifetime=LIFETIME,
            filter_elapsed_time=LIFETIME,
            filter_alarm_status=True,
        )
    )
    card.update_from_device(
        make_device(
            "airPurifier",
            filter_lifetime=LIFETIME,
            filter_elapsed_time=0,
            filter_alarm_status=False,
        )
    )
    assert card.status_chip.isHidden()
    assert card.footer_label.text() == "Filter 100 % · change in 180 days"


# --- fan speed (req-15) -------------------------------------------------------


@pytest.mark.parametrize(
    ("motor_state", "fan_mode", "expected"),
    [
        (0, FanModeEnum.OFF, 0),
        (0, "off", 0),
        (50, "off", 0),  # a stale speed does not beat "off"
        (1, FanModeEnum.AUTO, 1),
        (30, FanModeEnum.AUTO, 1),  # auto reports the speed it picked
        (0, FanModeEnum.AUTO, 1),  # auto wins over a stale 0
        (10, FanModeEnum.LOW, 2),
        (20, FanModeEnum.LOW, 3),
        (30, FanModeEnum.MEDIUM, 4),
        (40, FanModeEnum.MEDIUM, 5),
        (50, FanModeEnum.HIGH, 6),
        (30, None, 4),  # speed known, mode not
        (60, None, 6),  # out of range is clamped to speed 5
        (5, None, 2),  # below 10 is clamped to speed 1
        (None, FanModeEnum.LOW, None),
        (None, None, None),
    ],
)
def test_fan_speed_index(
    motor_state: object, fan_mode: object, expected: object
) -> None:
    assert fan_speed_index(motor_state, fan_mode) == expected


def _purifier(**kw: Any) -> "StubPurifier":
    kw.setdefault("motor_state", 10)
    kw.setdefault("fan_mode", FanModeEnum.LOW)
    return StubPurifier(**kw)


class StubPurifier:
    """A purifier whose `set_motor_state` records its thread and can fail."""

    attributes: Any

    def __init__(self, fail: bool = False, **attrs: Any) -> None:
        base = make_device("airPurifier", **attrs)
        self.__dict__.update(base.__dict__)
        self.capabilities = SimpleNamespace(can_receive=[])
        self.fail = fail
        self.calls: list[int] = []
        self.threads: list[threading.Thread] = []

    def set_motor_state(self, motor_state: int) -> None:
        self.threads.append(threading.current_thread())
        if self.fail:
            raise RuntimeError("hub said no")
        self.calls.append(motor_state)
        self.attributes.motor_state = motor_state

    def reload(self) -> "StubPurifier":
        return self


def test_fan_control_has_seven_segments_and_an_accessible_name() -> None:
    card = DeviceCard(make_device("airPurifier", motor_state=0, fan_mode="off"))
    assert [b.text() for b in card.fan_speed.buttons()] == [
        "Off",
        "Auto",
        "1",
        "2",
        "3",
        "4",
        "5",
    ]
    assert card.fan_speed.accessibleName() == f"{card.full_name} fan speed"
    assert card.fan_speed.current_index() == 0


def test_each_segment_sends_its_motor_state() -> None:
    sent: list[int] = []
    card = DeviceCard(
        make_device("airPurifier", motor_state=0, fan_mode="off"),
        on_fan_speed=lambda _card, state: sent.append(state),
    )
    for index in range(len(FAN_MOTOR_STATES)):
        card.fan_speed.button(index).click()
    assert sent == list(FAN_MOTOR_STATES)


def test_fan_control_hidden_without_a_fan_setting() -> None:
    card = DeviceCard(make_device("airPurifier", current_p_m25=4))
    assert card._fan_box is not None and card._fan_box.isHidden()


def test_refresh_moves_the_selection_without_a_command(window: Any) -> None:
    purifier = _purifier(motor_state=10)
    card = window.create_device_widget(purifier)
    card.show()
    assert card.fan_speed.current_index() == 2
    card.update_from_device(_purifier(motor_state=50, fan_mode=FanModeEnum.HIGH))
    assert card.fan_speed.current_index() == 6
    assert purifier.calls == []


def test_fan_command_runs_off_the_gui_thread(window: Any, wait_until: Wait) -> None:
    purifier = _purifier(motor_state=10)
    card = window.create_device_widget(purifier)
    card.show()
    card.fan_speed.button(4).click()  # speed 3
    wait_until(lambda: purifier.calls == [30])
    assert purifier.threads[0] is not threading.main_thread()
    wait_until(lambda: card.fan_speed.current_index() == 4)
    assert purifier.attributes.fan_mode is FanModeEnum.MEDIUM


def test_failed_fan_command_resyncs_and_shows_the_error(
    window: Any, wait_until: Wait
) -> None:
    purifier = _purifier(motor_state=10, fail=True)
    card = window.create_device_widget(purifier)
    card.show()
    card.fan_speed.button(0).click()  # Off
    wait_until(lambda: "hub said no" in card.footer_label.text())
    assert card.fan_speed.current_index() == 2
    assert purifier.calls == []
