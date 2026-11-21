"""
Design tokens and QSS stylesheet generator for the Dirigera Qt Dashboard.

All colour values, spacing constants, font sizes, and radii are defined here.
No other module should hard-code colours or spacing — import from this module
instead, and use generate_stylesheet() to apply the design to the application.

Colour tokens follow design-doc.md §5.1 (light theme only).
Spacing follows design-doc.md §4.4.
Typography follows design-doc.md §6.2.
Shape radii follow design-doc.md §7.1.
"""

from typing import Optional

# ---------------------------------------------------------------------------
# Colour tokens (light theme)
# ---------------------------------------------------------------------------

# Backgrounds
WINDOW = "#F4F5F7"  # Window background
SURFACE = "#FFFFFF"  # Cards, header, content areas
SUNKEN = "#ECEEF1"  # Slider tracks, offline cards, search field, hover

# Borders
BORDER = "#D5D9E0"  # Card and header outlines (decorative, not text)

# Text
TEXT = "#1A1D23"  # Primary text
TEXT2 = "#505968"  # Captions, units, types, labels

# Accent / interactive
ACCENT = "#1F5FD1"  # On-state, primary action, focus ring, slider fill
ACCENT_HOVER = "#1A50B3"  # Primary button hover
ON_ACCENT = "#FFFFFF"  # Text on accent background
ACCENT_SOFT = "#E6EEFC"  # Selected segment, selected room chip

# Off-state
OFF = "#7C8696"  # Switch track when off

# Colour-temperature slider track: warm (low Kelvin) to cool (high Kelvin).
# Decorative, so not part of the text contrast pairings.
TEMP_WARM = "#FFB45E"
TEMP_COOL = "#BDD9FF"

# Status: ok
OK = "#17753A"  # Ok chip text
OK_BG = "#E3F4EA"  # Ok chip background

# Status: warn
WARN = "#8F4A00"  # Warning chip text
WARN_BG = "#FBE9D7"  # Warning chip background

# Status: danger
DANGER = "#B3261E"  # Danger chip text, error text
DANGER_BG = "#FBE4E2"  # Danger chip background

# Room colours (req-22, t-86): best-guess RGB per hue word in the hub's colour
# names (e.g. "ikea_green_no_65"). They mark the room only (a dot and a card
# edge), never text or state, so each one is a mid tone that reaches 3:1
# against WINDOW and SURFACE (non-text contrast, design-doc.md §5.2).
ROOM_COLOURS: dict[str, str] = {
    "red": "#C62828",
    "orange": "#B85C00",
    "yellow": "#9A7400",
    "green": "#2E7D32",
    "turquoise": "#00808A",
    "blue": "#1565C0",
    "purple": "#6A1B9A",
    "lilac": "#7E57C2",
    "pink": "#C2185B",
    "beige": "#A38457",
    "brown": "#6D4C41",
    "grey": "#6B7280",
}


def room_colour(name: Optional[str]) -> Optional[str]:
    """Return the marker colour for a hub colour name, or None if unknown.

    The first part of the name (split on "_") that is a known hue word wins,
    so "ikea_green_no_65" maps to green. None, empty and unknown names stay
    neutral (None).
    """
    if not name:
        return None
    for part in name.lower().split("_"):
        if part in ROOM_COLOURS:
            return ROOM_COLOURS[part]
    return None


# ---------------------------------------------------------------------------
# Spacing scale (base unit 4 px — design-doc.md §4.4)
# ---------------------------------------------------------------------------

SP4 = 4
SP8 = 8
SP12 = 12
SP16 = 16
SP20 = 20
SP24 = 24

# ---------------------------------------------------------------------------
# Shape radii (design-doc.md §7.1)
# ---------------------------------------------------------------------------

RADIUS_CARD = 10  # Device and scene cards
RADIUS_BUTTON = 6  # Buttons, search field, segment group
RADIUS_CHIP = 9  # Chips (fully rounded for 18 px height)

# ---------------------------------------------------------------------------
# Typography (design-doc.md §6.2)
# ---------------------------------------------------------------------------

FONT_METRIC = 28  # Key sensor readings
FONT_APP_TITLE = 18  # Header title
FONT_TITLE = 16  # Card names
FONT_BODY = 14  # Controls and values
FONT_LABEL = 13  # Section labels, slider labels
FONT_CAPTION = 12  # Types, units, footers, chips


# ---------------------------------------------------------------------------
# Stylesheet generator
# ---------------------------------------------------------------------------


