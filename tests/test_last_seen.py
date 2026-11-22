"""An unchanged refresh still ages an offline card's "Last seen" text (t-97)."""

from datetime import datetime, timedelta
from typing import Any

import pytest
from conftest import make_device

import widgets.card


def test_unchanged_refresh_recomputes_last_seen(
    window: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    device = make_device("light", "l1", "Lamp", reachable=False, is_on=True)
    device.last_seen = datetime.now() - timedelta(minutes=5)
    window._on_refreshed([device], [])
    (card,) = window._device_cards.values()
    assert card.footer_label.text().startswith("Last seen")

    monkeypatch.setattr(widgets.card, "relative_time", lambda *_: "much later")
    window._on_refreshed([device], [])  # same data: signature unchanged
    assert card.footer_label.text() == "Last seen much later"
