"""WCAG contrast of the colour pairings in theme.py (t-53, design-doc 5.2).

Add a pairing here when a new token is introduced; the test does not guess.
"""

import pytest

import theme


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


TEXT_PAIRS = [
    ("TEXT", "WINDOW"),
    ("TEXT", "SURFACE"),
    ("TEXT", "SUNKEN"),
    ("TEXT2", "WINDOW"),
    ("TEXT2", "SURFACE"),
    ("TEXT2", "SUNKEN"),
    ("ACCENT", "SURFACE"),
    ("ACCENT", "ACCENT_SOFT"),
    ("ON_ACCENT", "ACCENT"),
    ("ON_ACCENT", "ACCENT_HOVER"),
    ("OK", "OK_BG"),
    ("WARN", "WARN_BG"),
    ("DANGER", "DANGER_BG"),
    ("DANGER", "SURFACE"),
    # PM2.5 band words sit on the card surface (t-88).
    ("OK", "SURFACE"),
    ("WARN", "SURFACE"),
]

# Non-text indicators (switch track, focus ring) need 3:1 against their surface.
NON_TEXT_PAIRS = [("OFF", "SURFACE"), ("ACCENT", "SURFACE")]


@pytest.mark.parametrize("fg, bg", TEXT_PAIRS)
def test_text_contrast(fg: str, bg: str) -> None:
    assert contrast(getattr(theme, fg), getattr(theme, bg)) >= 4.5


@pytest.mark.parametrize("fg, bg", NON_TEXT_PAIRS)
def test_non_text_contrast(fg: str, bg: str) -> None:
    assert contrast(getattr(theme, fg), getattr(theme, bg)) >= 3.0
