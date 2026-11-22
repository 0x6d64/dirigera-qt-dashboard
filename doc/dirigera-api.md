# DIRIGERA library facts

What the `dirigera` library (version pinned in `uv.lock`; facts below were read in
1.6.1) exposes, and what it does not. This is reference material for implementers:
it describes the library, not the app's design (see `design-doc.md`) or its code.

Tags: `[lib]` read in the library source or its README; `[unverified]` needs real hub
data before it is relied on; `[opinion]` judgment, open to challenge; `[known]` general
knowledge, not re-tested. Sections 1 to 4 were written
without a hub and rest on the library source. Section 5 records what was later
observed on a real hub (2026-11-21 and 2026-11-22) and takes precedence where
they differ; section 4 gives a read-only way to dump payloads
(`tools/hub_get.py`).

## 1. Findings that affect the implementation

1. **Render controls from `capabilities.can_receive`, not from "attribute is not
   None".** `[lib]` Setters raise `AssertionError` when the capability is absent
   and `ValueError` when out of range. Deciding on
   `light_level is not None` is a proxy for the capability and will drift. Guard
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
   library doesn't expect yet"). Latency was checked on a real hub (2026-11-21): a
   refresh is fast enough, so the app uses `get_all_devices()` as it is; relevant
   to `req-2`. A cheaper refresh would use one raw
   `hub.get("/devices")` with per-device conversion in `try/except`; the library's
   `dict_to_*` converters are not documented as public API.
3. **Plugs with metering can split into two devices.** `[lib]` Some plugs (the README
   names GRILLPLATS) report energy as a separate `electricalSensor` that shares the
   outlet's `relation_id`, so it could be merged into the outlet card. The app does not do this: each device gets its own
   card, and the Energy view lists outlets and electrical sensors alike. The
   test hub's plug (INSPELNING) carries the energy attributes on the outlet itself (§5
   item 2), so no split plug has been seen. Other plugs: `[unverified]`.
4. **Controllers have no press state.** `[lib]` Button presses are not stored as
   device state. A remote tile can show name, battery and reachability, nothing
   interactive. Do not show a generic "healthy" mark for them.
5. **Live updates are partial and the listener blocks.** `[lib]`
   `create_event_listener()` calls `run_forever` and returns only when the socket
   closes. The hub closes idle connections itself. Events carry `type` and
   `data.id` plus only the changed attributes (README example: `{'isOn': False}`).
   Events during a reconnect are lost, so refetch state after reconnecting. To apply
   an event, either merge its camelCase keys or `reload()` the device (one
   `GET /devices/{id}`), which is simpler and robust. This is `t-16`. The app uses
   neither: any readable event triggers one coalesced full refresh (`EventWorker` in
   `workers.py`), so the event shapes are not relied on. It passes
   `reconnect=5` to `create_event_listener`, takes `(ws, message)` in `on_message`,
   and ends the listener with `stop_event_listener()`, which only closes an
   existing socket (a stop that comes before it exists is re-applied in `on_open`).
   Whether a dropped connection always fires `on_close`/`on_error` is
   `[unverified]` until the real-hub run.
6. **The shared `requests.Session` is not documented as thread-safe.** `[lib]` The
   hub object uses one session for all calls. Running slider commands, refreshes and
   the listener concurrently on one `Hub` is a risk `[unverified]`. Serialize hub
   calls through one worker or use one `Hub` per thread (`req-4` already forbids GUI
   thread I/O).
7. **Several displayed values have no documented unit or meaning.** `[lib]` See
   section 4, items 1 to 6. Do not invent labels for them.

## 2. What the API exposes

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
| 6 | `is_hidden` | Optional bool; the dashboard hides these devices like the IKEA app (owner decision, t-89) |
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
created in the IKEA app only. A light's state is the top-level field
`light.adaptive_profile` (`AdaptiveProfileState(id, active)`, JSON key
`adaptiveProfile`, `None` when the hub sends nothing), not on `light.attributes`.
`activate_adaptive_profile(id)` sends `PATCH /devices/{id}`
`[{"adaptiveProfile": {"id": id, "active": true}}]` without a capability check.
There is no library call to leave adaptive mode; its docstring says a manual
change ends it (unverified, see section 5 item 7). What ends it, verified on the
real hub 2026-11-22: `PATCH /devices/{id}`
`[{"adaptiveProfile": {"id": <active id>, "active": false}}]` through
`light.dirigera_client.patch` (the hub then reports `{}`; level and on-state stay). `reload()` to see the state.

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

## 3. Device to controls

What each device type can sensibly show. A control appears only if its capability is
in `capabilities.can_receive` (finding 1). Unreachable devices show "Offline" and
disable controls. Never show the raw `device_type` string; humanize it.

