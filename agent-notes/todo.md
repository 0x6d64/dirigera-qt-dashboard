# Open topics

Working backlog for the Dirigera Qt dashboard. Derived from the initial repo review
and the `dirigera` 1.6.1 / Python 3.12 migration.

**Priority:** `A` = blocker (crash, broken core flow, security) · `B` = should fix
soon (correctness, maintainability) · `C` = nice to have.
**Effort:** `S` = under 1 h · `M` = 1–4 h · `L` = more than a day.
**IDs:** every task has a unique `t-<number>` ID. IDs are never reused; new tasks
take the next free number (see `AGENTS.md`).

## Correctness & runtime bugs

- [x] **t-1 [A·S]** Fix on/off toggle logic: `state == Qt.CheckState.Checked` compares `int` to an enum and is always `False` in PyQt6 6.12 (verified), so any toggle sends "off" — devices can never be switched on from the UI *(dashboard.py:404,461)*. Use the `toggled(bool)` signal or `Qt.CheckState(state)`.
- [x] **t-2 [A·S]** Fix `light.is_on` → `light.attributes.is_on` *(dashboard.py:403)* — raising `AttributeError` blocks every light widget.
- [x] **t-3 [A·S]** Fix `outlet.is_on` → `outlet.attributes.is_on` *(dashboard.py:460)* — same crash for outlets.
- [x] **t-4 [A·S]** Fix room lookup: `device.room` is a pydantic `Room`, not a dict, so `room.get("name")` raises *(dashboard.py:559)*. Use `device.room.name` and fall back to "Unknown Room" when `room is None`.
- [x] **t-5 [B·S]** Restore UI state when a command fails — checkboxes/sliders keep the new value after a failed PATCH *(dashboard.py:494–540)*. Reload the device or revert the control on error.
- [x] **t-6 [B·S]** `Hub()` construction never contacts the hub, so a wrong IP/token still shows "Connected" and only fails at refresh *(dashboard.py:282–303)*. Do a lightweight authenticated probe (e.g. `GET /home`) during connect.
- [x] **t-7 [B·S]** A failed Refresh leaves the dashboard blank because the lists are cleared before fetching *(dashboard.py:310–313)*. Build the new widgets first, then swap them in.
- [x] **t-8 [C·S]** Render scene icons as readable values instead of `Icon.SCENES_…` enum reprs *(dashboard.py:480)*, or drop the icon label.
- [x] **t-9 [C·S]** Rename `DiscoveryThread.finished` — it shadows the built-in `QThread.finished` signal *(dashboard.py:41)*.
- [x] **t-10 [C·S]** Remove the unused `device_widgets` registry or use it to update widgets in place instead of rebuilding *(dashboard.py:133,336)*.

## dirigera 1.6.1 migration follow-ups

- [x] **t-11 [A·S]** Fix `generate_token.py`: `dirigera.create_token()` does not exist (also not in 1.2.x) *(generate_token.py:32)*. Use the `dirigera.hub.auth` flow (`send_challenge` + `get_token`) or call the library's `generate-token` console script. Update README usage accordingly.
- [x] **t-12 [C·S]** Add blind up/down/stop controls using the new `BlindsStateEnum` / `Blind.set_state()`. *(superseded by t-45 for the card design; implemented there, capability guard fixed and verified offscreen)*
- [ ] **t-14 [C·M]** Add light color temperature / color controls (`set_color_temperature`, `set_light_color`). *(control logic; visual polish in t-42 and t-45)*
- [ ] **t-15 [C·L]** Expose adaptive light profiles via `hub.get_adaptive_profiles()` and `activate_adaptive_profile()`.
- [ ] **t-16 [C·L]** Replace manual Refresh with live updates using `Hub.create_event_listener()` (websocket). *(schedule after t-17)*

## UI responsiveness

