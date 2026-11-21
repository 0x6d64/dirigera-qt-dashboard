"""Air purifier card: filter health (req-20) and fan speed (req-15)."""

import pytest
from conftest import make_device

from widgets.card import DeviceCard
from widgets.text import filter_text

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
            filter_elapsed_time=LIFETIME + 10,
            filter_alarm_status=True,
        )
    )
    assert card.status_chip.text() == "Change filter"
    assert not card.status_chip.isHidden()
    assert card.footer_label.text() == "Filter used up · change now"


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
