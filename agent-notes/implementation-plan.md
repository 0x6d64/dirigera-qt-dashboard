# implementation plan

Concrete implementation plans for tasks from `agent-notes/todo.md`.
Reference tasks by their `t-<number>` ID — plans never get their own IDs
(see `AGENTS.md`).

## Format

```
### Plan: <short title> (t-<id>[, t-<id>])

Goal: <one or two sentences>
Affected files: <paths>
#### Commit N — "<message>" (t-<id>)
1. <step>
Verification: <commands / manual checks>
```

Plans use `###`, commits inside a plan use `####`.

## Active plans

### Plan: dirigera 1.6.1 migration follow-ups (t-12, t-14 … t-16)

Goal: Adopt the capabilities added in `dirigera` 1.6.1 that the card UI does
not expose yet. t-12 and t-13 landed with the `DeviceCard` refactor (design
plan commit 4); what remains is colour/temperature controls, adaptive
profiles, and live updates.

Affected files: `widgets/card.py`, `dashboard.py`

#### Commit 1 — "verify blind controls" (t-12) ✓ executed 2026-11-15

> Capability guard fixed in the same pass: `hasattr(attributes, "blinds_state")`
> was always true on the pydantic model, so every blind got Up/Down/Stop; it
> now requires an actual value. Verified offscreen — see step 3.

1. `widgets/card.py` renders Up / Down / Stop buttons for `blinds` devices
   when the device reports the capability (`"blindsState"` in
   `capabilities.can_receive`, or a `blinds_state` attribute exists), and
   emits the action label through the `on_blind_state` callback.
2. `dashboard.py` `set_blind_state()` maps `"Up"` / `"Down"` / `"Stop"` to
   `BlindsStateEnum.UP` / `DOWN` / `STOPPED` and calls `blind.set_state(...)`,
   keeping the warning-on-error pattern.
3. Offscreen smoke test: a `Blind` with `blindsState` in `can_receive` renders
   three buttons, and each triggers `set_state` with the matching enum; a
   `Blind` without the capability renders none.
4. Close t-12 in `todo.md` once the smoke test passes.

#### Commit 2 — "light color and temperature controls" (t-14)

1. In the light control zone of `widgets/card.py`, add an optional
   `on_color_temperature` callback (same pattern as `on_brightness`). When
   `"colorTemperature" in capabilities.can_receive` and min/max bounds are
   present, add a `LabeledSlider` spanning `attributes.color_temperature_min`
   … `color_temperature_max` (Kelvin; the library normalizes mireds
   internally) that emits on release (`released`), per req-6.
2. When `"colorHue"` / `"colorSaturation"` are in `can_receive`, add a
   "Color…" button opening `QColorDialog`; convert the picked color with
   `color.getHsvF()` (hue × 360, saturation × 100).
3. Handlers in `dashboard.py` (`set_light_color_temperature`,
   `set_light_color`) call `light.set_color_temperature(value)` and
   `light.set_light_color(hue, saturation)`, reusing the
   `sync_control_from_device` revert-on-failure pattern.
4. Every control behind a capability check — the library raises
   `AssertionError` otherwise.
5. Gates; offscreen smoke test invoking the handlers against a stubbed light.

#### Commit 3 — "adaptive light profiles" (t-15) — t-17 prerequisite is done

