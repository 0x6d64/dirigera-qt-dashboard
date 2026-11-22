# Text for the upstream issues and PR

Drafts, not yet posted. Target repo: `Leggin/dirigera`, base version 1.6.1.
Check the open issues and PRs again before posting (none were open on
2026-11-22). The maintainer's usual flow is an issue first, then a PR.
Issue 2 (energy reset) goes first; issue 1 (leave adaptive) is lower priority.
**Open decision:** whether `reset_energy_counter()` is offered on
`ElectricalSensor` at all (see README, open points); the texts below still
assume both classes.

## Issue 1: leave an adaptive profile

**Title:** Add a way to take a light out of adaptive mode

`Light.activate_adaptive_profile()` (#144) puts a light into adaptive mode, but
there is no call that takes it out again. The docstring says that changing the
light manually ends adaptive mode. I have not tested which manual changes do
that, but the hub also accepts an explicit request.

Tested on a real hub, one light (model "TRADFRI Driver 30W", brightness only):

```text
PATCH /devices/<device-id>
[{"adaptiveProfile": {"id": "<profile-id>", "active": false}}]
```

- The hub accepted it. About 6 s later the light reported `adaptiveProfile: {}`.
- Light level and on/off state did not change.
- I did not try the same request without the id.

Proposal: `Light.leave_adaptive_profile()`. It sends the request above with the id
from `light.adaptive_profile` and does nothing if the light is not known to
follow a profile (call `reload()` first). Happy to open a PR.

## Issue 2: reset the energy counter

**Title:** Add a way to reset the "since last reset" energy counter

`Outlet` and `ElectricalSensor` expose `energy_consumed_at_last_reset` and
`time_of_last_energy_reset`, but the IKEA app's "reset" has no counterpart in the
library.

Tested on a real hub, one INSPELNING plug (energy attributes on the outlet):

```text
PATCH /devices/<device-id>
[{"attributes": {"energyConsumedAtLastReset": 0}}]
```

- The hub accepted it. 3 s later `energyConsumedAtLastReset` equalled
  `totalEnergyConsumed` (19.026) and `timeOfLastEnergyReset` was set to now.
- `totalEnergyConsumed` did not change; it never resets.
- The plug lists `energyConsumedAtLastReset` in `canReceive`.

Proposal: `reset_energy_counter()` on `Outlet` and `ElectricalSensor`, guarded by
that capability like the other setters. Not tested: GRILLPLATS (the dump in #132
lists only `customName` in `canReceive` for its sensor, so the guard would refuse
there) and other plug models.

## Pull request

**Title:** Add leave_adaptive_profile and reset_energy_counter

Adds two small calls the hub supports but the library lacks. Both send one
`PATCH /devices/{id}` through the existing client.

- `Light.leave_adaptive_profile()`: sends
  `[{"adaptiveProfile": {"id": <active id>, "active": false}}]`, then sets
  `adaptive_profile` to an empty `AdaptiveProfileState`. No request if the light
  is not in adaptive mode.
- `Outlet.reset_energy_counter()` and `ElectricalSensor.reset_energy_counter()`:
  send `[{"attributes": {"energyConsumedAtLastReset": 0}}]`; raise
  `AssertionError` without the `energyConsumedAtLastReset` capability (same style
  as `set_name`). Local attributes are not changed because the hub sets both the
  value and the time; call `reload()`.

Tests use `FakeDirigeraHub`, same style as the existing ones (6 new tests). The
README adaptive section also needs one sentence on the new call and the energy
table one line on the reset; this is not in the patch yet.

Tested on real hardware as described in the issues. Closes #<issue 1>, #<issue 2>.