def generate_stylesheet() -> str:
    """Return a QSS string applying design tokens to common Qt widgets.

    Call this once and pass the result to QApplication.setStyleSheet().
    Individual widgets may apply additional token-derived QSS for states
    (selected, disabled, hover) using unpolish/polish after changing a
    dynamic property.
    """
    return f"""
/* ── Window & base background ─────────────────────────────────────── */
QMainWindow, QDialog {{
    background-color: {WINDOW};
}}

QWidget {{
    background-color: {WINDOW};
    color: {TEXT};
    font-size: {FONT_BODY}px;
    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
}}

/* ── Cards and panels (surface colour) ─────────────────────────────── */
QFrame[frameShape="1"],
QGroupBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
}}

QGroupBox::title {{
    color: {TEXT2};
    font-size: {FONT_LABEL}px;
    font-weight: 500;
    padding: 0 {SP4}px;
}}

/* ── Scroll areas ───────────────────────────────────────────────────── */
QScrollArea {{
    background-color: {WINDOW};
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: {WINDOW};
}}

QScrollBar:vertical {{
    background: {SUNKEN};
    width: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* ── Labels ─────────────────────────────────────────────────────────── */
QLabel {{
    background-color: transparent;
    color: {TEXT};
}}

/* Section label above each room's card grid (design-doc.md §8.9) */
QLabel[role="section"] {{
    background-color: transparent;
    color: {TEXT2};
    font-size: {FONT_LABEL}px;
    font-weight: 500;
}}

/* ── Header bar (design-doc.md §4.2) ────────────────────────────────── */
QWidget[role="header"] {{
    background-color: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}

QLabel[role="appTitle"] {{
    background-color: transparent;
    color: {TEXT};
    font-size: {FONT_APP_TITLE}px;
    font-weight: 600;
}}

/* Caption line under the header (status details, "showing data from…") */
QLabel[role="caption"] {{
    background-color: transparent;
    color: {TEXT2};
    font-size: {FONT_CAPTION}px;
}}

QLabel[role="caption"][tone="ok"] {{
    color: {OK};
}}

QLabel[role="caption"][tone="danger"] {{
    color: {DANGER};
}}

QLabel[role="caption"][tone="warn"] {{
    color: {WARN};
}}

/* ── Connection block (design-doc.md §8.12) ─────────────────────────── */
QFrame[role="connectionCard"] {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
}}

QLabel[role="cardTitle"] {{
    background-color: transparent;
    color: {TEXT};
    font-size: {FONT_TITLE}px;
    font-weight: 600;
}}

/* ── Line edits / search field ──────────────────────────────────────── */
QLineEdit {{
    background-color: {SUNKEN};
    color: {TEXT};
    border: 1px solid transparent;
    border-radius: {RADIUS_BUTTON}px;
    padding: {SP4}px {SP8}px;
    font-size: {FONT_BODY}px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
}}

QLineEdit:focus {{
    background-color: {SURFACE};
    border: 1px solid {ACCENT};
}}

QLineEdit:disabled {{
    color: {TEXT2};
    background-color: {SUNKEN};
}}

/* ── Buttons ────────────────────────────────────────────────────────── */

/* Primary button */
QPushButton[buttonVariant="primary"] {{
    background-color: {ACCENT};
    color: {ON_ACCENT};
    border: none;
    border-radius: {RADIUS_BUTTON}px;
    padding: 7px 16px;
    font-size: {FONT_BODY}px;
    font-weight: 600;
}}

QPushButton[buttonVariant="primary"]:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton[buttonVariant="primary"]:disabled {{
    background-color: #C9CFDA;
    color: {TEXT2};
}}

/* Ghost button (default) */
QPushButton {{
    background-color: transparent;
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_BUTTON}px;
    padding: 7px 16px;
    font-size: {FONT_BODY}px;
}}

QPushButton:hover {{
    background-color: {SUNKEN};
}}

QPushButton:disabled {{
    color: {TEXT2};
    border-color: {BORDER};
}}

QPushButton:pressed {{
    background-color: {BORDER};
}}

/* ── Segmented control (design-doc.md §8.6) ─────────────────────────── */
QFrame[role="segmented"] {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_BUTTON}px;
}}

QPushButton[segment="true"] {{
    background-color: transparent;
    color: {TEXT};
    border: 1px solid transparent;
    border-radius: 0;
    padding: 6px 12px;
    font-size: {FONT_BODY}px;
}}

QPushButton[segment="true"]:hover {{
    background-color: {SUNKEN};
}}

QPushButton[segment="true"]:disabled {{
    color: {TEXT2};
    border-color: transparent;
}}

QPushButton[segment="true"][selected="true"] {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT};
    border: 1px solid {ACCENT};
    font-weight: 600;
}}

/* Only the outer corners are rounded; inner corners stay square. */
QPushButton[segment="true"][first="true"] {{
    border-top-left-radius: 5px;
    border-bottom-left-radius: 5px;
}}

QPushButton[segment="true"][last="true"] {{
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}}

/* ── Sliders ────────────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    height: 6px;
    background-color: {SUNKEN};
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background-color: {ACCENT};
    border-radius: 3px;
}}

/* NOTE: Do NOT add QSlider:disabled::sub-page — it paints the whole
   groove grey under the Fusion style (doc/qt-gotchas.md item 4). */

QSlider::handle:horizontal {{
    width: 18px;
    height: 18px;
    margin: -6px 0;
    background-color: {SURFACE};
    border: 2px solid {ACCENT};
    border-radius: 9px;
}}

QSlider::handle:horizontal:disabled {{
    border-color: {OFF};
}}

/* ── Progress bars ──────────────────────────────────────────────────── */
QProgressBar {{
    background-color: {SUNKEN};
    border: none;
    border-radius: 3px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 3px;
}}

/* ── Tab widget ─────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: {RADIUS_BUTTON}px;
    background-color: {SURFACE};
}}

QTabBar::tab {{
    background-color: {SUNKEN};
    color: {TEXT2};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-radius: {RADIUS_BUTTON}px {RADIUS_BUTTON}px 0 0;
    padding: {SP8}px {SP16}px;
    font-size: {FONT_BODY}px;
}}

QTabBar::tab:selected {{
    background-color: {SURFACE};
    color: {TEXT};
}}

QTabBar::tab:hover {{
    background-color: {BORDER};
}}

/* ── Message / dialog boxes ─────────────────────────────────────────── */
QMessageBox {{
    background-color: {SURFACE};
}}

/* ── Combo boxes ────────────────────────────────────────────────────── */
QComboBox {{
    background-color: {SUNKEN};
    color: {TEXT};
    border: 1px solid transparent;
    border-radius: {RADIUS_BUTTON}px;
    padding: {SP4}px {SP8}px;
    font-size: {FONT_BODY}px;
}}

QComboBox:focus {{
    border: 1px solid {ACCENT};
    background-color: {SURFACE};
}}

QComboBox::drop-down {{
    border: none;
    width: {SP20}px;
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
}}
"""
