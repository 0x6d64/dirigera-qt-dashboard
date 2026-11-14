# Qt widget mapping and Dirigera API exposure

Reference for an implementer (human or LLM) who will build the dashboard UI.
Standalone document: it changes no project file and defines no `req-` or `t-` IDs.
Where it cites existing IDs (`req-3`, `t-16`, …) they were read from `doc/reqs.md`
and `agent-notes/todo.md` in the uploaded archive.

## 0. Provenance and limits

Every non-obvious claim carries a tag:

| Tag | Meaning |
| --- | --- |
| `[lib]` | Read in the installed `dirigera` 1.6.1 source or its bundled README |
| `[qt]` | Checked in a sandbox with PyQt 6.12.1 / Qt 6.12.0 (offscreen platform) |
| `[code]` | Seen in the uploaded `dashboard.py` |
| `[shot]` | Visible in the screenshot of the current UI |
| `[known]` | General Qt knowledge, not re-tested here |
| `[unverified]` | Needs a look at real hub data or real hardware |
| `[opinion]` | Design judgment, open to challenge |

Limits you should know about:

1. There was no live hub. Nothing below was observed on real device payloads.
   Section 6 gives a read-only way to dump them; do that before trusting any
   `[unverified]` item.
2. Qt checks ran on Linux with the `offscreen` platform. The screenshot shows
   Windows, so fonts, DPI and the native style can differ. Re-check on Windows.
3. The prototypes lived in `/tmp` and are not part of the project. Only the
   verified switch snippet in Appendix A is reproduced here.

## 1. Findings that change the implementation

Ordered by impact.

1. **Render controls from `capabilities.can_receive`, not from "attribute is not
   None".** `[lib]` Setters raise `AssertionError` when the capability is absent
   and `ValueError` when out of range. The current code decides on
   `light_level is not None` `[code]`, which is a proxy and will drift. Guard
   names seen in the library: `customName`, `isOn`, `lightLevel`,
   `colorTemperature`, `colorHue`, `colorSaturation`, `blindsTargetLevel`,
   `blindsState`, `childLock`. The air purifier's `set_fan_mode`,
   `set_motor_state` and `set_status_light` have no guard in the library, so their
   capability names are `[unverified]`.