- [x] **t-17 [B·M]** Move `connect_to_hub()` and `refresh_devices()` network I/O off the GUI thread *(dashboard.py:282-358)*. Use a worker `QThread` and disable buttons while loading. *(done: `ConnectWorker` / `RefreshWorker`; widgets are only touched in GUI-thread slots; `closeEvent` waits for a running worker)*
- [x] **t-18 [B·S]** Debounce slider commands: `valueChanged` currently fires one PATCH per tick *(dashboard.py:424,446)*. Send on `sliderReleased` or via a short `QTimer`. *(done: `LabeledSlider.committed` fires on release after a drag and after a 300 ms pause for track clicks, keys and wheel, which were previously never sent; unchanged values are not resent)*
- [x] **t-19 [C·S]** Preserve scroll position and avoid a full widget rebuild on Refresh.
- [x] **t-56 [A·S]** Auto refresh: nothing refreshes on a schedule, so values change only when the user presses Refresh — a light switched from the IKEA app or a wall switch stays wrong indefinitely, and the stale caption only appears after a *failed* refresh, so silently old data is never marked (`design-doc.md` §1 principle 1, §10.2). Add a `QTimer` calling `refresh_devices()` on a fixed interval (start with 30 s), paused while no hub is connected, while a fetch is already in flight (`_refresh_worker`), and while the window is minimised; show the interval and last-update time in the header or status line, and record the behaviour in `design-doc.md` §10.2. Distinct from t-16 (websocket push), which is unprioritised and which §10.3.1 says the design must not depend on. A poll triggers the full rebuild, so scroll position and in-progress slider drags are lost — either land t-19 first or skip the rebuild when the fetched data is unchanged.

## Network discovery

- [x] **t-20 [B·M]** Make discovery less dependent on MAC OUI guessing — `54:EF:44` is generic Espressif and the list can go stale *(network_discovery.py:13)*. Prefer an API probe or mDNS/SSDP, keeping OUI as a fallback.
- [ ] **t-21 [B·S]** Fix large-subnet scanning: for networks > 512 addresses only the first /24 is scanned *(network_discovery.py:108–111)*. Iterate all /24s with a total cap.
- [ ] **t-22 [C·S]** Make worker count and per-IP timeout configurable, and add a user-visible scan scope.
- [ ] **t-23 [C·S]** Avoid scanning VPN/virtual interfaces, or let the user pick the interface.
- [ ] **t-24 [C·S]** Deduplicate scanned networks — multiple interfaces can report the same subnet and double the scan time *(network_discovery.py:24–41)*.
- [ ] **t-25 [B·S]** Fix discovery UX: the progress dialog's Cancel button does nothing, and clicking Discover again spawns a second concurrent scan *(dashboard.py:237–253)*. Disable the button during the scan and wire Cancel to stop the thread. *(2026-11-21 review: Cancel now calls `QThread.terminate()`, which is unsafe for a thread running Python and leaves the scan's pool threads running — replace it with a cooperative stop flag checked by `discover_dirigera_hubs`)*

## Error handling & configuration

- [ ] **t-26 [B·M]** Replace broad `except Exception` blocks with specific handling plus logging *(dashboard.py:48,151,298,355,501–539)*. Discovery failures are currently swallowed and appear as "no hubs found".
- [x] **t-27 [B·S]** Surface `config.ini` parse/read errors instead of ignoring them silently *(dashboard.py:137–152)*.
- [x] **t-28 [B·S]** Resolve `config.ini` relative to the script/home directory instead of the current working directory *(dashboard.py:139)* — launching from elsewhere silently loses saved credentials.
- [x] **t-29 [B·M]** *(obsolete 2026-11-21: user decided plaintext `config.ini` is acceptable; req-7 withdrawn)* Stop storing the bearer token in plaintext `config.ini`; support an environment variable or OS keyring, with `config.ini` as fallback.
- [ ] **t-30 [C·S]** Validate the IP address format before attempting a connection *(dashboard.py:282)*.

## Review fixes (2026-11-21)

Found in the 2026-11-21 repo review and fixed on `improve-ui` the same day.

