"""Light colour temperature controls (t-14)."""

import threading
from collections.abc import Callable
from typing import Any

import pytest
from conftest import StubLight
from PyQt6.QtWidgets import QApplication

from widgets.card import kelvin_bounds

Wait = Callable[..., None]

TEMP = ["colorTemperature"]


def _lamp(**kw: Any) -> StubLight:
    kw.setdefault("color_temperature", 3000)
    kw.setdefault("color_temperature_min", 2200)
    kw.setdefault("color_temperature_max", 4000)
    return StubLight(can_receive=kw.pop("can_receive", TEMP), **kw)


def _card(win: Any, lamp: StubLight) -> Any:
    card = win.create_device_widget(lamp)
    card.show()
    return card


def test_warmth_slider_needs_the_capability(window: Any) -> None:
    assert hasattr(_card(window, _lamp()), "temperature_slider")
    assert not hasattr(_card(window, _lamp(can_receive=[])), "temperature_slider")
    assert not hasattr(
        _card(window, _lamp(color_temperature_min=None)), "temperature_slider"
    )


def test_slider_range_and_value_follow_the_light(window: Any) -> None:
    slider = _card(window, _lamp()).temperature_slider
    assert (slider._slider.minimum(), slider._slider.maximum()) == (2200, 4000)
    assert slider.value() == 3000


def test_mired_bounds_are_converted_and_ordered() -> None:
    attrs = _lamp(color_temperature_min=153, color_temperature_max=454).attributes
    # 153 mired is the cool end (6536 K), 454 mired the warm end (2203 K).
    assert kelvin_bounds(attrs) == (2203, 6536)


def test_commit_sets_temperature_off_the_gui_thread(
    window: Any, wait_until: Wait
) -> None:
    lamp = _lamp()
    card = _card(window, lamp)
    card.temperature_slider._slider.setValue(2700)
    card.temperature_slider._commit()
    wait_until(lambda: lamp.attributes.color_temperature == 2700)
    assert lamp.threads[0] is not threading.main_thread()
    wait_until(lambda: card.temperature_slider.value() == 2700)


def test_failed_commit_resyncs_the_slider(
    qapp: QApplication, window: Any, wait_until: Wait
) -> None:
    lamp = _lamp(fail=True)
    card = _card(window, lamp)
    card.temperature_slider._slider.setValue(2700)
    card.temperature_slider._commit()
    wait_until(lambda: "hub said no" in card.footer_label.text())
    assert card.temperature_slider.value() == 3000


def test_refresh_updates_the_slider(window: Any) -> None:
    card = _card(window, _lamp())
    card.update_from_device(_lamp(color_temperature=3600))
    assert card.temperature_slider.value() == 3600


@pytest.mark.parametrize("unknown", [None])
def test_light_without_a_reading_still_builds(window: Any, unknown: Any) -> None:
    card = _card(window, _lamp(color_temperature=unknown))
    assert card.temperature_slider.value() == 2200


# --- hue and saturation (second commit) --------------------------------------

COLOUR = ["colorHue", "colorSaturation"]


def _colour_lamp(**kw: Any) -> StubLight:
    kw.setdefault("color_hue", 120.0)
    kw.setdefault("color_saturation", 0.5)
    return StubLight(can_receive=kw.pop("can_receive", COLOUR), **kw)


def test_colour_controls_need_both_capabilities(window: Any) -> None:
    assert hasattr(_card(window, _colour_lamp()), "colour_button")
    for partial in (["colorHue"], ["colorSaturation"], []):
        card = _card(window, _colour_lamp(can_receive=partial))
        assert not hasattr(card, "colour_button")
        assert not hasattr(card, "hue_slider")


def test_colour_controls_are_hidden_until_the_button_is_pressed(window: Any) -> None:
    card = _card(window, _colour_lamp())
    assert card.colour_box.isHidden()
    card.colour_button.click()
    assert not card.colour_box.isHidden()
    assert card.hue_slider.value() == 120
    assert card.saturation_slider.value() == 50
    card.colour_button.click()
    assert card.colour_box.isHidden()


def test_commit_sends_both_values_scaled(window: Any, wait_until: Wait) -> None:
    lamp = _colour_lamp()
    card = _card(window, lamp)
    card.saturation_slider._slider.setValue(80)
    card.saturation_slider._commit()
    wait_until(lambda: lamp.colour_calls == [(120.0, 0.8)])
    assert lamp.threads[0] is not threading.main_thread()
    wait_until(lambda: not card.is_pending)  # one command at a time
    card.hue_slider._slider.setValue(300)
    card.hue_slider._commit()
    wait_until(lambda: lamp.colour_calls[-1] == (300.0, 0.8))


def test_refresh_updates_colour_sliders(window: Any) -> None:
    card = _card(window, _colour_lamp())
    card.update_from_device(_colour_lamp(color_hue=240.0, color_saturation=1.0))
    assert (card.hue_slider.value(), card.saturation_slider.value()) == (240, 100)
