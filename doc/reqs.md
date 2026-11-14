# Requirements

All requirements get a unique identifier `req-<number>`. Numbers are never
reused.

## Explicit

*(none yet — user-stated requirements go here)*

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
  (checkbox/slider) must be resynchronized with the device's actual state so
  the UI reflects reality, not the intended value. *(t-5, implemented)*
- **req-4** — Blocking network I/O must run in a worker thread, never on the
  GUI thread. *(t-17; also stated as a rule in `AGENTS.md`)*
- **req-5** — Hub discovery must not depend solely on a static MAC OUI list;
  hubs must be identified by their unauthenticated API response, with the OUI
  list kept only as a fallback. *(t-20, implemented)*
- **req-6** — Slider-based controls must not send one hub command per tick;
  commands must be debounced or sent on release. *(t-18, open)*
- **req-7** — The hub token must not be stored in plaintext as the primary
  mechanism; an environment variable or OS keyring is preferred, with
  `config.ini` as fallback. *(t-29, open)*
- **req-8** — Saved credentials must resolve relative to the script/home
  directory, not the current working directory, so launching from elsewhere
  does not silently lose them. *(t-28, open)*
- **req-9** — Verification must be possible without a real hub: offscreen
  smoke tests (`QT_QPA_PLATFORM=offscreen`, stub client subclassing
  `AbstractSmartHomeHub`). *(established during t-1…t-10 execution)*
- **req-10** — Discovery must cover all local subnets, not just the first
  /24 of a large network. *(t-21, open)*
- **req-11** — Only one discovery scan may run at a time, and the progress
  dialog's Cancel button must actually stop the scan. *(t-25, open)*
- **req-12** — Token generation must use the auth flow that actually exists
  in the installed `dirigera` version (currently the `dirigera.hub.auth`
  challenge flow). *(t-11, implemented)*