1. In `RefreshWorker.run`, fetch `self.adaptive_profiles =
   self.hub.get_adaptive_profiles()` inside a guarded `try` (empty list on
   failure — older hubs don't expose profiles).
2. Extend `DeviceCard` (constructor + factory call in `dashboard.py`) to
   accept the available profiles and, in the light control zone, add a
   `QComboBox` with "(manual)" plus profile names, preselecting the profile
   from `light.adaptive_profile.id` (new 1.6.1 field).
3. Handler `set_light_profile(light, profile_id)`: activating calls
   `light.activate_adaptive_profile(profile_id)` then `light.reload()`;
   choosing "(manual)" is a no-op (any manual change already ends adaptive
   mode).
4. Gates; offscreen smoke test with a stub hub returning one profile.
5. Note: adds blocking calls to the refresh flow — they belong in
   `RefreshWorker.run()` (t-17, done), never on the GUI thread.

#### Commit 4 — "live updates via websocket" (t-16) — large, after t-17 and t-10 decision

1. Add an `EventListenerThread(QThread)` wrapping
   `hub.create_event_listener(on_message=..., on_error=..., on_close=...)`;
   the callbacks only marshal data into a `pyqtSignal` — they must never
   raise and never touch widgets (the library's `run_forever` blocks the
   calling thread and disables TLS verification).
2. Slot on the GUI side: parse device events, match `device.id`, reload that
   device in a small worker and update its widget — requires reintroducing a
   widget registry (reverses t-10; record the ID's outcome in `todo.md`
   accordingly).
3. Start the listener after a successful connect; stop it on disconnect and
   in `closeEvent` (`hub.stop_event_listener()`).
4. Keep the manual Refresh button as fallback; add a "live" status indicator
   to the connection bar.
5. Gates; manual verification against a real hub (toggle a light from the
   IKEA app and watch the dashboard update without Refresh).

#### Ordering & dependencies

- The "Correctness & runtime bugs" plan (t-1 … t-10) and token generation
  (t-11) are done; no prerequisite work remains there.
- Design plan commits 1–9 are done (t-40 … t-45, t-46 … t-49, t-51, t-52);
  t-13 was closed by t-45 and t-12 by this plan's commit 1.
- The design plan is complete (10a, t-50, landed; 10b, t-53, moved to the
  tests/CI plan). t-46 landed before this plan's remaining commits, so
  the room/grid layout these controls render into is in place and its stable
  card ordering keeps `req-2` intact.
- t-17 (worker threads) is done: connect and refresh run in worker threads, so
  t-15 and t-16 are unblocked.
- t-56 adds a periodic refresh that today would rebuild the whole widget tree;
  land t-19 (plan "automated refresh", below) before commit 3 (t-15) so the
  profile combo it adds is not reset every poll.

---

### Plan: automated refresh (t-19, t-56)

Goal: stop the dashboard showing stale values. Poll the hub every 30 s and
update existing cards in place, so a poll keeps scroll position, card order,
focus, and an in-progress slider drag (`req-13`, `design-doc.md` §10.2,
`req-2`). t-56 is priority A and explicitly depends on t-19's incremental
update; if t-19 slips, ship t-56 with at least the unchanged-data skip so a
poll with identical data is a no-op.

Affected files: `dashboard.py`, `widgets/card.py`, `widgets/energy.py`,
`widgets/scene.py`, `doc/design-doc.md` §10.2, `doc/reqs.md`,
`agent-notes/todo.md`

#### Commit 1 — "update cards without rebuilding" (t-19)

1. `widgets/card.py`: add `update_from_device(device: Any) -> None`. Reassign
   `self.device`, then resync the *existing* controls from the new attributes —
   switch state, brightness/blind slider values, status chip, footer, offline
   state — without recreating widgets. Never overwrite a control that is
   currently focused or being dragged (`QSlider.isSliderDown()`,
   `QApplication.focusWidget()`).
2. `widgets/scene.py`: tiles only render name and glyph, so a scene update is a
   no-op; document that in the method (or omit it) rather than rebuilding.
3. `dashboard.py` `_on_refreshed`: match fetched devices and scenes to the
   existing cards by `device.id` / `scene.id`. Update matches in place, insert
   cards for new ids at their sorted position (`device_sort_key`), and remove
   cards whose ids disappeared. Do not clear `self.devices_layout`,
   `self.scenes_grid`, or the energy rooms on a normal poll.
4. Preserve view state around the update: capture
   `devices_scroll.verticalScrollBar().value()` (same for scenes and energy) and
   the focused widget, restore both after the update when the widget survived.
5. `widgets/energy.py`: add `update_rooms(...)` following the same in-place rule
   (match by device id), or — if that is disproportionate — document that the
   energy view rebuilds and that only its scroll position is preserved.
6. Early-out: compute a cheap signature of the fetched data (sorted
   `(device.id, is_reachable, repr(attributes))` plus scene ids) and return
   without touching the widget tree or the caption when it is unchanged.

Verification: offscreen script (no `pytest` until t-32) — stub hub whose
attributes change between fetches; feed `_on_refreshed` twice and assert the
same `DeviceCard` objects (identity, not recreated), an unchanged scrollbar
value, an unreleased slider still holding the dragged value, and that an
identical payload leaves the status caption untouched. Gates: black, ruff,
mypy clean.

#### Commit 2 — "periodic background refresh" (t-56)

1. `dashboard.py` `__init__`: `self.refresh_timer = QTimer(self)` with a
   30_000 ms interval, `timeout -> self._poll`, and `self._poll_interval = 30`.
2. `_poll()`: skip when `self.hub is None`, when `_connect_worker` or
   `_refresh_worker` is running (a poll must not stack on a manual refresh),
   and when the window is minimised. Otherwise call `refresh_devices()`.
3. Start the timer in `_on_connected` (after the first successful refresh) and
   stop it in the disconnect path and in `closeEvent`, next to the existing
   worker shutdown.
4. Minimise handling: `changeEvent(QEvent)` for `QEvent.Type.WindowStateChange`
   — stop the timer when `isMinimized()`, restart it when restored and fire one
   immediate poll so the view is current again.
5. Caption: show the schedule and the last successful update in the status row,
   e.g. `Updated 21:42 · every 30 s`, refreshed in `_on_refreshed`. Keep the
   existing stale caption for failures; when the last success is older than two
   intervals, surface it in warn tone without a modal dialog — a silent poll
   failure must not raise a `QMessageBox` every 30 s, so suppress the dialog for
   timer-driven refreshes and keep it for manual ones.
6. Docs: record polling in `design-doc.md` §10.2 (interval, pause rules,
   last-update caption, no modal on background failure); mark `req-13`
   implemented in `reqs.md`; check off t-19 and t-56 in `todo.md`.

Verification: offscreen script — connect with a stub hub, assert the timer is
active with a 30 s interval, that a poll during an in-flight manual refresh is
skipped, that a minimised window does not fire, and that a failed background
poll sets the warn caption without creating a dialog. Gates as above.

---

### Plan: responsive header under 640 px (t-54)

Goal: remove the ~970 px minimum window width set by the fixed 56 px single-row
header (design commit 6), so the window can actually reach t-46's 640 px
single-column breakpoint by resizing (`design-doc.md` §11 row 3, minimum window
640 × 480).

Affected files: `dashboard.py` (`build_header`, `init_ui`, `resizeEvent`),
`widgets/segments.py` (only if the control needs a compact variant),
`doc/design-doc.md` §4.2/§11, `agent-notes/todo.md`

#### Commit 1 — "two-row header below 640 px" (t-54)

1. Define `HEADER_BREAKPOINT = 640`, `HEADER_HEIGHT = 56`, and
   `HEADER_HEIGHT_COMPACT = 96` (two 48 px rows) as module constants in
   `dashboard.py`.
2. Split `build_header()` into a widget that owns two layouts: row 1 (title,
   status chip, stretch, search field, Refresh) and row 2 (view switcher). At
   normal widths row 2 is hidden and the switcher lives in row 1 — move the one
   instance with `QLayout.removeWidget(w)` then `addWidget(w)`; a widget can
   only have one parent, so do not create a second copy.
3. `_apply_header_layout(compact: bool)`: toggles row membership, header fixed
   height, and alignment; call it from `resizeEvent` only when the boolean
   changes, to avoid relayout churn during a drag.
4. Keep the 760 px behaviour intact: the search field still shrinks to about
   180 px before the compact switch. In compact mode the switcher sits on row 2
   left-aligned and the search field takes the remaining row-1 width.
5. Set `setMinimumWidth(640)` and `setMinimumHeight(480)` on the main window
   once the header no longer forces more, and assert
   `minimumSizeHint().width() <= 640`.

Verification: offscreen — resize to 1080 / 760 / 640 / 639 px and assert header
height is 56 px above the breakpoint and 96 px below it, the switcher is on
row 2 only in compact mode, card columns are 3 / 2 / 1 / 1, and
`minimumSizeHint().width() <= 640`. Manual: drag the window narrow on Windows;
check the 150 % scaling note in §11. Gates: black, ruff, mypy clean.

---

## Done

### Plan: pytest suite (t-32, t-33, t-53, t-55)

Goal: a small suite that guards behaviour (requirements) and pure logic, not
layout or styling, so it survives UI work. Executed on branch
`test/pytest-suite`.

1. Add `pytest` to the dev group, `pythonpath`/`testpaths` config and shared
   fixtures in `tests/conftest.py` (offscreen `QApplication`, recording
   `QMessageBox` stub, `wait_until`/`pump` helpers, stub device/light/scene/hub,
   a `window` fixture that never reads the real `config.ini`).
2. Pure logic: discovery helpers with mocked network (req-5), room grouping,
   labels, sort order.
3. Widget contracts: `LabeledSlider` commit semantics (req-6); WCAG contrast of
   theme token pairs (t-53).
4. Dashboard behaviour against a stub hub: connect verification (req-1),
   failed refresh keeps view (req-2), failed command resync (req-3), no GUI-thread
   hub calls (req-4), inline scene errors, scene lookup after refresh, filter,
   deferred close (req-14).
5. GitHub Actions CI (t-33): gates plus pytest; `slow` tests run on master
   only, `hardware` tests never.
6. Bookkeeping in `todo.md`.

Rules for new tests: assert state a user can observe or a requirement, use the
stubs in `conftest.py`, never assert pixel sizes, stylesheet text or widget-tree
shape. Not covered here: real-hub runs, the remaining ad-hoc scripts
of t-55 (energy view, header responsiveness).

Verification: `uv run pytest`, plus the three gates.

### Plan: design document v1.0 implementation (t-40 … t-53)

Goal: Implement the visual design described in `doc/design-doc.md` v1.0 —
introducing a token-driven theme, purpose-built components, a redesigned card
and grid layout, a header bar with segmented navigation, and three views
(Rooms, Scenes, Energy).

Affected files: `theme.py` (new), `widgets/switch.py` (new),
`widgets/slider.py` (new), `widgets/chip.py` (new), `widgets/metric.py` (new),
`widgets/card.py` (new), `widgets/grid.py` (new), `widgets/segments.py` (new),
`widgets/connection.py` (new), `widgets/energy.py` (new),
`widgets/icons.py` (new), `dashboard.py` (heavily refactored), `main.py`
(stylesheet injection)

#### Ordering note

Execute commits in this order. Each commit is independently mergeable but
relies on the files introduced before it:
`t-40 → t-43 + t-44 → t-41 + t-42 → t-45 → t-46 + t-47 + t-48 → t-49 + t-51 + t-52 → t-50 + t-53`

**Status (2026-11-21): complete.** Commits 1–9 and 10a (t-50, search filter)
are executed. Commit 10b (t-53, contrast tests) was moved out of this plan on
2026-11-21: it is blocked until t-32 adds `pytest` and `tests/` and t-33 adds
CI (its acceptance criterion is "run as part of CI"), so it belongs to the
tests/CI plan that will cover t-32, t-33 and t-55. The commit 10b steps below
stay as the reference for that plan.

---

#### Commit 1 — "theme module and design tokens" (t-40) ✓ executed 2026-11-14

**New file: `theme.py`**

1. Define all 17 colour tokens from `design-doc.md` §5.1 as module-level
   string constants (`WINDOW`, `SURFACE`, `SUNKEN`, `BORDER`, `TEXT`,
   `TEXT2`, `ACCENT`, `ACCENT_HOVER`, `ON_ACCENT`, `ACCENT_SOFT`, `OFF`,
   `OK`, `OK_BG`, `WARN`, `WARN_BG`, `DANGER`, `DANGER_BG`).
2. Define spacing constants from §4.4: `SP4=4`, `SP8=8`, `SP12=12`,
   `SP16=16`, `SP20=20`, `SP24=24` and radius constants: `RADIUS_CARD=10`,
   `RADIUS_BUTTON=6`.
3. Define font constants: `FONT_METRIC=28`, `FONT_TITLE=16`, `FONT_BODY=14`,
   `FONT_LABEL=13`, `FONT_CAPTION=12`.
4. Implement `generate_stylesheet() -> str` that returns a QSS string applying
   the tokens to `QMainWindow`, `QWidget`, `QPushButton`, `QLineEdit`,
   `QSlider`, `QLabel`, `QGroupBox`, and `QScrollArea`. Avoid per-widget
   colour hard-coding in any other module.
5. In `main.py`: call `app.setStyleSheet(theme.generate_stylesheet())` after
   creating `QApplication`.
6. Gates: `uv run black . && uv run ruff check . && uv run mypy .`; offscreen
   smoke test that imports `theme` and asserts token values are non-empty
   strings.

---

#### Commit 2 — "status chip and metric widgets" (t-43, t-44) ✓ executed 2026-11-14

**New files: `widgets/chip.py`, `widgets/metric.py`**

Create a `widgets/` package (`widgets/__init__.py` empty).

**t-43 — `widgets/chip.py`**

1. `class StatusChip(QLabel)`:
   - Constructor: `__init__(self, text: str, variant: str = "neutral")`.
   - `variant` is one of `"ok"`, `"warn"`, `"danger"`, `"neutral"`.
   - Sets fixed height 20 px, fully rounded (border-radius = 9 px for 18 px
     font height + 2 px padding), caption font (12 px), and padding 2 px top/
     bottom, 9 px left/right via QSS from `theme` tokens.
   - `set_variant(variant: str) -> None`: updates colours with
     `unpolish/polish` to force QSS re-evaluation.

**t-44 — `widgets/metric.py`**

1. `class MetricWidget(QWidget)`:
   - Constructor: `__init__(self, caption: str)`.
   - Layout: `QHBoxLayout` with a 28 px bold value `QLabel` and a caption-size
     unit `QLabel` baseline-aligned, then a caption `QLabel` beneath the whole
     group.
   - `set_value(value: float | None, unit: str) -> None`: formats the number
     (1 dp for floats, `"–"` for `None`) and updates both labels.
2. Gates: offscreen smoke tests instantiating each widget; assert chip height
   is 20 px and metric label text matches expected format.

---

#### Commit 3 — "custom switch and slider widgets" (t-41, t-42) ✓ executed 2026-11-14

**New files: `widgets/switch.py`, `widgets/slider.py`**

**t-41 — `widgets/switch.py`**

1. `class ToggleSwitch(QAbstractButton)`:
   - Geometry: `sizeHint()` returns `QSize(44, 24)`.
   - `thumb` `pyqtProperty(float)` drives the thumb X position from 3 px
     (off) to 23 px (on). Do **not** name it `pos`.
   - `QPropertyAnimation` on `thumb`, 120 ms, `QEasingCurve.Type.OutCubic`.
   - `paintEvent`: draw the rounded track (`ACCENT` if checked, `OFF` if not)
     and white thumb circle (18 px diameter, 3 px inset) using `QPainter`.
   - After `setChecked`, call `setAccessibleName(label)` where `label` is
     passed at construction.
   - `toggled(bool)` signal emitted on click.

**t-42 — `widgets/slider.py`**

1. `class LabeledSlider(QWidget)`:
   - Layout: `QHBoxLayout` with a fixed-width (60 px) `QLabel` for the label,
     a `QSlider(Qt.Orientation.Horizontal)`, and a fixed-width (50 px)
     right-aligned `QLabel` for the value.
   - Slider: minimum height 24 px; track 6 px via QSS from `theme`; thumb
     18 px. Do **not** use `QSlider:disabled::sub-page`.
   - `valueChanged` emits a `value_changed(int)` pyqtSignal on each tick
     (for live value display only). The `released(int)` pyqtSignal fires on
     `sliderReleased` for sending hub commands (`req-6`).
   - Disabled state: use a custom `active` property that swaps colours via
     `unpolish/polish`.
2. Gates: offscreen smoke test; assert slider minimum height ≥ 24 px; assert
   `released` does not fire on value change, only on release.

---

#### Commit 4 — "redesigned device card" (t-45, closes t-13) ✓ executed 2026-11-14

**New file: `widgets/card.py`; refactor `dashboard.py`**

1. `class DeviceCard(QFrame)`:
   - Geometry: `setMinimumWidth(280)`, `setFrameShape(QFrame.Shape.StyledPanel)`.
   - QSS (from `theme`): background `SURFACE`, border 1 px `BORDER`,
     border-radius `RADIUS_CARD` px, padding `SP16` px.
   - **Header row** (`QHBoxLayout`):
     - Left column: device name (`QLabel`, 16 px bold, `elideRight`,
       `setToolTip(full_name)`) over device type (`QLabel`, 12 px, `TEXT2`).
     - Right: `StatusChip` (initially `"neutral"` / empty).
   - **Control zone** (`QVBoxLayout`): populated by device-type helpers (see
     below); empty for read-only/offline devices.
   - **Footer** (`QLabel`, 12 px, `TEXT2`): battery, last-seen or hint text.
   - `set_offline(offline: bool)`: sets background to `SUNKEN`, disables
     controls, updates chip to `"neutral" / "Offline"`.
   - Device-type control helpers:
     - Light: `ToggleSwitch` for on/off + `LabeledSlider` for brightness
       (1–100 %) + blind buttons if applicable.
     - Outlet: `ToggleSwitch` only.
     - Blind: position `LabeledSlider` + Up / Down / Stop buttons (t-12
       logic, now visual).
     - Electrical sensor: `MetricWidget` for power (W); captions for V and A;
       footer with total kWh (closes t-13).
     - Other: no control zone (read-only card).
   - Stable ordering within rooms: lights → outlets → blinds → sensors →
     remotes.
2. In `dashboard.py`, replace `create_device_widget` calls with
   `DeviceCard(device)`.
   Note: in the executed refactor, `create_device_widget()` was kept as a thin
   factory that injects the action handlers into `DeviceCard` — keep that
   indirection for later commits that add callbacks.
3. Gates: offscreen smoke tests for each device type; assert no
   `QCheckBox` or bare `QSlider` remains in the widget tree.

---

#### Commit 5 — "responsive card grid and room sections" (t-46) ✓ executed 2026-11-15

> `FlowLayout` lives in `widgets/grid.py` (new file) as a height-for-width
> layout. A plain `QGridLayout` with a recomputed column count was tried first
> and rejected: every card's 280 px minimum pinned the row, so the grid kept
> its column count while the window shrank instead of reflowing. Verified
> offscreen — 3 / 2 / 1 columns at 1080 / 760 / 640 px.

**Refactor `dashboard.py` devices tab layout**

1. Implement `FlowLayout(QLayout)` (or use `QGridLayout` with dynamic column
   count): on `resizeEvent`, recompute columns as
   `max(1, floor(available_width / (280 + SP16)))` and rearrange cards.
2. Replace the current `QVBoxLayout`-of-`QGroupBox` room layout with:
   - For each room: a `QLabel` section header (13 px, medium weight, `TEXT2`,
     sentence-case room name) followed by the `FlowLayout` of `DeviceCard`s.
   - Room sections stacked in a single `QVBoxLayout` with 24 px gap between
     them.
3. Wrap the whole thing in a `QScrollArea` (widget already set;
   `widgetResizable=True`).
4. Preserve card order within rooms on refresh (`req-2`, t-19): do not sort
   or shuffle cards between refresh cycles.
5. Gates: resize the offscreen window to 1080, 760, and 640 px; assert column
   count is 3, 2, 1 respectively; assert room label text is sentence-case.

---

#### Commit 6 — "header bar and segmented view switcher" (t-47) ✓ executed 2026-11-15

> Two interim decisions, both reversed by later commits:
> - The IP/token inputs stay in a temporary row under the header instead of
>   disappearing, so connecting still works until t-48 replaces them with the
>   not-connected block.
> - The Energy segment is shown but disabled (tooltip "arrives in t-49"), since
>   there is no Energy view before t-49.
>
> The fixed 56 px single row sets a ~870 px minimum window width, so t-46's
> 640 px breakpoint is not reachable by resizing yet — recorded as t-54
> (two-row header, `design-doc.md` §11 row 3).

**Refactor `dashboard.py` top-level layout**

1. Replace the `QGroupBox("Hub Connection")` section with a fixed-height
   56 px `QWidget` header bar:
   - Left: app title `QLabel` (18 px, semibold).
   - Hub status `StatusChip` (initially neutral "Not connected").
   - Flexible spacer.
   - Search `QLineEdit` (260 px, `sunken` background, placeholder "Search
     devices and scenes", disabled until connected).
   - Segmented view switcher: three `QPushButton`s ("Rooms", "Scenes",
     "Energy") joined visually; selected one gets `accent-soft` background
     and `accent` text via a `selected` dynamic property + `unpolish/polish`.
   - Ghost-style "Refresh" `QPushButton` (1 px border, `text` label).
   - Bottom border 1 px `BORDER`.
2. Remove the token and IP fields from the header — they move to the
   not-connected block (t-48).
3. Keep the existing `QTabWidget` logic for now but wire it to the new
   segmented switcher (tab switching can migrate fully in t-48/t-49).
4. Gates: offscreen test asserts header height == 56 px; chip text is
   "Not connected" at startup; switcher buttons are exclusive.

---

#### Commit 7 — "not-connected state and connection block" (t-48) ✓ executed 2026-11-15

> The block lives in `widgets/connection.py` and the content area is a
> `QStackedWidget` (connection block / views page), so nothing is drawn behind
> the form. Three notes:
> - The search field stays disabled even when connected; an enabled field that
>   filters nothing would be worse than an inert one until t-50.
> - A failed connect attempt shows the warn chip "Hub unreachable" — §3.1 has
>   no connect-failed row, and it describes the situation better than
>   "Not connected".
> - The credential probe still runs on the GUI thread, so "Connecting…" is a
>   brief state; t-17 moved the hub I/O into a worker thread.

**Refactor `dashboard.py` connection logic**

1. Add a `ConnectionBlock(QWidget)`: centred card (`SURFACE`, 400 px wide,
   `RADIUS_CARD` radius) containing:
   - Heading `QLabel` "Connect to your hub" (16 px bold).
   - Help line `QLabel` (caption, `TEXT2`).
   - IP `QLineEdit` (placeholder "e.g. 192.168.1.100").
   - Token `QLineEdit` (placeholder "Authentication token",
     `EchoMode.Password`).
   - `QHBoxLayout` with ghost "Discover" and primary "Connect" buttons.
2. When `self.hub is None`: show `ConnectionBlock` in the content area, hide
   the view grid; set header chip to `"neutral" / "Not connected"`.
3. When connecting: disable all `ConnectionBlock` inputs and buttons; set chip
   to `"neutral" / "Connecting…"`.
4. On success: hide `ConnectionBlock`, show view grid; set chip to
   `"ok" / "Hub online · <ip>"`.
5. On refresh failure: set chip to `"warn" / "Hub unreachable"` and show
   "Showing data from <time>" in a content-area caption; keep device cards
   in place (`req-2`).
6. Load IP and token from `config.ini` into `ConnectionBlock` fields on start.
7. Gates: offscreen tests covering each connection state; assert chip variant
   and text match the spec; assert `ConnectionBlock` is hidden when connected.

---

#### Commit 7a — "off-thread hub calls" (t-17) ✓ executed 2026-11-15

> Prerequisite for commit 8, recorded here because commit 8 depended on it: the
> Energy view is only useful if the refresh that feeds it does not freeze the
> window. Not part of the design plan's commit list.

**`dashboard.py`: worker threads for connect and refresh**

1. `ConnectWorker(QThread)` — constructs `Hub(...)` and probes `get("/home")`
   in `run()`; emits `connected(hub, ip)` or `failed(message)`.
2. `RefreshWorker(QThread)` — fetches devices and scenes in `run()`; emits
   `refreshed(devices, scenes)` or `failed(message)`.
3. `connect_to_hub()` / `refresh_devices()` only start a worker. While one
   runs the other is refused, so clicks cannot stack up network calls.
   Refresh is disabled while loading and re-enabled when the worker finishes.
4. Widget updates happen exclusively in the GUI-thread slots
   (`_on_connected`, `_on_connect_failed`, `_on_refreshed`,
   `_on_refresh_failed`); the workers never touch widgets.
5. `closeEvent` waits for an in-flight worker (bounded 2 s) so no `QThread`
   outlives the window.

---

#### Commit 8 — "Energy view" (t-49) ✓ executed 2026-11-15

> The plan's original note said "schedule after t-17"; t-17 is done (commit
> 7a), so the refresh that feeds this view no longer blocks the GUI thread.
>
> Deviations from the plan text:
> - `EnergyCard` is its own widget in `widgets/energy.py` instead of a
>   `DeviceCard`: the content zone is a power metric plus an A/V caption, not
>   on/off controls, and an unmetered device must show no metric row at all.
> - The tab bar is hidden: with three views the segmented switcher is the only
>   navigation, and a visible tab bar duplicated it (`design-doc.md` §4.2).
> - No totals are shown: §9.4 leaves per-home versus per-room totals `[open]`.
> - An empty home shows a centred "No energy data" caption instead of an empty
>   grid.
>
> Metering is gated on `current_active_power` being present; both
> `OutletAttributes` and `ElectricalSensorAttributes` carry it in 1.6.1, so the
> same card works for both device types.

**Add Energy tab to `dashboard.py`**

1. Add a third segment ("Energy") to the switcher from t-47.
2. `EnergyView(QWidget)`: same flow-grid layout as the Rooms view, populated
   with `DeviceCard`s restricted to outlets and electrical sensors.
3. For each device:
   - If `ElectricalSensorAttributes` are present: show `MetricWidget` for
     live power (W), secondary captions for voltage (V) and current (A),
     footer with total energy (kWh).
   - If outlet with no metering data: footer reads "No energy data"; no
     empty metric row.
4. Totals and grouping by room, same approach as Rooms view.
5. Gates: offscreen smoke test with stub electrical sensor data; assert metric
   labels contain the expected values and "No energy data" appears for
   unmetered outlets.

---

#### Commit 9 — "scene tiles and SVG icon system" (t-51, t-52) ✓ executed 2026-11-15

**New file: `widgets/icons.py`; refactor scenes layout in `dashboard.py`; new `widgets/scene.py`**

**t-52 — `widgets/icons.py`**

1. `ICON_SVG: dict[str, str]` mapping icon names (`"light"`, `"outlet"`,
   `"blind"`, `"scene"`, `"sensor"`, etc.) to SVG strings on a 24 px grid,
   1.5 px stroke, `currentColor` fill/stroke.
2. `render_icon(name: str, color: str, size: int = 24) -> QPixmap`: replaces
   `currentColor` with the given hex token and uses `QSvgRenderer` to raster
   to a `QPixmap`.
3. Fallback: if name not found, return an empty `QPixmap`.

**t-51 — scene tiles**

1. `class SceneTile(QFrame)`:
   - Min width 240 px; same surface/border/radius as `DeviceCard`.
   - Glyph: `QLabel` with `render_icon("scene", theme.ACCENT)` (or scene-
     specific icon if mapped).
   - Name `QLabel` (16 px bold).
   - Right/bottom-aligned primary "Activate" button.
   - On activate: call `scene.trigger()` in a worker thread; on return show
     "Activated" (`OK` text colour) for 2 s via `QTimer`, then revert.
2. Replace the existing `QListWidget` scene list with a `FlowLayout` of
   `SceneTile`s.
3. Gates: offscreen smoke test; assert tile minimum width ≥ 240 px; assert
   "Activated" label appears and reverts.

---

#### Commit 10a — "search filter" (t-50) ✓ executed 2026-11-17

> Split from the original commit 10 on 2026-11-17: t-53 asserts that the
> contrast suite runs in CI, and neither `pytest` nor CI exists yet (t-32,
> t-33). Running t-50 alone keeps the last design commit moving without
> inventing a second, throwaway test layout.
>
> Notes from execution:
> - `FlowLayout` gained `_visible_items()`: filtering hides cards instead of
>   deleting them, and the old layout gave every hidden card a slot, leaving
>   holes in the grid. `CardGrid.apply_filter(predicate)` wraps that and
>   returns the number of visible cards.
> - Room sections are tracked as `(section, grid)` pairs so hiding a section
>   is a one-liner; the filter runs again at the end of `_on_refreshed` so a
>   rebuild keeps the active query.
> - Enabling the field moved into `_set_view_controls_enabled()`; leaving the
>   connected state clears the text, which also drops the filter (§9.1).
> - The Energy view is intentionally not filtered: §8.8 covers devices and
>   scenes only.

**Wire search field**

1. Connect the header search `QLineEdit.textChanged` signal to a
   `filter_devices(query: str)` slot that shows/hides `DeviceCard`s and
   `SceneTile`s whose name contains the query (case-insensitive).
2. Hiding a card does not change room-section visibility if at least one card
   in the room matches; hide the whole room section only when zero cards match.
3. Clear filter on empty query; enable the field when a hub connects (it is
   deliberately disabled today, see commit 7's note) and keep it enabled across
   refreshes, re-applying the current query to newly built cards.
4. Gates: offscreen test; populate 3 cards with names "Bookshelf", "Desk lamp",
   "Ceiling"; filter "desk" → only "Desk lamp" visible.

#### Commit 10b — "contrast tests" (t-53) — moved to the tests/CI plan (blocked on t-32 and t-33)

1. Add `tests/test_contrast.py`: for every token pairing listed in
   `design-doc.md` §5.2, compute the WCAG relative-luminance contrast ratio
   and `assert ratio >= threshold` (4.5 for text, 3.0 for non-text).
2. Implement `wcag_contrast(hex_a: str, hex_b: str) -> float` as a pure
   function in `tests/test_contrast.py` or a shared helper (no extra
   dependencies beyond `pytest`).
3. Add the test to the CI workflow created by t-33.
4. Gates: `uv run pytest tests/test_contrast.py -v` passes; all 10 pairings
   from the spec assert at or above their threshold.

---

#### Cross-cutting gates (all commits)

- `uv run black .` — no reformatting needed.
- `uv run ruff check .` — zero warnings.
- `uv run mypy .` — must stay clean; t-31 removed the last 4 errors.
- Offscreen smoke test: `QT_QPA_PLATFORM=offscreen uv run python -m pytest`
  with any per-commit smoke tests listed above. Until t-32 adds `pytest` and
  `tests/`, the per-commit checks were ad-hoc offscreen scripts; keep using
  that pattern rather than introducing a second test layout.
- No `QCheckBox` or bare `QSlider` instance must remain in the final widget
  tree after commit 4.

---

### Plan: fix token generation (t-11)

> **Executed 2026-11-14** — commit (t-11). Replaced non-existent
> `dirigera.create_token` with `dirigera.hub.auth` challenge flow (`send_challenge`
> + `get_token`). Verified script usage, imports, unit mock flow, and gate checks.

Goal: Fix `generate_token.py` to use the working `dirigera.hub.auth` challenge-response
flow present in `dirigera` 1.6.1 instead of the non-existent `dirigera.create_token()`,
fulfilling req-12, and update documentation.

Affected files: `generate_token.py`, `README.md`, `doc/reqs.md`, `agent-notes/todo.md`

#### Commit 1 — "fix token generation" (t-11)

1. In `generate_token.py`:
   - Replace `import dirigera` with importing `ALPHABET`, `CODE_LENGTH`,
     `random_code`, `send_challenge`, and `get_token` from `dirigera.hub.auth`.
   - In `main()`:
     - Generate `code_verifier = random_code(ALPHABET, CODE_LENGTH)`.
     - Send challenge: `code = send_challenge(hub_ip, code_verifier)`.
     - Prompt user: `input("Press the pairing button on your Dirigera hub, then press ENTER...")`.
     - Fetch token: `token = get_token(hub_ip, code, code_verifier)`.
   - Keep existing banner formatting and error handling.
   - Update module docstring and usage messages to reflect the two-step pairing flow.
2. In `README.md`:
   - In "Getting Your Dirigera Token" (~lines 43–57), clarify that the user needs to
     press the pairing button on the hub and then press ENTER in the terminal.
3. Update tracking docs:
   - Mark `req-12` as implemented in `doc/reqs.md`.
   - Check off `t-11` in `agent-notes/todo.md`.
4. Verification:
   - `uv run python generate_token.py` with no args prints usage and exits with code 1.
   - `uv run python -c "import generate_token"` succeeds without error.
   - Run unit smoke test with mocked `send_challenge` and `get_token` to verify execution flow and output.
   - Gates: `uv run black .`, `uv run ruff check .`, `uv run mypy .`.

### Plan: Correctness & runtime bugs (t-1 … t-10)

> **Executed 2026-11-14** — commits `f0740fd` (t-1–t-4), `365ffce`
> (t-5–t-7), `c9290d2` (t-8–t-10). Offscreen smoke checks passed; mypy
> settled at 4 remaining errors, all t-31 scope.

Goal: Make the dashboard actually usable against a real hub: devices render,
toggle in the right direction, failed commands don't corrupt the UI, and
connect/refresh failures are visible instead of silent.
Supersedes the earlier "Fix the priority-A blockers" plan entry (t-1–t-4 and
t-11 content is folded in here / into the migration plan).

Affected files: `dashboard.py` (all three commits)

#### Commit 1 — "fix device attribute and room lookups" (t-1, t-2, t-3, t-4)

1. `add_light_controls` *(dashboard.py:403)*:
   `on_off_checkbox.setChecked(light.attributes.is_on)`
2. `add_light_controls` *(dashboard.py:404)* and `add_outlet_controls`
   *(dashboard.py:461)*: replace the `stateChanged` int/enum comparison with
   the `toggled(bool)` signal:
   ```python
   on_off_checkbox.toggled.connect(
       lambda checked: self.toggle_light(light, checked)
   )
   ```
   (analogous for `self.toggle_outlet(outlet, checked)`); handler signatures
   stay as they are.
3. `get_room_name` *(dashboard.py:559–562)*: replace the dict access with
   ```python
   room = getattr(device, "room", None)
   if room is None:
       return "Unknown Room"
   return room.name or "Unknown Room"
   ```
4. Gates: `uv run black . && uv run ruff check . && uv run mypy .`
   — mypy must drop to only the t-31 errors (`pyqtSignal` at dashboard.py:41
   and the two `clear_layout` guards, 4 errors total).
5. Offscreen smoke check (no hub): with `QT_QPA_PLATFORM=offscreen`, build a
   `Light` and an `Outlet` via `dict_to_light` / `dict_to_outlet` with a stub
   client, call `create_device_widget(device)` and `get_room_name(device)`;
   assert no `AttributeError` and that a checked toggle emits
   `toggle_light(light, True)`.

#### Commit 2 — "harden connect and refresh error handling" (t-5, t-6, t-7)

1. t-7 *(dashboard.py:305–358)*: in `refresh_devices`, fetch devices and
   scenes into local variables first; only clear the layouts and rebuild after
   both fetches succeed. On fetch failure: show the error and keep the current
   UI as-is.
2. t-6 *(dashboard.py:282–303)*: in `connect_to_hub`, after constructing
   `Hub(...)`, probe with `self.hub.get("/home")` inside the same `try`; only
   set the green status and enable Refresh when the probe succeeds. Note: at
   the time this was blocking I/O on the GUI thread by design; t-17 has since
   moved the whole probe into `ConnectWorker`.
3. t-5 *(dashboard.py:494–540)*: pass the owning control into each handler's
   lambda closure. On command failure: call `device.reload()` inside a guarded
   `try`, then resync the control from the reloaded attributes
   (checkbox from `.attributes.is_on`, sliders from
   `.attributes.light_level` / `.attributes.blinds_current_level`), and keep
   the existing `QMessageBox` warning.
4. Gates; extend the offscreen smoke test: stub client whose
   `set_light`/`set_light_level` raises, assert the checkbox/slider reverts to
   the device's real state and no unhandled exception escapes.

#### Commit 3 — "small dashboard cleanups" (t-8, t-9, t-10)

1. t-8 *(dashboard.py:480–482)*: render scene icons via a small helper, e.g.
   `icon.value.removeprefix("scenes_").replace("_", " ")`
   → "arrive home"; drop the label if the value is empty.
2. t-9 *(dashboard.py:41,250)*: rename `DiscoveryThread.finished` to
   `discovery_done` and update the `connect(...)` call in `discover_hubs`
   (removes the shadowing of the built-in `QThread.finished`).
3. t-10 *(dashboard.py:133,313,336)*: delete the unused `device_widgets`
   registry. Note: t-16 (live updates) will likely reintroduce a registry —
   if t-16 is scheduled first, skip t-10 instead and record the decision in
   `todo.md`.
4. Gates; mypy error count must stay at 4 (t-31 untouched); offscreen smoke
   test from commit 1 still passes.
