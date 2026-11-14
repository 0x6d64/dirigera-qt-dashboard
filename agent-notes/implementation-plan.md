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

### Plan: fix token generation (t-11)

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
- t-11 is independent and can be committed at any time.

## Done

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
