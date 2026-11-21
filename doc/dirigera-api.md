# DIRIGERA library facts

What the `dirigera` library (version pinned in `uv.lock`; facts below were read in
1.6.1) exposes, and what it does not. This is reference material for implementers:
it describes the library, not the app's design (see `design-doc.md`) or its code.

Tags: `[lib]` read in the library source or its README; `[unverified]` needs real hub
data before it is relied on; `[opinion]` judgment, open to challenge; `[known]` general
knowledge, not re-tested. No live hub was
available when this was written, so nothing here was observed on real payloads.
Section 4 gives a read-only way to dump them.

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
   library doesn't expect yet"). Measure latency on the real hub before optimizing
   `[unverified]`; relevant to `req-2`. A cheaper refresh would use one raw
   `hub.get("/devices")` with per-device conversion in `try/except`; the library's
   `dict_to_*` converters are not documented as public API.
3. **Plugs with metering can split into two devices.** `[lib]` Some plugs (the README
   names GRILLPLATS) report energy as a separate `electricalSensor` that shares the
   outlet's `relation_id`. Merge it into the outlet card by `relation_id`; do not
   render a second tile. Other plugs (INSPELNING) carry the energy attributes on the
   outlet itself. Which case a given plug is: `[unverified]`.
4. **Controllers have no press state.** `[lib]` Button presses are not stored as
   device state. A remote tile can show name, battery and reachability, nothing
   interactive. Do not show a generic "healthy" mark for them.
5. **Live updates are partial and the listener blocks.** `[lib]`
   `create_event_listener()` calls `run_forever` and returns only when the socket
   closes. The hub closes idle connections itself. Events carry `type` and
   `data.id` plus only the changed attributes (README example: `{'isOn': False}`).
   Events during a reconnect are lost, so refetch state after reconnecting. To apply
   an event, either merge its camelCase keys or `reload()` the device (one
   `GET /devices/{id}`), which is simpler and robust. This is `t-16`.
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

## 3. Device to controls

What each device type can sensibly show. A control appears only if its capability is
in `capabilities.can_receive` (finding 1). Unreachable devices show "Offline" and
disable controls. Never show the raw `device_type` string; humanize it.

| # | Type | Shows | Notes |
| --- | --- | --- | --- |
| 1 | `light` | Switch; brightness 1 to 100; colour temperature (gradient slider); hue and saturation | 0 is rejected by the library, "off" goes through the switch. Colour controls belong in a secondary section. `QColor.hueF()` returns 0 to 1 and -1 for greys; convert to 0 to 360 |
| 2 | `outlet`, `electricalSensor` | Switch (outlets); power W, voltage V, current A, total kWh, only non-None values | Merge a sensor into the outlet with the same `relation_id`; standalone read-only tile only if no outlet matches |
| 3 | `blinds` | Position slider (0 to 100); Up, Stop, Down buttons; moving state as text | Do not label the ends "open" or "closed" until checked on a real blind |
| 4 | `airPurifier` | Fan mode as segments; PM2.5; filter progress; alarm badge; child lock, status light | Not implemented. `motor_state` semantics and units are `[unverified]`; hide until checked |
| 5 | `*Controller` | Name, type, battery, reachability | No press state exists; a live "pressed" flash needs the event shape (section 2.6 item 4) |
| 6 | `environmentSensor` | Temperature, humidity, PM2.5, VOC index, CO2: non-None only | Min/max PM2.5 in a tooltip. No air-quality colour bands until a standard is chosen |
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
| 4 | Should `is_hidden` devices be shown? | Compare the dump with what the IKEA app lists |
| 5 | Values of `color_mode`, `room.icon`, `room.color` | Read from the dump |
| 6 | Does `light_level` stay populated while a light is off? | Read from the dump with a light off |
| 7 | Event shapes for button presses, add/remove, reachability | Log raw events from a listener while pressing a remote |

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
   `timeOfLastEnergyReset`. `canReceive` contains `energyConsumedAtLastReset`,
   so the reset is a `PATCH` of that attribute; the value to send (presumably
   0) is unverified, and it was not tried because it would erase the user's
   counter. Usage since the last reset is
   `totalEnergyConsumed - energyConsumedAtLastReset`.
3. **Air purifier (STARKVIND E2007)**: `fanMode` `low` with
   `fanModeSequence` `lowMediumHighAuto` and `motorState` 20, so modes map to
   motor-state steps of 10. `currentPM25` is a plain integer. Filter:
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
   app's graphs may come from IKEA's cloud or from a route not found yet.
