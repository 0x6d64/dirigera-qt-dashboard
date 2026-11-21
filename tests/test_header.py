"""Window defaults and the responsive header (design-doc.md §4.1, §4.2, §11)."""

from typing import Any


def test_default_window_size(window: Any) -> None:
    assert (window.width(), window.height()) == (1080, 700)
