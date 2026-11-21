# Requirements

All requirements get a unique identifier `req-<number>`. Numbers are never
reused.

## Explicit

- **req-13** — The dashboard must refresh device state automatically; a manual
  Refresh click must not be the only way displayed values update. *(user,
  2026-11-15; t-56, implemented)*
- **req-15** — The air purifier card must let the user set the fan speed: off,
  auto, or a fixed level. *(user, 2026-11-21; t-80, open)*
- **req-16** — The air purifier's PM2.5 reading must be displayed. *(user,
  2026-11-21; t-81, implemented by t-69)*
- **req-17** — Historical air quality readings should be shown if the hub
  provides them; whether it does is to be explored. *(user, 2026-11-21; t-82,
  open)*
- **req-18** — The Energy tab must offer the metering plugs' reset of
  accumulated usage. *(user, 2026-11-21; t-83, open)*
- **req-19** — Metering plugs must show the cost of their usage, from a
  configurable price per kWh and currency; when unset the defaults are Romanian
  prices (RON). *(user, 2026-11-21; t-84, open)*
- **req-20** — The air purifier card must show the filter's health and when the
  filter needs changing. *(user, 2026-11-21; t-85, open)*

## Inferred

Derived from the backlog (`agent-notes/todo.md`), code review, and work done
during implementation. Each entry cites its origin.

- **req-1** — The app must report "Connected" only after the credentials have
  been verified with a live hub call; constructing the `Hub` object alone
  proves nothing (it never contacts the hub). *(t-6, implemented)*
- **req-2** — A failed refresh must keep the current dashboard view; layouts
  may only be cleared and rebuilt after devices and scenes have both been
  fetched successfully. *(t-7, implemented)*
- **req-3** — After a failed device command, the affected control
  (switch/slider) must be resynchronized with the device's actual state so
  the UI reflects reality, not the intended value. *(t-5, implemented;
  wording updated after the t-45 card refactor replaced checkboxes with
  switches)*
- **req-4** — Blocking network I/O must run in a worker thread, never on the
  GUI thread. *(t-17 for connect and refresh, t-57 for device commands,
  implemented; also stated as a rule in `AGENTS.md`)*
- **req-5** — Hub discovery must not depend solely on a static MAC OUI list;
  hubs must be identified by their unauthenticated API response, with the OUI
  list kept only as a fallback. *(t-20, implemented)*
- **req-6** — Slider-based controls must not send one hub command per tick;
  commands must be debounced or sent on release, and every user input path
  (drag, track click, arrow/Page keys, mouse wheel) must send its value.
  *(t-18, implemented: `LabeledSlider.committed` fires on release after a drag
  and after a 300 ms pause for every other change)*
- **req-7** — *Obsolete (2026-11-21, user decision).* The hub token must not be
  stored in plaintext as the primary mechanism. Dropped: a gitignored
  `config.ini` is accepted for this single-user desktop tool. *(t-29, obsolete)*
- **req-8** — Saved credentials must resolve relative to the script/home
  directory, not the current working directory, so launching from elsewhere
  does not silently lose them. *(t-28, implemented)*
- **req-9** — Verification must be possible without a real hub: offscreen
  smoke tests (`QT_QPA_PLATFORM=offscreen`, stub client subclassing
  `AbstractSmartHomeHub`). *(established during t-1…t-10 execution)*
- **req-10** — Discovery must cover all local subnets, not just the first
  /24 of a large network. *(t-21, implemented)*
- **req-11** — Only one discovery scan may run at a time, and the progress
  dialog's Cancel button must actually stop the scan. *(t-25, implemented)*
- **req-12** — Token generation must use the auth flow that actually exists
  in the installed `dirigera` version (currently the `dirigera.hub.auth`
  challenge flow). *(t-11, implemented)*
- **req-14** — Closing the window while hub calls are in flight must not
  crash or lose the call; the app may finish them before it exits, but no
  running worker thread may be destroyed. *(t-61, implemented)*