2. **A refresh is 12 sequential `GET /devices` calls plus the scenes call.** `[lib]`
   `get_all_devices()` runs one `get_*()` per device class, and each of the 12
   re-fetches `/devices`. Every request has a 10 s timeout. None of them isolates a
   single device that fails pydantic validation, so one odd device fails the whole
   refresh. The library README confirms this can happen ("reports data that the
   library doesn't expect yet"). Measure latency on the real hub before optimizing
   `[unverified]`; relevant to `t-17`, `t-19`, `req-2`.
3. **Plugs with metering can split into two devices.** `[lib]` Some plugs (the README
   names GRILLPLATS) report energy as a separate `electricalSensor` that shares the
   outlet's `relation_id`. Merge it into the outlet card by `relation_id`; do not
   render a second tile. Other plugs (INSPELNING) carry the energy attributes on the
   outlet itself. `[shot]` "Plug 3 (metering)" is a plain outlet there; which of the
   two cases it is `[unverified]`.
4. **Controllers have no press state.** `[lib]` Button presses are not stored as
   device state. A remote tile can show name, battery and reachability, nothing
   interactive. The current ✓ `[code]` is a generic fallback branch for every type
   except `light`, `blinds` and `outlet`; it means "no handler", not "healthy".
5. **Live updates are partial and the listener blocks.** `[lib]`
   `create_event_listener()` calls `run_forever` and returns only when the socket
   closes. The hub closes idle connections itself. Events carry `type` and
   `data.id` plus only the changed attributes (README example: `{'isOn': False}`).
   Events during a reconnect are lost, so refetch state after reconnecting. This is
   `t-16`; design the state layer for it now (section 5).
6. **The shared `requests.Session` is not documented as thread-safe.** `[lib]` The
   hub object uses one session for all calls. Running slider commands, refreshes and
   the listener concurrently on one `Hub` is a risk `[unverified]`. Serialize hub
   calls through one worker or use one `Hub` per thread (`req-4` already forbids GUI
   thread I/O).
7. **Several displayed values have no documented unit or meaning.** `[lib]` See
   section 6, items 1 to 6. Do not invent labels for them.
8. **Qt gaps.** `[qt]` Qt Widgets has no native toggle switch. There is no
   `QSegmentedControl`. `QtCharts` is not in the base `PyQt6` wheel (it is a
   separate package). There is also no built-in flow layout `[known]`.
9. **Qt Quick Controls 2 is available and ships a native `Switch`.** `[qt]` The wheel
   contains the Basic, Fusion, Material, Universal, Imagine and FluentWinUI3 styles
   and `QtQml`, `QtQuick`, `QtQuickWidgets` import. QML is a real option, not a
   hypothetical one (section 4.1).

## 2. What the dirigera API exposes

### 2.1 Hub methods (public surface of `Hub`) `[lib]`

| # | Group | Methods |
| --- | --- | --- |
| 1 | Bulk fetch | `get_all_devices()`, `get_scenes()`, `get_adaptive_profiles()` |
| 2 | Typed fetch (each has `_by_id` / `_by_name`) | `get_lights`, `get_outlets`, `get_electrical_sensors`, `get_blinds`, `get_air_purifiers`, `get_controllers`, `get_environment_sensors`, `get_motion_sensors`, `get_light_sensors`, `get_occupancy_sensors`, `get_open_close_sensors`, `get_water_sensors`, `get_scene_by_id/name` |
| 3 | Scenes | `create_scene`, `delete_scene` (plus `Scene.trigger/undo`) |
| 4 | Events | `create_event_listener(on_open, on_message, on_error, on_close, ping_intervall, reconnect, …)`, `stop_event_listener()` |
| 5 | Raw access | `get(route)`, `patch(route, data)`, `post`, `delete`, `headers()` |

Not exposed as methods: a room list, hub status or firmware info, users, groups,
history of any kind. Raw `get()` can reach whatever the hub serves, but those
routes are undocumented in the library `[unverified]`. Rooms only appear as
`device.room`.

### 2.2 Fields on every device `[lib]`

| # | Field | Notes |
| --- | --- | --- |
| 1 | `id`, `relation_id` | `relation_id` links sibling devices (plug and its electrical sensor) |
| 2 | `type`, `device_type` | `type` is coarse (`controller`), `device_type` is fine (`lightController`) |
| 3 | `is_reachable` | Use for the offline state; reliability on battery devices `[unverified]` |
| 4 | `last_seen`, `created_at` | Datetimes |
| 5 | `room` | Optional `Room(id, name, color, icon)`; value formats of `color` and `icon` `[unverified]` |
| 6 | `is_hidden` | Optional bool; whether the IKEA app hides these `[unverified]` |
| 7 | `capabilities` | `can_send`, `can_receive` (lists of camelCase attribute names) |
| 8 | `device_set`, `remote_links` | Untyped lists; meaning `[unverified]` |
| 9 | `attributes` (common) | `custom_name`, `model`, `manufacturer`, `firmware_version`, `hardware_version`, optional `serial_number`, `product_code`, `ota_*` |

### 2.3 Per type: readable attributes and setters `[lib]`

`get_all_devices()` returns exactly these 12 classes, so unknown types cannot occur
through it in 1.6.1; keep a fallback anyway.

| # | `device_type` | Readable attributes (units where documented) | Setters (all have `set_name`, `reload`) |
| --- | --- | --- | --- |
| 1 | `light` | `is_on`, `light_level` (1 to 100), `color_temperature`, `color_temperature_min/max`, `color_hue` (0 to 360), `color_saturation` (0.0 to 1.0), `color_mode`, `startup_on_off`; plus `light.adaptive_profile` (`id`, `active`) | `set_light(bool)`, `set_light_level(1..100)`, `set_color_temperature(K)`, `set_light_color(hue, sat)`, `set_startup_behaviour`, `activate_adaptive_profile(id)` |
| 2 | `outlet` | `is_on`, `startup_on_off`, `status_light`, and (metering plugs only) `current_active_power` W, `current_amps` A, `current_voltage` V, `total_energy_consumed` kWh, counter/reset timestamps | `set_on(bool)`, `set_startup_behaviour` |
| 3 | `electricalSensor` | Same energy attributes as outlet; read-only | none besides name |
| 4 | `blinds` | `blinds_current_level` 0 to 100, `blinds_target_level` 0 to 100, `blinds_state` (`up`/`down`/`stopped`), `battery_percentage` | `set_target_level(0..100)`, `set_state(BlindsStateEnum)` |
| 5 | `airPurifier` | `fan_mode` (`off,on,low,medium,high,auto`), `motor_state` 0 to 50, `current_p_m25`, `child_lock`, `status_light`, `filter_alarm_status`, `filter_elapsed_time`, `filter_lifetime`, `motor_runtime`, `fan_mode_sequence` | `set_fan_mode`, `set_motor_state`, `set_child_lock`, `set_status_light` |
| 6 | `*Controller` (`lightController`, `shortcutController`, …) | `battery_percentage`, `is_on`, `switch_label` | none besides name |
| 7 | `environmentSensor` | `current_temperature` °C, `current_r_h` %, `current_p_m25`, `max/min_measured_p_m25`, `voc_index` (VINDSTYRKA only), `current_c_o2` ppm (ALPSTUGA only), `battery_percentage` | none |
| 8 | `motionSensor` | `is_detected`, `is_on` (None on some), `light_level`, `battery_percentage` | none |
| 9 | `lightSensor` | `illuminance`, `min/max_illuminance`, `battery_percentage` | none |
| 10 | `occupancySensor` | `is_detected`, `battery_percentage` | none |
| 11 | `openCloseSensor` | `is_open`, `battery_percentage` | none |
| 12 | `waterSensor` | `water_leak_detected`, `battery_percentage` | none |

Light colour temperature quirk `[lib]`: some bulbs (KAJPLATS) report the min/max
bounds in mireds (153 to 454) while the value itself is in Kelvin; the library
normalizes with a private helper `_bound_to_kelvin` and validates against
`min()`/`max()` of the converted bounds. Replicate that logic rather than trusting
`min < max`.

### 2.4 Scenes `[lib]`

| # | Field | Use in UI |
| --- | --- | --- |
| 1 | `info.name`, `info.icon` | Title and glyph; `Icon` enum has 38 values (`scenes_*`), so you need a mapping with a generic fallback |
| 2 | `type` | `userScene`, `customScene`, `playlistScene`, `wakeUpScene`; whether to show non-user scenes `[opinion]` |
| 3 | `triggers[]` | `type`, `disabled`, `next_trigger_at`, `triggered_at`; enough for "next run" labels |
| 4 | `actions[]` | `id` (device), `type`, `enabled`, `attributes.is_on`; enough for "affects N devices" |
| 5 | `last_triggered`, `last_completed`, `last_undo`, `created_at` | Datetimes (the `Scene` model; the older `SceneAttributes` class types them as str, ignore it) |
| 6 | `undo_allowed_duration` | Unit undocumented (README: "shortly afterwards") `[unverified]` |
| 7 | `trigger()`, `undo()` | Activate; Undo within the allowed window |

### 2.5 Adaptive lighting `[lib]`

`get_adaptive_profiles()` returns `AdaptiveProfile(id, name, adaptive_schedule[])`
with entries `start_time "HH:MM"`, `light_level`, `color_temperature`. Profiles are
created in the IKEA app only. Setting a light manually takes it out of adaptive
mode; `reload()` to see the state.

### 2.6 Events `[lib]`

| # | Item | Status |
| --- | --- | --- |
| 1 | Types documented | `deviceStateChanged`, `sceneCreated`, `sceneUpdated`, `sceneDeleted` |
| 2 | Payload | JSON string; `data.id`, and for state changes `data.attributes` with only changed camelCase keys |
| 3 | Device added/removed events, reachability-change events | Not documented `[unverified]` |
| 4 | Button-press event shape | Not documented; README only says to use events or a controller-trigger scene `[unverified]` |
| 5 | Delivery | Blocking call; callbacks run on the worker thread `[known]`, so never touch widgets from them |

### 2.7 Not available at all

History (power, temperature, motion), "last motion" time, button presses as state,
hub health. Anything shown over time must be sampled in memory by the app and is
lost on exit. That makes sparklines a live-updates feature, not a launch feature.

## 3. Qt building blocks that fit this app

Classes below were confirmed to exist in PyQt 6.12.1 `[qt]` unless tagged otherwise.

| # | Need | Qt class(es) | Note |
| --- | --- | --- | --- |
| 1 | App shell | `QMainWindow`, `QToolBar`, `QStatusBar`, `QAction`, `QKeySequence` | Actions give menu, toolbar and shortcut from one object (F5 refresh) |
| 2 | Page switching | `QStackedWidget` + `QTabBar` (document mode) or `QListWidget` sidebar | Pages: Connect, Devices, Scenes |
| 3 | Room navigation | `QSplitter` + `QListView`/`QListWidget` | Scales better than stacked group boxes once rooms exceed about 4 `[opinion]` |
| 4 | Scrolling | `QScrollArea` | Preserve scroll value across refresh (`t-19`) |
| 5 | Card grid | custom `QLayout` flow layout or resize-driven `QGridLayout` | No built-in `[known]`; about 70 lines |
| 6 | Card surface | `QFrame` with a dynamic property styled by QSS | Flat card plus 1 px border; no shadows (see 3.2) |
| 7 | Slider with fill | `QSlider` + QSS `groove` / `sub-page` / `handle` | Verified rendering `[qt]` |
| 8 | Gradient slider | `QSlider` + QSS `qlineargradient` on `groove` | Verified `[qt]`; for colour temperature, hue, saturation |
| 9 | Meter | `QProgressBar` + QSS `::chunk` | Needs `setFixedHeight` and `setTextVisible(False)` `[qt]` |
| 10 | Segmented control | `QButtonGroup` (exclusive) + checkable `QToolButton` | Verified; end caps via a `segpos` property `[qt]` |
| 11 | Toggle switch | custom `QAbstractButton` subclass | Appendix A; stays checkable, focusable, keyboard-operable |
| 12 | Drawn widgets | `QPainter`, `QPainterPath`, `QRectF` | Blind position bar, sparkline, battery glyph |
| 13 | Animation | `QPropertyAnimation`, `QEasingCurve`, `QGraphicsOpacityEffect` | Keep to switch thumb and toast fade |
| 14 | Debounce / timers | `QTimer` (single shot) | Slider commands (`req-6`), undo countdown, relative times |
| 15 | Icons | `QtSvg` (`QSvgRenderer`, importable `[qt]`) with SVG strings in a Python module | No asset files; recolor `currentColor` per theme |
| 16 | Theme | `QStyleHints.colorScheme()` and `colorSchemeChanged` (both exist `[qt]`), `QPalette`, `QApplication.setStyle("Fusion")` | Styles available here: Windows, Fusion `[qt]`; Fusion default on this platform |
| 17 | Popovers / menus | `QMenu` + `QWidgetAction`, `QToolButton` with `setMenu` | Colour picker, scene "Undo" |
| 18 | Persistence | `QSettings` | Window geometry only; the hub token stays out of it (`req-7`, `req-8`) |
| 19 | Background work | `QThread` (event listener), `QThreadPool` + `QRunnable` (commands) | Signals to cross back to the GUI thread (`req-4`) |
| 20 | Notifications | `QSystemTrayIcon.showMessage` (exists `[qt]`) | Leak alerts; only meaningful if the app runs in the tray `[opinion]` |
| 21 | Accessibility | `setAccessibleName`, `setToolTip`, focus policy | Every switch and slider needs a name like "Bookshelf brightness" |

### 3.1 Cards versus model/view

Model/view (`QAbstractListModel` + `QListView` + `QStyledItemDelegate`) virtualizes
long lists, but interactive controls inside delegates need persistent editors and
are awkward. A home has tens of devices, not thousands, so use real widgets per
device inside a scroll area. Revisit only past about 200 devices `[opinion]`.

### 3.2 QSS: what works and what bites

| # | Item |
| --- | --- |
| 1 | Works `[qt]`: dynamic-property selectors (`QFrame[kind="card"][offline="true"]`), `border-radius`, per-corner radii, `qlineargradient`, slider sub-controls, `QProgressBar::chunk`, `:checked`, `:hover`, `:disabled` |
| 2 | Pitfall `[qt]`: a dynamic property named `pos` collides with the built-in `QWidget.pos` property, so `[pos="first"]` did not match. Use a prefixed name (`segpos`) |
| 3 | Pitfall `[qt]`: a `pyqtProperty` named `pos` on a widget shadows the `pos()` method in Python. Use `thumb` or `progress` |
| 4 | Pitfall `[qt]`: an 18 px slider handle clips unless the slider has `setMinimumHeight(24)` |
| 5 | Pitfall `[qt]`: `height:6px` on `QProgressBar` in QSS did not apply; use `setFixedHeight(6)` |
| 6 | Pitfall `[known]`: type selectors match subclasses (`QLabel` is a `QFrame`); scope rules with properties or object names |
| 7 | Pitfall `[known]`: after changing a dynamic property at runtime, call `style().unpolish(w)` then `polish(w)` for the new rule to apply |
| 8 | Not supported `[known]`: `box-shadow`, CSS transitions, flex/grid. Avoid `QGraphicsDropShadowEffect` on many widgets inside scroll areas; it is costly and clips |
| 9 | Noise `[qt]`: the offscreen platform prints "does not support propagateSizeHints()"; ignore it when asserting "no QSS warnings" in smoke tests (`req-9`) |

## 4. Device to element mapping

Rule for every card: show a control only if its capability is present (finding 1);
if `is_reachable` is false, dim the card via a property, disable the controls and
show "Offline" plus `last_seen` as a relative time in a tooltip. Card header is
always: name (bold), humanized type (never the raw `device_type`), battery chip if
`battery_percentage` is not None.

### 4.1 Widgets or QML

| # | Option | For | Against |
| --- | --- | --- | --- |
| 1 | QtWidgets + QSS + 4 to 5 custom widgets | Matches the existing code; offscreen smoke tests already planned (`req-9`); flat module layout in `AGENTS.md`; QSS verified above | Switch, flow layout, bar widgets are hand-written |
| 2 | QML / Qt Quick Controls 2 | Native `Switch`, `Dial`, `RangeSlider`; Fluent style on Windows; animation is declarative | Rewrite of the whole UI; two languages; tests harder; token and thread plumbing crosses a bridge |
| 3 | Hybrid via `QQuickWidget` | Use QML only for a gauge | Two styling systems side by side `[opinion]` |

Recommendation `[opinion]`: option 1. Revisit QML only if you want heavy animation
or gauge visuals.

### 4.2 Lights (`light`)

| # | Data | Element | Shown when |
| --- | --- | --- | --- |
| 1 | `is_on` | Switch (custom `QAbstractButton`) | `isOn` capability |
| 2 | `light_level` | `QSlider` 1 to 100 + fixed-width right-aligned `%` label | `lightLevel` capability |
| 3 | `color_temperature` | `QSlider` with warm-to-cool gradient groove, range from normalized bounds | `colorTemperature` capability |
| 4 | `color_hue`, `color_saturation` | Two gradient `QSlider`s (hue rainbow 0 to 360, saturation 0 to 1) in a popover | `colorHue` and `colorSaturation` capabilities |
| 5 | `color_mode` | Decides which of 3 or 4 is highlighted; allowed values `[unverified]` | if value is known |
| 6 | `adaptive_profile.active` | `QComboBox` of profiles plus "Manual" | `get_adaptive_profiles()` non-empty `[unverified]` |
| 7 | `startup_on_off` | `QComboBox` in the expanded section | present |

Notes: the slider minimum is 1 because 0 raises `ValueError` `[lib]`; "off" goes
through the switch, not the slider. Send on `sliderReleased` or after a short
`QTimer` (`req-6`), update the label live while dragging, resync on failure (`req-3`).
Rows 3 to 7 belong in a collapsible section (`QToolButton` arrow +
`QPropertyAnimation` on `maximumHeight`) to keep the primary card calm.
`QColor.hueF()` returns 0 to 1 and -1 for greys; convert carefully to the API's
0 to 360.

### 4.3 Outlets (`outlet`) and electrical sensors

| # | Data | Element |
| --- | --- | --- |
| 1 | `is_on` | Switch |
| 2 | `current_active_power`, `current_voltage`, `current_amps` | `MetricLabel` (value large, unit and caption small); only the non-None ones |
| 3 | `total_energy_consumed` | `MetricLabel` in kWh |
| 4 | power over time | `QPainter` sparkline fed from in-memory samples; live-updates feature (section 2.7) |
| 5 | `status_light`, `startup_on_off` | Small switch and `QComboBox` in the expanded section |
| 6 | `electricalSensor` with matching `relation_id` | Merge into the outlet card; standalone read-only tile only if no outlet matches (`t-13`) |

### 4.4 Blinds (`blinds`)

| # | Data | Element | Shown when |
| --- | --- | --- | --- |
| 1 | `blinds_current_level`, `blinds_target_level` | Custom `BlindPositionBar`: fill = current, handle = target; or a plain `QSlider` plus a thin `QProgressBar` for current | `blindsTargetLevel` capability |
| 2 | `blinds_state` | Moving icon + text ("Moving up"), no spinner | present |
| 3 | up / stop / down | Three `QToolButton`s (non-exclusive) calling `set_state` | `blindsState` capability (`t-12`) |
| 4 | `battery_percentage` | Battery chip | not None |

Do not label the ends "open" or "closed": the library only says 0 to 100
`[unverified]`. Check on the physical blind.

### 4.5 Air purifier (`airPurifier`)

| # | Data | Element |
| --- | --- | --- |
| 1 | `fan_mode` | Exclusive segmented `QButtonGroup` (Off, Low, Medium, High, Auto) |
| 2 | `motor_state` 0 to 50 | `QSlider`; its relation to `fan_mode` (code comment: 0 off, 1 auto) is `[unverified]`, so hide it until checked |
| 3 | `current_p_m25` | `MetricLabel`; unit undocumented `[unverified]` |
| 4 | filter | `QProgressBar` of `1 - elapsed/lifetime`; valid only if both share a unit `[unverified]` |
| 5 | `filter_alarm_status` | Warning badge (dynamic property `state="warn"`, verified styling `[qt]`) |
| 6 | `child_lock`, `status_light` | Two small switches in the expanded section |
| 7 | `motor_runtime`, `fan_mode_sequence` | Omit; diagnostics only |

No air purifier controls exist in the current code or backlog; this is new scope.

### 4.6 Sensors (read-only tiles)

| # | `device_type` | Element |
| --- | --- | --- |
| 1 | `environmentSensor` | Grid of `MetricLabel`: temperature °C, humidity %, PM2.5, VOC index, CO2 ppm; show only non-None; min/max PM2.5 in a tooltip |
| 2 | `motionSensor`, `occupancySensor` | State badge ("Motion" / "Clear") via dynamic property; `light_level` as a metric on motion sensors |
| 3 | `openCloseSensor` | State badge ("Open" / "Closed") |
| 4 | `waterSensor` | State badge; on `water_leak_detected` also an app-level danger banner (and a tray notification if tray-resident) |
| 5 | `lightSensor` | `MetricLabel` for `illuminance` (unit undocumented `[unverified]`) |
| 6 | all battery devices | Battery chip: a small painted glyph or `QProgressBar`; low state at or below a threshold the product owner picks `[opinion]` |

Colour banding for air quality needs an external standard and is a product
decision; default to plain numbers with no colour until one is chosen. Never rely
on colour alone: pair every state colour with text or an icon.

### 4.7 Controllers (`*Controller`)

Compact tile: name, humanized type, battery chip, reachability. No controls. A live
"pressed" flash is possible only after the press event shape is known
(section 2.6, item 4).

### 4.8 Scenes

| # | Data | Element |
| --- | --- | --- |
| 1 | `info.name`, `info.icon` | Card with SVG glyph (mapped, fallback glyph) and title |
| 2 | activation | Whole card or a primary `QPushButton`, keyboard-activatable; replaces the modal `QMessageBox.information` `[code]` with a non-blocking toast or inline "Activated" state |
| 3 | undo | `QToolButton` with a `QMenu` item or a small "Undo" button shown for `undo_allowed_duration`, driven by a `QTimer`; unit of the duration `[unverified]` |
| 4 | next run | Label from the earliest non-disabled `triggers[].next_trigger_at` |
| 5 | failure | Inline error on the card with retry; not a modal |

### 4.9 Fallback for unknown device types

Show name, humanized `device_type` (split camelCase, sentence case), model and
manufacturer. No ✓. Never show the raw `device_type` string as the type label.

## 5. State and threading shape (brief)

This is the structure that makes the above cheap to build; the detailed plan
belongs in the implementation plan, not here `[opinion]`.

1. A `DeviceStore(QObject)` owns the device objects keyed by `id`, merges refreshes
   and events, and emits `deviceChanged(str)`. Cards subscribe; they never poll.
2. Event merge: either map the event's camelCase keys onto the model, or call
   `device.reload()` for the event's `id` (one `GET /devices/{id}`); the second is
   simpler and robust.
3. A `QThread` runs the listener in a loop with a short sleep and a full refetch on
   reconnect (the library README's own recommendation).
4. Commands run on a `QThreadPool`/`QRunnable` (or one serial worker, finding 6),
   report back by signal, and coalesce slider values (latest wins).
5. Controls update with `blockSignals(True)` or a guard flag so a store update never
   triggers a command (the current `sync_control_from_device` already follows this
   `[code]`).
6. Prefer one raw `hub.get("/devices")` and per-device conversion inside
   `try/except` over `get_all_devices()` only if measurements show the 12-call cost
   matters; the library's `dict_to_*` converters are importable but are not
   documented as public API `[lib]`.

## 6. Open questions and how to answer them

Answer from real data, not assumption. The dump below is read-only. Supply the token
through an environment variable and never print or commit it; strip serial numbers
before sharing output. The variable names are examples.

```python
import os
from dirigera import Hub

hub = Hub(token=os.environ["DIRIGERA_TOKEN"], ip_address=os.environ["DIRIGERA_IP"])
for d in hub.get("/devices"):
    print(d["deviceType"], d["attributes"].get("customName"),
          "reachable:", d["isReachable"], "hidden:", d.get("isHidden"),
          sorted(d["capabilities"]["canReceive"]))
```

| # | Question | How to settle it |
| --- | --- | --- |
| 1 | Blind level 0 means open or closed? | Move a real blind and read `blinds_current_level` |
| 2 | Units of PM2.5, illuminance, filter times; meaning of `motor_state` | Compare against the IKEA app's displayed values |
| 3 | Is a plug's energy on the outlet or a separate electrical sensor? | Dump shows whether an `electricalSensor` shares its `relationId` |
| 4 | Should `is_hidden` devices be shown? | Compare the dump with what the IKEA app lists |
| 5 | Values of `color_mode`, `room.icon`, `room.color` | Read from the dump |
| 6 | Does `light_level` stay populated while a light is off? | Read from the dump with a light off |
| 7 | Event shapes for button presses, add/remove, reachability | Log raw events from a listener while pressing a remote |
| 8 | Is one shared `Hub` safe across threads? | Treat as unsafe; serialize hub calls |
| 9 | Air quality colour bands | Product decision plus a cited standard; default none |
| 10 | Tray-resident app for alerts, or plain window | Product decision |
| 11 | Widgets or QML | Section 4.1; default Widgets |

## Appendix A: verified toggle switch

Verified offscreen `[qt]`: animates, shows a focus ring, renders a disabled state.
The animated property is named `thumb`, not `pos` (finding in section 3.2). Colours
are placeholders; take them from the theme tokens when implementing.

```python
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, QSize
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QAbstractButton


class Switch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._thumb = 0.0
        self._anim = QPropertyAnimation(self, b"thumb", self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self):
        return QSize(44, 24)

    def _animate(self, checked):
        self._anim.stop()
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def get_thumb(self):
        return self._thumb

    def set_thumb(self, value):
        self._thumb = value
        self.update()

    thumb = pyqtProperty(float, get_thumb, set_thumb)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on, off = QColor("#1F5FD1"), QColor("#7C8696")
        if not self.isEnabled():
            on, off = QColor("#9DB4E3"), QColor("#C9CFDA")
        t = self._thumb
        track = QColor(*(int(off.getRgb()[i] + (on.getRgb()[i] - off.getRgb()[i]) * t) for i in range(3)))
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * t
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QColor("#1F5FD1"))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(0, 0, -1, -1), 12, 12)
```

Set `setAccessibleName("<device> power")` on each instance when it is created.
