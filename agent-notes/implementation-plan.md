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

### Plan: dirigera 1.6.1 migration follow-ups (t-12 … t-16)

Goal: Adopt the capabilities added in `dirigera` 1.6.1 so the dashboard covers
the new device types and controls.

Affected files: `dashboard.py`

#### Commit 1 — "device widgets for new device classes" (t-12, t-13)

1. t-12: in `add_blind_controls` *(dashboard.py:435–455)*, add Up / Down /
   Stop `QPushButton`s wired to a new
   `set_blind_state(blind, state: BlindsStateEnum)` handler calling
   `blind.set_state(state)` (existing warning-on-error pattern). Import
   `BlindsStateEnum` from `dirigera.devices.blinds`. Enable the buttons only
   when `"blindsState" in blind.capabilities.can_receive`.
2. t-13 *(dashboard.py:391)*: add an `electricalSensor` branch to
   `create_device_widget` that calls a new read-only
   `add_electrical_sensor_controls(layout, device)` showing labels from
   `ElectricalSensorAttributes`: `current_active_power` (W),
   `current_voltage` (V), `current_amps` (A), `total_energy_consumed` (kWh),
   `–` when `None`. No controls — the device cannot receive anything.
3. Gates; offscreen smoke test with `dict_to_electrical_sensor` and a `Blind`
   whose `capabilities.can_receive` contains `blindsState`.

#### Commit 2 — "light color and temperature controls" (t-14)

1. In `add_light_controls`, when
   `"colorTemperature" in light.capabilities.can_receive` and min/max bounds
   are present: add a color-temperature slider spanning
   `attributes.color_temperature_min` … `color_temperature_max` (Kelvin; the
   library normalizes mireds internally) and send on `sliderReleased` via
   `light.set_color_temperature(value)`.
2. When `"colorHue"` / `"colorSaturation"` are in `can_receive`: add a
   "Color…" button opening `QColorDialog`; convert the picked color with
   `color.getHsvF()` (hue × 360, saturation × 100) and call
   `light.set_light_color(hue, saturation)`.
3. Every control behind a capability check — the library raises
   `AssertionError` otherwise.
4. Gates; offscreen smoke test invoking the handlers against a stubbed light.

#### Commit 3 — "adaptive light profiles" (t-15) — schedule after t-17 if possible

1. In `refresh_devices`, fetch `self.adaptive_profiles =
   self.hub.get_adaptive_profiles()` inside a guarded `try` (empty list on
   failure — older hubs don't expose profiles).
2. In `add_light_controls`, if profiles exist: add a `QComboBox` per light
   with "(manual)" plus profile names, preselecting the profile from
   `light.adaptive_profile.id` (new 1.6.1 field).
3. Handler `set_light_profile(light, profile_id)`: activating calls
   `light.activate_adaptive_profile(profile_id)` then `light.reload()`;
   choosing "(manual)" is a no-op (any manual change already ends adaptive
   mode).
4. Gates; offscreen smoke test with a stub hub returning one profile.
5. Note: adds blocking calls to the existing refresh flow — acceptable only
   because t-17 will move all of it into a worker; execute t-17 before this
   commit if scheduling allows.

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

- Execute the "Correctness & runtime bugs" plan first: t-17 (worker threads)
  unblocks t-15/t-16, and t-1–t-4 must land before any real-hub testing.

---

### Plan: design document v1.0 implementation (t-40 … t-53)

Goal: Implement the visual design described in `doc/design-doc.md` v1.0 —
introducing a token-driven theme, purpose-built components, a redesigned card
and grid layout, a header bar with segmented navigation, and three views
(Rooms, Scenes, Energy).

Affected files: `theme.py` (new), `widgets/switch.py` (new),
`widgets/slider.py` (new), `widgets/chip.py` (new), `widgets/metric.py` (new),
`widgets/card.py` (new), `widgets/icons.py` (new), `dashboard.py` (heavily
refactored), `main.py` (stylesheet injection)

#### Ordering note

Execute commits in this order. Each commit is independently mergeable but
relies on the files introduced before it:
`t-40 → t-43 + t-44 → t-41 + t-42 → t-45 → t-46 + t-47 + t-48 → t-49 + t-51 + t-52 → t-50 + t-53`

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

#### Commit 3 — "custom switch and slider widgets" (t-41, t-42)

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

#### Commit 4 — "redesigned device card" (t-45, closes t-13)

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
3. Gates: offscreen smoke tests for each device type; assert no
   `QCheckBox` or bare `QSlider` remains in the widget tree.

---

#### Commit 5 — "responsive card grid and room sections" (t-46)

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

#### Commit 6 — "header bar and segmented view switcher" (t-47)

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

#### Commit 7 — "not-connected state and connection block" (t-48)

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

#### Commit 8 — "Energy view" (t-49)

*Schedule after t-17 (off-thread refresh) to avoid blocking the GUI thread.*

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

#### Commit 9 — "scene tiles and SVG icon system" (t-51, t-52)

**New file: `widgets/icons.py`; refactor scenes layout in `dashboard.py`**

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

#### Commit 10 — "search filter and contrast tests" (t-50, t-53)

**Wire search field; add test suite entry**

**t-50 — search filter**

1. Connect the header search `QLineEdit.textChanged` signal to a
   `filter_devices(query: str)` slot that shows/hides `DeviceCard`s and
   `SceneTile`s whose name contains the query (case-insensitive).
2. Hiding a card does not change room-section visibility if at least one card
   in the room matches; hide the whole room section only when zero cards match.
3. Clear filter on empty query.
4. Gates: offscreen test; populate 3 cards with names "Bookshelf", "Desk lamp",
   "Ceiling"; filter "desk" → only "Desk lamp" visible.

**t-53 — contrast tests**

1. Add `tests/test_contrast.py`: for every token pairing listed in
   `design-doc.md` §5.2, compute the WCAG relative-luminance contrast ratio
   and `assert ratio >= threshold` (4.5 for text, 3.0 for non-text).
2. Implement `wcag_contrast(hex_a: str, hex_b: str) -> float` as a pure
   function in `tests/test_contrast.py` or a shared helper (no extra
   dependencies beyond `pytest`).
3. Gates: `uv run pytest tests/test_contrast.py -v` passes; all 10 pairings
   from the spec assert at or above their threshold.

---

#### Cross-cutting gates (all commits)

- `uv run black .` — no reformatting needed.
- `uv run ruff check .` — zero warnings.
- `uv run mypy .` — error count must not increase above the t-31 baseline (4).
- Offscreen smoke test: `QT_QPA_PLATFORM=offscreen uv run python -m pytest`
  with any per-commit smoke tests listed above.
- No `QCheckBox` or bare `QSlider` instance must remain in the final widget
  tree after commit 4.


## Done

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
   set the green status and enable Refresh when the probe succeeds. Note: this
   is still blocking I/O on the GUI thread by design — t-17 will move it into
   a worker; do not solve that here.
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
