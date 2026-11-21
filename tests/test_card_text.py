"""Card text: name elision, offline footer, chips, type captions, energy."""

from typing import Any

from conftest import make_device

from widgets.card import DeviceCard


def test_long_name_is_elided_and_keeps_the_card_width(qapp: Any) -> None:
    name = "Living room ceiling lamp " * 8
    card = DeviceCard(make_device("light", name=name, is_on=True, light_level=50))
    card.resize(300, 200)
    card.show()
    qapp.processEvents()
    assert card.width() == 300
    assert card.name_label.text().endswith("…")
    assert len(card.name_label.text()) < len(name)
    assert card.name_label.toolTip() == name
    assert card.full_name == name
    card.hide()


def test_short_name_is_not_elided(qapp: Any) -> None:
    card = DeviceCard(make_device("light", name="Lamp", is_on=True, light_level=50))
    card.resize(300, 200)
    qapp.processEvents()
    assert card.name_label.text() == "Lamp"