- [x] **t-57 [A·M]** Device commands (toggle, brightness, blind position and state) and the reload after a failure ran on the GUI thread and froze the window for up to the 10 s hub timeout (`req-4`; t-17 had only moved connect and refresh). *(done: `CommandWorker`; the card shows "Sending…" meanwhile)*
- [x] **t-58 [B·S]** A card's chip and footer did not follow a successful command: after switching a light on the chip still said "Off" until the next refresh. *(done: `DeviceCard.sync_from_device()` after every command)*
- [x] **t-59 [B·S]** Non-dimmable lights got a brightness slider at an invented 50 %: `light_level` is an Optional pydantic field, so `hasattr()` was always true. *(done)*
- [x] **t-60 [B·S]** The "Low battery" chip never appeared: the chip refresh in `DeviceCard.__init__` overwrote what the footer update had set. *(done: the battery check lives in `_update_status_chip`)*
- [x] **t-61 [A·S]** Closing the window during a hub call aborted the process: `closeEvent` waited 2 s per worker against a 10 s timeout, nothing checked `requestInterruption()`, and the discovery thread was not waited for (`req-14`). *(done: the window hides and the close completes once the last worker finishes)*
- [x] **t-62 [B·S]** Every finished discovery ran the cancel handler, because `QProgressDialog.close()` emits `canceled`; it called `terminate()` on the returning thread. *(done)*
- [x] **t-63 [C·S]** A refresh during scene activation dropped the "Activated"/"Failed" line, because the tile was looked up by object identity. *(done: matched by scene id)*
- [x] **t-64 [C·S]** Rooms were grouped by name (two rooms with the same name merged) and sorted case-sensitively; the fallback label was "Unknown Room". *(done)*
- [x] **t-65 [C·S]** Remove dead dashboard code: `DEFAULT_BRIGHTNESS`, `VIEW_*`, `handle_manual_ip`, `get_device_name`, `toggle_light`, `toggle_outlet`. *(done)*

## Design conformance gaps (deferred 2026-11-21)

Found by comparing the implementation with `doc/design-doc.md` in the 2026-11-21 review. Deliberately deferred: the design topic is revisited as a whole later, and several items need a decision in the doc first.

- [ ] **t-66 [B·M]** Replace modal `QMessageBox` errors for routine failures (device commands, refresh) with inline status (§8.14, §10.1). Coordinate with t-56, which must not raise a dialog every poll.
- [ ] **t-67 [B·S]** Truncate long device names with an ellipsis and tooltip; today a long name widens the card or clips (§8.1 rule 2, acceptance item 6).
- [ ] **t-68 [B·S]** Offline footer should read "Last seen <relative time>" from `device.last_seen`, not "Device unreachable" (§8.1 state 2).
- [ ] **t-69 [B·M]** Give the remaining device types real state instead of an empty card with an invented "Ready" chip: environment, motion, open/close, water, occupancy and light sensors, air purifiers, controllers (§8.5, principle 1). Add the missing types to the card sort map (§8.1 rule 3).
- [ ] **t-70 [C·S]** Chip text rules: no percentage in blind chips, sentence case, and no raw `device_type` captions such as "Open close sensor" (§8.2, acceptance item 4).
- [ ] **t-71 [C·S]** Scene tiles should use a 240 px minimum column width, not the 280 px card width (§8.10.1); give `CardGrid` a configurable minimum.
- [ ] **t-72 [C·S]** Window defaults: 1080 × 700 default, 640 × 480 minimum, no extra tab-layout margins outside the spacing scale (§4.1, §4.4). Related to t-54.
- [ ] **t-73 [C·S]** Refresh button shows "Refreshing…" while running (§10.2.1); first-load skeleton (§8.13).
- [ ] **t-74 [C·M]** Keyboard and accessibility: arrow keys in the segmented control, fixed width for metric values, accessible names on blind buttons and sliders, reduced-motion setting (§10.4.5, §10.5, §12.3).
- [ ] **t-75 [C·S]** Outlets with metering show their energy footer in the Rooms view, as electrical sensors do.
- [ ] **t-76 [C·S]** Fix the design doc itself. Done on `docs/design-doc-cleanup`: missing-doc references, stale `[open]`/`[verified]` tags, §5.2 pairings (now owned by the contrast test), chip radius vs height. Remaining: window size (1080 vs code 1000, with t-70), "Dirigera" as the app title against §2.2, and polling in §10.2 (see t-56).
- [ ] **t-77 [C·S]** Decide whether "automatic scenes" exist: the library's `SceneType` has no automatic type, so §8.10.5 and §9.3 cannot be built as written.
- [ ] **t-78 [C·S]** Verify on a real blind whether level 100 means open or closed; the card labels the slider "Open" and the chip says "Open" at 100 (§8.1).

## Typing, tests & CI

