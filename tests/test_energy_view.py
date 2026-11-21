"""Energy view: room grouping, live power, in-place refresh, empty state."""

from typing import Any

from conftest import make_device
from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QLabel

from widgets.energy import EnergyView


def _outlet(
    id_: str, name: str, room: tuple[str, str] | None, power: float | None, **kw: Any
) -> Any:
    return make_device(
        "outlet",
        id_,
        name=name,
        room=room,
        is_on=True,
        current_active_power=power,
        **kw,
    )


def _section_labels(view: EnergyView) -> list[str]:
    return [
        label.text()
        for label in view.content.findChildren(QLabel)
        if label.property("role") == "section"
    ]


def test_rooms_are_grouped_and_sorted_in_the_window(window: Any) -> None:
    window._on_refreshed(
        [
            _outlet("a", "Kettle", ("2", "kitchen"), 5.0),
            _outlet("b", "Lamp", ("1", "attic"), 1.0),
            _outlet("c", "Toaster", ("2", "kitchen"), 2.0),
            make_device("light", "l", name="Not metered"),
        ],
        [],
    )
    view = window.energy_view
    assert _section_labels(view) == ["Attic", "Kitchen"]
    names = sorted(card.full_name for card in view.cards())
    assert names == ["Kettle", "Lamp", "Toaster"]


def test_metering_device_shows_its_power(qapp: Any) -> None:
    view = EnergyView()
    view.set_rooms([("Kitchen", [_outlet("a", "Kettle", None, 12.5)])])
    (card,) = view.cards()
    assert card.is_metered
    assert card.power_metric is not None
    assert card.power_metric.value_text == "12.5"
    assert card.power_metric.unit_text == "W"


def test_device_without_metering_says_so(qapp: Any) -> None:
    view = EnergyView()
    view.set_rooms([("Kitchen", [_outlet("a", "Plug", None, None)])])
    (card,) = view.cards()
    assert not card.is_metered
    assert card.footer_label.text() == "No energy data"


def test_refresh_with_new_power_updates_the_same_card(qapp: Any) -> None:
    view = EnergyView()
    rooms = [("Kitchen", [_outlet("a", "Kettle", None, 10.0)])]
    view.update_rooms(rooms)
    (card,) = view.cards()

    view.update_rooms([("Kitchen", [_outlet("a", "Kettle", None, 42.0)])])

    (after,) = view.cards()
    assert after is card
    assert card.power_metric is not None
    assert card.power_metric.value_text == "42"


def test_card_is_rebuilt_when_metering_appears(qapp: Any) -> None:
    view = EnergyView()
    view.update_rooms([("Kitchen", [_outlet("a", "Plug", None, None)])])
    assert not view.cards()[0].is_metered
    view.update_rooms([("Kitchen", [_outlet("a", "Plug", None, 3.0)])])
    # The replaced card is deleted on the next event-loop turn.
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    (after,) = view.cards()
    assert after.is_metered


def test_empty_energy_view_shows_its_empty_state(qapp: Any) -> None:
    view = EnergyView()
    view.show()
    view.set_rooms([])
    assert view.empty_label.isVisible()
    assert view.empty_label.text() == "No energy data"
    assert not view.scroll_area.isVisible()
    assert view.cards() == []

    view.set_rooms([("Kitchen", [_outlet("a", "Kettle", None, 1.0)])])
    assert not view.empty_label.isVisible()
    assert view.scroll_area.isVisible()
    view.hide()


def test_view_price_reaches_new_and_existing_cards(qapp: Any) -> None:
    view = EnergyView()
    view.set_price(1.0, "EUR")
    view.set_rooms(
        [("Kitchen", [_outlet("a", "Kettle", None, 1.0, total_energy_consumed=2.0)])]
    )
    (card,) = view.cards()
    assert card.usage_label.text() == "Usage 2.00 kWh · 2.00 EUR"

    view.set_price(2.0, "EUR")
    assert card.usage_label.text() == "Usage 2.00 kWh · 4.00 EUR"