| # | Type | Shows | Notes |
| --- | --- | --- | --- |
| 1 | `light` | Switch; brightness 1 to 100; colour temperature (gradient slider); hue and saturation | 0 is rejected by the library, "off" goes through the switch. Colour controls belong in a secondary section. An "Adaptive" profile picker shows on lights that carry the `adaptiveProfile` state (`supports_adaptive`, §5 item 7; t-15). `QColor.hueF()` returns 0 to 1 and -1 for greys; convert to 0 to 360 |
| 2 | `outlet`, `electricalSensor` | Switch (outlets); power W, voltage V, current A, total kWh, only non-None values | Not merged by the app: a split-off sensor is its own read-only card (§1 item 3) |
| 3 | `blinds` | Position slider (0 to 100); Up, Stop, Down buttons; moving state as text | Do not label the ends "open" or "closed" until checked on a real blind |
| 4 | `airPurifier` | Fan speed (Off, Auto, 1–5 via `motorState`, §5 item 3); PM2.5; filter life and alarm | Child lock is deliberately not shown (owner decision 2026-11-21, `req-21`); status light is not planned. Fan control (t-80) and the filter footer and alarm chip (t-85) are implemented |
| 5 | `*Controller` | Name, type, battery, reachability | No press state exists; a live "pressed" flash needs the event shape (section 2.6 item 4) |
| 6 | `environmentSensor` | Temperature, humidity, PM2.5, VOC index, CO2: non-None only | Min/max PM2.5 in a tooltip. PM2.5 shows its band word, good, moderate or poor (t-88) |
| 7 | `motionSensor`, `occupancySensor` | State word ("Motion" / "Clear"); light level on motion sensors | |
| 8 | `openCloseSensor` | State word ("Open" / "Closed") | |
| 9 | `waterSensor` | State word; leak raises a danger state | |
| 10 | `lightSensor` | Illuminance | Unit undocumented |
| 11 | unknown | Name, humanized type, model, manufacturer | `get_all_devices()` cannot return unknown types in 1.6.1; keep the fallback anyway |
| 12 | scenes | Name, mapped glyph with generic fallback, Activate, inline result | Undo window and "next run" are possible from `undo_allowed_duration` and `triggers[]` but not planned |

## 4. Open questions and how to answer them

Answer from real data, not assumption. The dump below is read-only. Supply the token
through an environment variable and never print or commit it; strip serial numbers
before sharing output.

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
| 4 | Should `is_hidden` devices be shown? | Decided: no, hide them (t-89) |
| 5 | Values of `color_mode`, `room.icon`, `room.color` | Read from the dump; `room.color` is a hub colour name (e.g. `ikea_green_no_65`) mapped by its hue word to best-guess RGB values (t-86, `theme.ROOM_COLOURS`) |
| 6 | Does `light_level` stay populated while a light is off? | Answered by the owner: yes, the hub keeps the last value |
| 7 | Event shapes for button presses, add/remove, reachability | Not needed by t-16 (events are only a hint); record them from a debug log of the real-hub run if wanted |

## 5. Observed on a real hub (2026-11-21)

Read with `tools/hub_get.py` (GET only) on one home: 2 lights, 2 plugs (one
INSPELNING with metering), a STARKVIND air purifier, 2 VINDSTYRKA sensors, 3
remotes. Answers to section 4 where the data settles them:

1. **Raw `/devices` also lists the hub itself** (`deviceType` `gateway`).
   `get_all_devices()` filters it out, so the app never sees it.