- [x] **t-31 [B·S]** Fix the remaining `mypy` errors: `pyqtSignal(list)` stub call *(dashboard.py:41)* and missing `None` guards in `clear_layout` *(dashboard.py:542–547)*. *(done: typed the signal with the same `# type: ignore[call-arg]` used by the other signals; `clear_layout` now takes `Optional[QLayoutItem]` into account and annotates its return; `mypy` is clean in all 17 files)*
- [x] **t-32 [B·M]** Add a small test suite (also adds `pytest` to the dev group): discovery helpers (`is_ikea_device`, network parsing with mocked `netifaces`) and mocked-hub smoke tests for `refresh_devices`.
- [x] **t-33 [B·S]** Add CI (GitHub Actions) running `ruff check`, `black --check`, `mypy` and `pytest` on Python 3.12.
- [ ] **t-34 [C·M]** Enable `check_untyped_defs` and annotate the GUI methods so mypy actually checks their bodies.
- [ ] **t-55 (partly done: see "pytest suite" plan; energy view and header scripts not ported) [B·M]** Create a small smoke test suite: port the ad-hoc offscreen scripts written during the design work (`t-1`, `t-2`, `t-12`, `t-17`, `t-46`, `t-47`, `t-48`, `t-49`) into `pytest` under `tests/`, with a shared `QT_QPA_PLATFORM=offscreen` `QApplication` fixture, silent `QMessageBox` stub, and the worker `settle()` helper. Complements t-32 (which adds `pytest` and covers discovery helpers plus `refresh_devices`) rather than replacing it: this one keeps the widget/state assertions that already exist as throwaway scripts. Depends on t-32 for the dev-dependency and layout; feeds t-33.

## Repository & documentation

- [x] **t-35 [B·S]** Get `refactor` merged: `master` is still at the initial commit while all work lives on `refactor`. *(done: `master` merged `rc1` as `4031d1e`, so all work through the design-doc backlog is on `master`; the working branch is now `improve-ui`)*
- [ ] **t-36 [C·S]** Update README: `netifaces2` requirement, Python 3.12/uv setup, and known discovery limitations. *(token-generation docs were updated in t-11; this covers the remaining gaps)*
- [ ] **t-37 [C·S]** Add a `[project.scripts]` entry point (e.g. `dirigera-dashboard = "main:main"`) so the app can be launched without `python main.py`.
- [ ] **t-38 [C·M]** Add package metadata (license expression, classifiers, keywords) to `pyproject.toml`.
- [ ] **t-39 [C·S]** Document the security model in the README: the hub uses a self-signed certificate and the `dirigera` library disables TLS verification, so the token should be treated as a network secret.

## Design document implementation (v1.0)

Design tasks build on each other. Recommended order: t-40 → t-43/t-44 → t-41/t-42 → t-45 → t-46/t-47/t-48 → t-49/t-51/t-52 → t-50/t-53. Run t-17 before t-49.

