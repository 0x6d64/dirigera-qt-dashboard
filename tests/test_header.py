"""Window defaults and the responsive header (design-doc.md §4.1, §4.2, §11)."""

from typing import Any

import pytest

import dashboard


def test_default_window_size(window: Any) -> None:
    assert (window.width(), window.height()) == (1080, 700)


def _show(window: Any, qapp: Any, width: int, height: int = 700) -> None:
    window.show()
    window.resize(width, height)
    qapp.processEvents()
    qapp.processEvents()


def _is_on_row2(window: Any) -> bool:
    return bool(window.header_row2.isAncestorOf(window.view_switcher))


@pytest.mark.parametrize("width", [1080, 900])
def test_single_row_header_at_wide_widths(window: Any, qapp: Any, width: int) -> None:
    _show(window, qapp, width)
    assert window.header.height() == 56
    assert not window.header_row2.isVisible()
    assert not _is_on_row2(window)
    assert window.view_switcher.isVisible()


@pytest.mark.parametrize("width", [760, 700, 640])
def test_two_row_header_at_narrow_widths(window: Any, qapp: Any, width: int) -> None:
    _show(window, qapp, width)
    assert window.header.height() == 96
    assert window.header_row2.isVisible()
    assert _is_on_row2(window)
    assert window.view_switcher.isVisible()
    # Left-aligned on its own row, below the search field.
    assert window.view_switcher.y() >= 0
    assert window.header_row2.y() >= window.header_row1.height()


def test_switcher_is_the_same_widget_across_modes(window: Any, qapp: Any) -> None:
    switcher = window.view_switcher
    _show(window, qapp, 1080)
    _show(window, qapp, 640)
    _show(window, qapp, 1080)
    assert window.view_switcher is switcher
    assert not _is_on_row2(window)
    assert len(window.view_switcher.buttons()) == 3


def test_window_can_shrink_to_minimum(window: Any, qapp: Any) -> None:
    _show(window, qapp, 640, 480)
    assert window.minimumSizeHint().width() <= 640
    assert window.minimumWidth() == 640
    assert window.minimumHeight() == 480
    window.resize(300, 200)
    qapp.processEvents()
    assert window.width() == 640


def test_single_row_fits_at_the_breakpoint(window: Any, qapp: Any) -> None:
    """The floor must not be narrower than the row at the default font."""
    _show(window, qapp, 1080)
    assert window._header_row_width() <= dashboard.HEADER_BREAKPOINT


def test_wider_row_switches_to_two_rows_earlier(
    window: Any, qapp: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row wider than the floor (larger fonts, scaling) moves the switch point.

    The row width is fixed here: how much a font change widens it depends on
    the platform's font propagation (it did not on the Linux CI runner).
    """
    needed = 1100
    monkeypatch.setattr(window, "_header_row_width", lambda: needed)
    _show(window, qapp, 1000)
    assert 1000 > dashboard.HEADER_BREAKPOINT
    assert window.header.height() == 96
    assert _is_on_row2(window)
    # Wide enough for the bigger row again: one row.
    _show(window, qapp, needed + 20)
    assert window.header.height() == 56
    assert not _is_on_row2(window)
