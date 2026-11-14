# Open topics

Working backlog for the Dirigera Qt dashboard. Derived from the initial repo review
and the `dirigera` 1.6.1 / Python 3.12 migration.

**Priority:** `A` = blocker (crash, broken core flow, security) · `B` = should fix
soon (correctness, maintainability) · `C` = nice to have.
**Effort:** `S` = under 1 h · `M` = 1–4 h · `L` = more than a day.

## Correctness & runtime bugs

- [ ] **[A·S]** Fix on/off toggle logic: `state == Qt.CheckState.Checked` compares `int` to an enum and is always `False` in PyQt6 6.12 (verified), so any toggle sends "off" — devices can never be switched on from the UI *(dashboard.py:404,461)*. Use the `toggled(bool)` signal or `Qt.CheckState(state)`.
- [ ] **[A·S]** Fix `light.is_on` → `light.attributes.is_on` *(dashboard.py:403)* — raising `AttributeError` blocks every light widget.
- [ ] **[A·S]** Fix `outlet.is_on` → `outlet.attributes.is_on` *(dashboard.py:460)* — same crash for outlets.
- [ ] **[A·S]** Fix room lookup: `device.room` is a pydantic `Room`, not a dict, so `room.get("name")` raises *(dashboard.py:559)*. Use `device.room.name` and fall back to "Unknown Room" when `room is None`.
- [ ] **[B·S]** Restore UI state when a command fails — checkboxes/sliders keep the new value after a failed PATCH *(dashboard.py:494–540)*. Reload the device or revert the control on error.
- [ ] **[B·S]** `Hub()` construction never contacts the hub, so a wrong IP/token still shows "Connected" and only fails at refresh *(dashboard.py:282–303)*. Do a lightweight authenticated probe (e.g. `GET /home`) during connect.
- [ ] **[B·S]** A failed Refresh leaves the dashboard blank because the lists are cleared before fetching *(dashboard.py:310–313)*. Build the new widgets first, then swap them in.
- [ ] **[C·S]** Render scene icons as readable values instead of `Icon.SCENES_…` enum reprs *(dashboard.py:480)*, or drop the icon label.
- [ ] **[C·S]** Rename `DiscoveryThread.finished` — it shadows the built-in `QThread.finished` signal *(dashboard.py:41)*.
- [ ] **[C·S]** Remove the unused `device_widgets` registry or use it to update widgets in place instead of rebuilding *(dashboard.py:133,336)*.

## dirigera 1.6.1 migration follow-ups

- [ ] **[A·S]** Fix `generate_token.py`: `dirigera.create_token()` does not exist (also not in 1.2.x) *(generate_token.py:32)*. Use the `dirigera.hub.auth` flow (`send_challenge` + `get_token`) or call the library's `generate-token` console script. Update README usage accordingly.
- [ ] **[C·S]** Add blind up/down/stop controls using the new `BlindsStateEnum` / `Blind.set_state()`.
- [ ] **[C·M]** Give new `ElectricalSensor` devices a real widget (power, voltage, energy) instead of the generic "✓" branch *(dashboard.py:391)*.
- [ ] **[C·M]** Add light color temperature / color controls (`set_color_temperature`, `set_light_color`).
- [ ] **[C·L]** Expose adaptive light profiles via `hub.get_adaptive_profiles()` and `activate_adaptive_profile()`.
- [ ] **[C·L]** Replace manual Refresh with live updates using `Hub.create_event_listener()` (websocket).

## UI responsiveness

- [ ] **[B·M]** Move `connect_to_hub()` and `refresh_devices()` network I/O off the GUI thread *(dashboard.py:282–358)*. Use a worker `QThread` and disable buttons while loading.
- [ ] **[B·S]** Debounce slider commands: `valueChanged` currently fires one PATCH per tick *(dashboard.py:424,446)*. Send on `sliderReleased` or via a short `QTimer`.
- [ ] **[C·S]** Preserve scroll position and avoid a full widget rebuild on Refresh.

## Network discovery

- [ ] **[B·M]** Make discovery less dependent on MAC OUI guessing — `54:EF:44` is generic Espressif and the list can go stale *(network_discovery.py:13)*. Prefer an API probe or mDNS/SSDP, keeping OUI as a fallback.
- [ ] **[B·S]** Fix large-subnet scanning: for networks > 512 addresses only the first /24 is scanned *(network_discovery.py:108–111)*. Iterate all /24s with a total cap.
- [ ] **[C·S]** Make worker count and per-IP timeout configurable, and add a user-visible scan scope.
- [ ] **[C·S]** Avoid scanning VPN/virtual interfaces, or let the user pick the interface.
- [ ] **[C·S]** Deduplicate scanned networks — multiple interfaces can report the same subnet and double the scan time *(network_discovery.py:24–41)*.
- [ ] **[B·S]** Fix discovery UX: the progress dialog's Cancel button does nothing, and clicking Discover again spawns a second concurrent scan *(dashboard.py:237–253)*. Disable the button during the scan and wire Cancel to stop the thread.

## Error handling & configuration

- [ ] **[B·M]** Replace broad `except Exception` blocks with specific handling plus logging *(dashboard.py:48,151,298,355,501–539)*. Discovery failures are currently swallowed and appear as "no hubs found".
- [ ] **[B·S]** Surface `config.ini` parse/read errors instead of ignoring them silently *(dashboard.py:137–152)*.
- [ ] **[B·S]** Resolve `config.ini` relative to the script/home directory instead of the current working directory *(dashboard.py:139)* — launching from elsewhere silently loses saved credentials.
- [ ] **[B·M]** Stop storing the bearer token in plaintext `config.ini`; support an environment variable or OS keyring, with `config.ini` as fallback.
- [ ] **[C·S]** Validate the IP address format before attempting a connection *(dashboard.py:282)*.

## Typing, tests & CI

- [ ] **[B·S]** Fix the remaining `mypy` errors: `pyqtSignal(list)` stub call *(dashboard.py:41)* and missing `None` guards in `clear_layout` *(dashboard.py:542–547)*.
- [ ] **[B·M]** Add a small test suite (also adds `pytest` to the dev group): discovery helpers (`is_ikea_device`, network parsing with mocked `netifaces`) and mocked-hub smoke tests for `refresh_devices`.
- [ ] **[B·S]** Add CI (GitHub Actions) running `ruff check`, `black --check`, `mypy` and `pytest` on Python 3.12.
- [ ] **[C·M]** Enable `check_untyped_defs` and annotate the GUI methods so mypy actually checks their bodies.

## Repository & documentation

- [ ] **[B·S]** Get `refactor` merged: `master` is still at the initial commit while all work lives on `refactor`.
- [ ] **[B·S]** Update README: `netifaces2` requirement, Python 3.12/uv setup, working token-generation command, and the known discovery limitations.
- [ ] **[C·S]** Add a `[project.scripts]` entry point (e.g. `dirigera-dashboard = "main:main"`) so the app can be launched without `python main.py`.
- [ ] **[C·M]** Add package metadata (license expression, classifiers, keywords) to `pyproject.toml`.
- [ ] **[C·S]** Document the security model in the README: the hub uses a self-signed certificate and the `dirigera` library disables TLS verification, so the token should be treated as a network secret.
