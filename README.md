# dirigera-qt-dashboard

A PyQt desktop dashboard for IKEA DIRIGERA smart-home hubs.

This is an unofficial, community project. It is not affiliated with, endorsed
by, or supported by IKEA. "DIRIGERA" is an IKEA product name, used here only to
describe what the app talks to. The app uses the unofficial
[`dirigera`](https://github.com/Leggin/dirigera) Python library.

## Features

- **Rooms**: all devices grouped by room, with controls that fit the device:
  - **Lights**: on/off, brightness, and colour temperature or colour where the
    light supports them. Lights that can follow an adaptive profile have an
    "Adaptive" picker (see below).
  - **Blinds**: a position slider and Up, Down and Stop buttons
  - **Outlets**: on/off, with power and energy readings where available
  - **Air purifiers**: a Fan control (Off, Auto, speeds 1 to 5), the PM2.5
    reading with a word for its band (good, moderate, poor), and the filter:
    how much life is left and when to change it, with a "Change filter" chip
    once the hub raises the filter alarm. The child lock is deliberately not
    shown.
  - **Sensors and other devices**: their current state
- **Adaptive profiles**: a light that can follow one of the hub's adaptive
  profiles shows which one it follows, and you pick another from its card. The
  profiles themselves are created in the IKEA app only. "Off" is shown as the
  state but cannot be chosen yet; changing the light's brightness or warmth
  ends the profile on the hub, and the card then shows what the hub applied
  after a few seconds.
- **Room colours**: a switch above the rooms marks each room with the colour
  you gave it in the IKEA app (a dot by the room name and a coloured card
  edge). It is off by default, and the choice is remembered.
- **Scenes**: list and trigger the scenes stored on the hub. Automatic scenes
  (every scene that is not a user scene) are hidden unless you turn on "Show
  automatic scenes" above the scene grid; the choice is remembered.
- **Energy**: live power use of outlets and electrical sensors with metering,
  totals per room and for the home, the usage since the last reset with its
  cost (see "Energy price"), and a Reset button for plugs the hub lets reset.
  Reset asks for a second click to confirm and cannot be undone.
- **Live updates**: while the hub's event connection is open, changes made
  elsewhere (the IKEA app, a wall switch) show within about two seconds, and
  the status line reads "Live". If the connection drops, the dashboard keeps
  working by polling.
- **Auto refresh**: data also refreshes by polling, every 30 seconds (every
  300 seconds while live updates work); the Refresh button fetches
  immediately. If the hub cannot be reached, the last good data stays visible
  with the time it is from.
- **Commands**: a device command runs in the background and the card shows
  "Sending…" while it runs. A card handles one command at a time: a second
  change on a card that is still sending is ignored and the control snaps back
  to the real value, so wait for "Sending…" to go away. A slider's mouse wheel
  works only after you click it or reach it with Tab; otherwise the wheel
  scrolls the page.
- **Inline errors**: problems (bad IP, wrong token, unreachable hub) show as
  messages in the window, not as pop-up dialogs
- **Hub discovery**: scans your local network for hubs

Closing the window while a hub call is running waits for the call to finish
(up to the 10 second timeout) and then exits; no new refresh starts meanwhile.

<!-- Screenshots: to be added by the owner. -->

## Requirements

- Python 3.12 or newer
- [uv](https://github.com/astral-sh/uv) for installing and running
- A DIRIGERA hub on the same network
- An authentication token for the hub (see below)

Dependencies (installed by `uv sync`): `dirigera`, `PyQt6`, `getmac`, and
`netifaces2` (reads the local network interfaces for hub discovery).

## Installation

```bash
git clone https://github.com/0x6d64/dirigera-qt-dashboard.git
cd dirigera-qt-dashboard
uv sync
```

## Getting your token

Run the helper script with the hub's IP address:

```bash
uv run python generate_token.py <hub_ip_address>
```

When prompted, press the pairing button on the hub, then press ENTER in the
terminal. The script prints your token; store it securely.

## Running

```bash
uv run dirigera-dashboard
```

(`uv run python main.py` works too.)

Enter the hub IP and token, then click **Connect**. To fill in the IP
automatically, click **Discover**.

### Saved credentials (optional)

Copy `config.ini.example` to `config.ini` in the project folder, next to
`dashboard.py`, and fill in the hub IP and token. The app reads it from there
whatever directory you start it from, and pre-fills the connection fields.
`config.ini` is gitignored; keep it that way.

### Hub discovery

**Discover** probes the local network for hubs and names the networks it is
scanning in the progress text.

- A single hub is filled in automatically; with several you pick one; with
  none you can enter the IP by hand.
- Link-local (169.254.x.x) and single-host networks are skipped, and so are
  virtual adapters (docker, veth, vbox, vmnet, tun, tap, wg, utun) where the
  operating system reports readable interface names. Windows does not, so
  there you may want to set `networks` explicitly.
- A scan stops at 4096 addresses in total.
- **Cancel** stops the scan; a partial result is discarded.

To scan specific networks or tune the scan, add a `[discovery]` section to
`config.ini` (all keys optional, see `config.ini.example`):

```ini
[discovery]
networks = 192.168.1.0/24, 10.0.0.0/24
max_workers = 50
timeout = 1.0
```

Invalid values are ignored with a message in the status line, and the defaults
are used.

### Energy price

The Energy tab shows the cost of each metering plug's usage. The price comes
from an optional `[energy]` section in `config.ini`: `price_per_kwh` (default
1.54) and `currency` (default RON). The default is the Romanian residential
price of March 2026, including network costs and taxes; set your own tariff if
it differs. Invalid values are ignored with a message, as for `[discovery]`.

## Security

The hub uses a self-signed certificate, and the `dirigera` library does not
verify it, so traffic to the hub is not protected against someone who can
intercept your local network. Treat the token as a network secret: anyone who
has it and can reach the hub can control your devices. Keep `config.ini` and
the token private, never commit them, and only use the app on networks you
trust.

## Development

See [AGENTS.md](AGENTS.md) for the repository's working rules: task and
requirement ID conventions, the implementation-plan branch workflow, code
gates, and git rules. Read it before contributing.

Run the checks before committing:

```bash
uv run black .
uv run ruff check .
uv run mypy .
uv run pytest -q
```

Tests run in parallel (`pytest-xdist`, one worker per CPU core). Pass `-n 0` to
run them serially, for example under a debugger.

## License

MIT. See [LICENSE](LICENSE).