- [x] **t-40 [B·M]** Theme & design tokens: implement a central `theme.py` module with all colour tokens and spacing constants (`design-doc.md` §4.4, §5), and a `generate_stylesheet()` helper that produces a QSS string from those tokens. All other design tasks depend on this landing first.
- [x] **t-41 [B·M]** Custom switch widget: implement animated `QAbstractButton` toggle (44×24 px, 18 px thumb, 120 ms out-cubic animation, `thumb` pyqtProperty, accessible name) to replace the existing `QCheckBox` in device cards (`design-doc.md` §8.3). Depends on t-40.
- [x] **t-42 [B·M]** Redesigned slider: styled `QSlider` subclass/wrapper with fixed 13 px label column, 6 px track, 18 px thumb, 24 px minimum height, right-aligned fixed-width value label; avoid `QSlider:disabled::sub-page` (`design-doc.md` §8.4, §13.2). Depends on t-40. Subsumes the visual half of t-18 (debounce stays in t-18).
- [x] **t-43 [B·S]** Status chip component: `QLabel` subclass rendering a fully rounded 20 px chip in `ok`, `warn`, `danger`, or `neutral` token variant, for use in card headers and the connection bar (`design-doc.md` §8.2). Depends on t-40.
- [x] **t-44 [B·S]** Metric display component: composite widget showing a 28 px semibold value with a secondary unit label (caption size, `text-2`) and a caption beneath, for use in electrical-sensor and energy cards (`design-doc.md` §8.5). Depends on t-40.
- [x] **t-45 [B·L]** Redesigned device card: `DeviceCard` widget with min 280 px width, 10 px radius, 1 px border, 16 px padding; card sections — header row (name truncated with tooltip + type caption + status chip), control zone, footer caption; stable card order within rooms (lights → outlets → blinds → sensors → remotes) (`design-doc.md` §8.1). Integrates t-41, t-42, t-43; also covers the visual half of t-12 (blind buttons) and t-13 (electrical sensor metrics, t-44). Depends on t-40, t-41, t-42, t-43, t-44.
- [x] **t-13 [C·M]** ~~Give new `ElectricalSensor` devices a real widget~~ — **absorbed into t-45**: the electrical-sensor card body (using t-44 metrics) is part of the t-45 `DeviceCard` refactor. Close this when t-45 is done.
- [x] **t-46 [B·M]** Responsive card grid & room sections: replace current `QVBoxLayout`-of-`QGroupBox` layout with a width-driven flow grid (min 280 px cards, 16 px gaps) inside a `QScrollArea`; room labels use 13 px medium `text-2`; grid reflows at 760 px and 640 px breakpoints (`design-doc.md` §4.3, §11). Depends on t-45. *(done: `widgets/grid.py` `FlowLayout`; verified 3/2/1 columns at 1080/760/640 px)*
- [x] **t-47 [B·M]** Header bar & segmented view switcher: replace the current `QGroupBox`-based connection panel with a 56 px header containing the app title, hub status chip (t-43), 260 px search field, segmented Rooms/Scenes/Energy switcher, and ghost-style Refresh button; connection inputs move to the not-connected block (t-48) (`design-doc.md` §4.2, §8.6, §8.7). Depends on t-40, t-43. *(done: `widgets/segments.py` control; inputs stay in a temporary row until t-48, Energy segment disabled until t-49; narrow-width reflow recorded as t-54)*
- [x] **t-48 [B·M]** Not-connected state & centered connection block: when no hub is connected, show a centred card (heading, IP field, token field, Discover and Connect buttons) instead of empty tabs; disable search and view switcher (`design-doc.md` §8.12, §9.1). Depends on t-47. *(done: `widgets/connection.py` in a `QStackedWidget`; stale-data caption on refresh failure; search stays inert until t-50)*
- [x] **t-49 [B·M]** Energy view: third segment tab grouping power-metered outlets and `ElectricalSensor` devices by room, using t-44 metric widgets for live W, V, A, and total kWh; "No energy data" footer for unmetered outlets (`design-doc.md` §3.1, §8.11, §9.4). Depends on t-44, t-47. Schedule after t-17 (needs off-thread refresh). *(done: `widgets/energy.py`; tab bar hidden so the segmented switcher is the only navigation; no totals until §9.4 is decided)*
- [x] **t-50 [C·M]** Search/filter: wire the header search field (t-47) to filter device cards and scene tiles in real-time as the user types; filtering is case-insensitive on device/scene name (`design-doc.md` §8.8). Depends on t-46, t-47. *(done: `filter_devices()` matches the full name case-insensitively across Rooms and Scenes, hides room sections with no matches, and re-applies the active query after a rebuild; `FlowLayout` now skips hidden cards so filtered grids close up; the field enables on connect and clears on disconnect)*
- [x] **t-51 [C·M]** Redesigned scene tiles: 240 px min-width scene cards with a glyph, name, and primary Activate button; show inline "Activated" text in `ok` colour for ~2 s after activation, then revert — no modal dialog (`design-doc.md` §8.10). Depends on t-40, t-43. *(done: `widgets/scene.py`; inline result line; activation runs in `SceneTriggerWorker` off the GUI thread; 2 s auto-revert via `QTimer`)*
- [x] **t-52 [C·M]** SVG icon system: `icons.py` module with inline SVG strings (monoline, 24 px grid, 1.5 px stroke, `currentColor`), loaded via `QSvgRenderer` and recoloured by substituting the token colour at load time (`design-doc.md` §7.3). Depends on t-40. *(done: `widgets/icons.py`; glyphs for all device categories, scene icons, status glyphs, and battery levels; `SCENE_ICONS` maps hub icon enums to glyph names)*
- [x] **t-53 [C·S]** Automated contrast tests: `pytest` test asserting all colour-token pairings in `theme.py` meet WCAG 4.5:1 for text and 3:1 for non-text indicators; run as part of CI (t-33) (`design-doc.md` §5.2). Depends on t-40, t-33. *(moved out of the design-doc plan on 2026-11-21; to be scheduled with the tests/CI plan for t-32, t-33, t-55)*
- [ ] **t-54 [B·M]** Responsive header below 640 px: move the view switcher to a second header row so the window can reach the single-column breakpoint (`design-doc.md` §11 row 3). The fixed 56 px single-row header from t-47 sets a ~970 px minimum window width, which currently prevents t-46's 640 px reflow from being reached by resizing. Depends on t-47.
