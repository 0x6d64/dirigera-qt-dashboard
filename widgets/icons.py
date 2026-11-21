"""
Icon system: inline SVG glyphs rasterised to pixmaps.

Follows design-doc.md §7.3:
- Monoline, 24 px grid, 1.5 px stroke, round caps and joins.
- Rendered from SVG strings in code via `QtSvg` (part of PyQt6), recoloured by
  substituting `currentColor` with a theme token at load time.
- Device-category glyphs are keyed by `device_type` (`"light"`, `"outlet"`,
  `"blinds"`, …), so `render_icon(device.device_type, …)` needs no mapping.
- Scene glyphs are keyed by the hub's scene icon value; common ones are mapped
  in `SCENE_ICONS` and everything else falls back to the generic `"scene"`
  glyph (§7.3.4).
- Battery glyphs are generated per level, 0 to 4 (§7.3.3).

The glyphs are drawn here rather than imported from an icon set, so the open
licensing question in §7.3.5 does not apply.
"""

from typing import Any, Dict

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

# Stroke width on the 24 px grid (design-doc.md §7.3.1).
STROKE = 1.5


def _svg(body: str) -> str:
    """Wrap `body` in a 24 px monoline SVG document drawn in `currentColor`."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="{STROKE}" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>"
    )


ICON_SVG: Dict[str, str] = {
    # ── Device categories, keyed by `device_type` ──────────────────────────
    "light": _svg(
        '<path d="M9.5 18h5M10.5 21h3M12 3a6 6 0 0 0-3.4 10.9V15h6.8v-1.1'
        'A6 6 0 0 0 12 3Z"/>'
    ),
    "outlet": _svg(
        '<rect x="4" y="5" width="16" height="14" rx="3"/>'
        '<path d="M9.5 9.5v3M14.5 9.5v3"/>'
    ),
    "blinds": _svg(
        '<rect x="4" y="4" width="16" height="11" rx="1"/>'
        '<path d="M4 8h16M4 11.5h16M12 15v5"/>'
    ),
    "air_purifier": _svg(
        '<rect x="6" y="3" width="12" height="18" rx="3"/>'
        '<circle cx="12" cy="9.5" r="3"/><path d="M9 16.5h6"/>'
    ),
    "environment_sensor": _svg(
        '<path d="M14 14.8V6a2 2 0 0 0-4 0v8.8a4 4 0 1 0 4 0Z"/>' '<path d="M12 9v6"/>'
    ),
    "electrical_sensor": _svg('<path d="M13 3 5.5 13.5H11l-1 7.5 8-11H12l1-7Z"/>'),
    "sensor": _svg(
        '<circle cx="12" cy="12" r="2"/>'
        '<path d="M8.2 8.2a5.4 5.4 0 0 0 0 7.6M15.8 8.2a5.4 5.4 0 0 1 0 7.6"/>'
    ),
    "motion_sensor": _svg(
        '<path d="M4 15a8 8 0 0 1 16 0"/><path d="M7.5 15a4.5 4.5 0 0 1 9 0"/>'
        '<circle cx="12" cy="18" r="1.6"/>'
    ),
    "open_close_sensor": _svg(
        '<path d="M6 21V4a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v17"/>'
        '<path d="M3.5 21h17"/><circle cx="14" cy="12" r="1"/>'
    ),
    "controller": _svg(
        '<rect x="7" y="2.5" width="10" height="19" rx="3"/>'
        '<circle cx="12" cy="8" r="1.6"/><path d="M9.5 13.5h5M9.5 17h5"/>'
    ),
    # ── Actions and generic scene glyph (§7.3.3) ──────────────────────────
    "scene": _svg(
        '<circle cx="12" cy="12" r="2.5"/>'
        '<path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21'
        "M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M18.4 5.6l-1.8 1.8"
        'M7.4 16.6l-1.8 1.8"/>'
    ),
    "play": _svg('<path d="M8.5 5.5v13L19 12 8.5 5.5Z"/>'),
    "undo": _svg(
        '<path d="M4.5 10.5H14a5 5 0 0 1 0 10H9"/>' '<path d="m8.5 6.5-4 4 4 4"/>'
    ),
    "refresh": _svg('<path d="M20 12a8 8 0 1 1-2.5-5.8"/><path d="M20.5 3.5v5h-5"/>'),
    "settings": _svg(
        '<path d="M4 7h16M4 12h16M4 17h16"/>'
        '<circle cx="9" cy="7" r="2"/><circle cx="15" cy="12" r="2"/>'
        '<circle cx="7.5" cy="17" r="2"/>'
    ),
    # ── Status glyphs (§7.3.3) ────────────────────────────────────────────
    "ok": _svg('<circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.5 2.5 2.5 5-6"/>'),
    "warn": _svg(
        '<path d="M12 4.5 3 20h18L12 4.5Z"/><path d="M12 10v4.5M12 17.2h.01"/>'
    ),
    "danger": _svg(
        '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v5.5M12 16.2h.01"/>'
    ),
    "offline": _svg('<circle cx="12" cy="12" r="8.5"/><path d="m6 6 12 12"/>'),
    "moving": _svg(
        '<path d="M12 3v18"/><path d="m8.5 6.5 3.5-3.5 3.5 3.5"/>'
        '<path d="m8.5 17.5 3.5 3.5 3.5-3.5"/>'
    ),
    # ── Scene glyphs used by SCENE_ICONS ──────────────────────────────────
    "home": _svg(
        '<path d="M4 11 12 4l8 7"/><path d="M6.5 10.2V20h11v-9.8"/>'
        '<path d="M10.5 20v-5h3v5"/>'
    ),
    "sun": _svg(
        '<circle cx="12" cy="12" r="4"/>'
        '<path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2'
        "M5.2 5.2l1.5 1.5M17.3 17.3l1.5 1.5M18.8 5.2l-1.5 1.5"
        'M6.7 17.3l-1.5 1.5"/>'
    ),
    "moon": _svg('<path d="M20 14.2A8.5 8.5 0 0 1 9.8 4a8.5 8.5 0 1 0 10.2 10.2Z"/>'),
    "book": _svg(
        '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M12 4v16"/>'
    ),
    "heart": _svg(
        '<path d="M12 20.2S4.5 15.8 4.5 10.4A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 '
        '7.5 3.2c0 5.4-7.5 9.8-7.5 9.8Z"/>'
    ),
    "music": _svg(
        '<path d="M9.5 17.5V6l9-1.8v11.5"/>'
        '<circle cx="7" cy="17.8" r="2.5"/><circle cx="16" cy="15.7" r="2.5"/>'
    ),
    "movie": _svg(
        '<rect x="3" y="5" width="18" height="14" rx="2"/>'
        '<path d="M8 5v14M16 5v14"/>'
    ),
    "sparkles": _svg(
        '<path d="M11 3.5 12.6 8l4.5 1.6-4.5 1.6L11 15.7 9.4 11.2 4.9 9.6 9.4 8 '
        '11 3.5Z"/>'
        '<path d="m18 14.5.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2Z"/>'
    ),
    "snowflake": _svg(
        '<path d="M12 2.5v19M4.2 7l15.6 10M19.8 7 4.2 17"/>'
        '<path d="m9 4.5 3 2.5 3-2.5M9 19.5l3-2.5 3 2.5"/>'
    ),
    "flame": _svg(
        '<path d="M12 21.5c3.6 0 6-2.4 6-5.8 0-4.4-3.8-6-3.8-9.8-1.9 1-3 '
        "2.7-3 4.6-.9-.5-1.5-1.4-1.7-2.5-1.5 1.5-3.5 3.7-3.5 7.7 0 3.4 2.4 "
        '5.8 6 5.8Z"/>'
    ),
    "leaf": _svg(
        '<path d="M5 19.5c0-7.5 4.8-12.5 14.5-13.5C19.5 15.5 14.5 20 6.5 20'
        'L5 19.5Z"/><path d="M5 20c2-4.2 5.2-7.2 9.5-9"/>'
    ),
    "trophy": _svg(
        '<path d="M8 4h8v4.5a4 4 0 0 1-8 0V4Z"/>'
        '<path d="M8 5.5H5v1.8a3 3 0 0 0 3 3M16 5.5h3v1.8a3 3 0 0 1-3 3"/>'
        '<path d="M12 12.5v4M9 20h6"/>'
    ),
    "headphones": _svg(
        '<path d="M4 15.5v-3a8 8 0 0 1 16 0v3"/>'
        '<rect x="3" y="14" width="4" height="6.5" rx="2"/>'
        '<rect x="17" y="14" width="4" height="6.5" rx="2"/>'
    ),
    "gamepad": _svg(
        '<rect x="2.5" y="7.5" width="19" height="10" rx="5"/>'
        '<path d="M7 10.5v4M5 12.5h4M15.5 11.5h.01M18 14h.01"/>'
    ),
    "coffee": _svg(
        '<path d="M4 8h12v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V8Z"/>'
        '<path d="M16 9.5h1.5a2.5 2.5 0 0 1 0 5H16"/>'
        '<path d="M7.5 3v2.5M11.5 3v2.5"/>'
    ),
    "gift": _svg(
        '<rect x="3" y="9" width="18" height="11.5" rx="1.5"/>'
        '<path d="M3 13.5h18M12 9v11.5"/>'
        '<path d="M12 9C10 9 8 8.2 8 6.3a2.1 2.1 0 0 1 4 0V9Z"/>'
        '<path d="M12 9c2 0 4-.8 4-2.7a2.1 2.1 0 0 0-4 0V9Z"/>'
    ),
    "dumbbell": _svg('<path d="M4 9v6M7 7v10M17 7v10M20 9v6M7 12h10"/>'),
}


def _battery_svg(level: int) -> str:
    """Return a battery glyph filled for `level` (0 to 4 bars)."""
    level = max(0, min(4, level))
    fill = ""
    if level:
        width = round(level * 3.2, 1)
        fill = (
            f'<rect x="4" y="10" width="{width}" height="4" rx="1" '
            'fill="currentColor" stroke="none"/>'
        )
    return _svg(
        f'<rect x="2" y="8" width="17" height="8" rx="2"/>{fill}<path d="M21.5 11v2"/>'
    )


ICON_SVG.update({f"battery-{level}": _battery_svg(level) for level in range(5)})


# Hub scene icon value (see `dirigera.devices.scene.Icon`) -> glyph name.
# Only common values are mapped; the rest use the generic glyph (§7.3.4).
SCENE_ICONS: Dict[str, str] = {
    "scenes_arrive_home": "home",
    "scenes_leave_home": "home",
    "scenes_home_filled": "home",
    "scenes_wake_up": "sun",
    "scenes_sun_horizon": "sun",
    "scenes_brightness_up": "sun",
    "scenes_moon": "moon",
    "scenes_book": "book",
    "scenes_heart": "heart",
    "scenes_music_note": "music",
    "scenes_clapper": "movie",
    "scenes_popcorn": "movie",
    "scenes_clean_sparkles": "sparkles",
    "scenes_disco_ball": "sparkles",
    "scenes_snowflake": "snowflake",
    "scenes_flame": "flame",
    "scenes_leaf": "leaf",
    "scenes_tree": "leaf",
    "scenes_trophy": "trophy",
    "scenes_headphones": "headphones",
    "scenes_game_pad": "gamepad",
    "scenes_hot_drink": "coffee",
    "scenes_gift_box": "gift",
    "scenes_gift_bag": "gift",
    "scenes_weights": "dumbbell",
}


def scene_icon_name(icon: Any) -> str:
    """Map a hub scene icon value to a glyph name, defaulting to `"scene"`."""
    if icon is None:
        return "scene"
    return SCENE_ICONS.get(str(getattr(icon, "value", icon)), "scene")


def render_icon(name: str, color: str, size: int = 24) -> QPixmap:
    """Render glyph `name` in `color` at `size` px; empty pixmap if unknown."""
    svg = ICON_SVG.get(name)
    if svg is None:
        return QPixmap()

    document = QByteArray(svg.replace("currentColor", color).encode("utf-8"))
    renderer = QSvgRenderer(document)
    if not renderer.isValid():
        return QPixmap()

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    return pixmap