2. **Metering plug (INSPELNING E2206)** carries energy on the outlet itself (no
   separate `electricalSensor`; question 3). Attributes: `currentActivePower` W,
   `currentVoltage` V, `currentAmps` A, `totalEnergyConsumed` kWh (with
   `totalEnergyConsumedLastUpdated`), `energyConsumedAtLastReset` kWh,
   `timeOfLastEnergyReset`. Usage since the last reset is
   `totalEnergyConsumed - energyConsumedAtLastReset`. **Reset (tried with the
   owner's permission):** `PATCH /devices/{id}` with
   `[{"attributes": {"energyConsumedAtLastReset": 0}}]` succeeds; the hub then
   stores the current `totalEnergyConsumed` in `energyConsumedAtLastReset` and
   sets `timeOfLastEnergyReset` to now. `totalEnergyConsumed` itself never
   resets, so "since reset" starts again at 0.
3. **Air purifier (STARKVIND E2007)**: `fanModeSequence` is
   `lowMediumHighAuto`; `currentPM25` is a plain integer. **Speed control
   (tried with the owner's permission):** `PATCH` of `motorState` sets the
   speed, and the hub derives `fanMode` from it:

   | Sent `motorState` | Read back | `fanMode` |
   | --- | --- | --- |
   | 0 | 0 | `off` |
   | 1 | 30 at that moment (the purifier picks its own speed) | `auto` |
   | 10, 20 | same | `low` (levels 1, 2) |
   | 30, 40 | same | `medium` (levels 3, 4) |
   | 50 | 50 | `high` (level 5) |

   So the IKEA app's five speeds are `motorState` 10 to 50 in steps of 10, 0 is
   off and 1 is auto. `currentPM25` read 0 while the fan was off. Filter:
   `filterLifetime` 259200 and `filterElapsedTime` 353271 are minutes (259200
   min = 180 days, STARKVIND's six-month filter), `filterAlarmStatus` true once
   elapsed passes lifetime (question 2, filter times). `motorRuntime` is also a
   counter, unit presumably minutes.
4. **Air quality sensor (VINDSTYRKA E2112)**: `currentTemperature`,
   `currentRH`, `currentPM25`, `vocIndex`; `maxMeasuredPM25` 999 and
   `minMeasuredPM25` 0 look like range bounds, not measured extremes.
5. **No history found.** `/home` returns `user`, `hub`, `devices`, `users`,
   `scenes`, `rooms`, `deviceSets`, `music`, `adaptiveProfiles`: no readings
   over time. Guessed routes (`/history`, `/devices/{id}/history`,
   `/devices/{id}/measurements`, `/statistics`, `/insights`, `/energy`,
   `/events`, …) return 404, and no public documentation names one. The IKEA
   app's graphs may come from IKEA's cloud or from a route not found yet. A web
   search (2026-11-21) found no history route either: the community projects
   (Prometheus exporter, Home Assistant, Raspberry Pi guides) poll the hub and
   store the readings themselves, and the IKEA apps pin their TLS certificate,
   which makes a traffic capture hard. Decision: history is dropped (t-82).
6. **A level sent to an off light is ignored.** Light Strip (`canReceive`
   `isOn`, `lightLevel`, `colorHue`, `colorSaturation`), tested 2026-11-21 with
   a 6 s wait before each read (the hub applies changes with a delay of a few
   seconds, so an immediate read shows the old value): `lightLevel` alone
   leaves the light off and the level unchanged; `isOn: true` and `lightLevel`
   in one request switches it on but keeps the old level; `isOn: true` followed
   at once by a separate `lightLevel` request works, and the reverse order
   does not. Colour and temperature commands to an off light were not tested.
7. **Adaptive profiles (read-only check E1, 2026-11-22).** `/home` returns 3
   `adaptiveProfiles`, every one with a `name`; each has `id`, `name` and
   `adaptiveSchedule` (entries with `startTime`, `lightLevel`,
   `colorTemperature`). Nothing in `/home` links lights to profiles.
   `/devices` carries a top-level `adaptiveProfile` key for **every** light: one
   light reports `{"id": "<uuid>", "active": true}` (it follows a profile
   although it is switched off), another reports `{}` (no profile). So the
   state does come with a normal refresh. Lights' `canReceive` lists
   `colorHue`, `colorSaturation`, `customName`, `isOn`, `lightLevel`: there is
   no `adaptiveProfile` capability, and the light that follows a profile has no
   `colorTemperature` capability. Rule used by `supports_adaptive`
   (`adaptive.py`): a `light` that carries the `adaptive_profile` field with a
   state object (the hub sent the key), or that already reports an active
   profile. **Unknown:** whether a profile can be activated on the light that
   reports `{}`; that light also gets the picker, and a failed activation
   shows the card error. **Pending owner permission (hub writes, not run):**
   W1 (what activation does to an off light, level and warmth; which manual
   changes end a profile).
   **W2 and activation on the Light Strip (owner, 2026-11-22, one light, model
   "TRADFRI Driver 30W": brightness only, no warmth; same for all the owner's
   lights, whose `canReceive` is `customName`, `isOn`, `lightLevel`,
   `colorHue`, `colorSaturation`).** Start: on, level 100, `adaptiveProfile`
   `{}`. Activation, `PATCH /devices/{id}` `[{"adaptiveProfile": {"id": <profile
   id>, "active": true}}]`, was accepted; about 6 s later the light reported
   `{"id": <id>, "active": true}` and its level had moved from 100 to 98, so a
   light without warmth accepts a profile and follows it. W2a, the same
   payload with `"active": false` (id kept), was accepted; about 6 s later
   `adaptiveProfile` was `{}` and level and on-state were unchanged (on, 98).
   **That payload leaves adaptive mode**; the id-less variant (W2b) was not
   needed and not tried. Side observation, not investigated: a later `PATCH`
   `[{"lightLevel": 100}]`, sent twice with an 8 s wait, was accepted but the
   strip stayed at 98.
