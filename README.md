# dirigera-qt-dashboard

A PyQt desktop dashboard for IKEA DIRIGERA smart-home hubs.

This is an unofficial, community project. It is not affiliated with, endorsed
by, or supported by IKEA. "DIRIGERA" is an IKEA product name, used here only to
describe what the app talks to. The app uses the unofficial
[`dirigera`](https://github.com/Leggin/dirigera) Python library.

## Features

- **Rooms**: all devices grouped by room, with controls that fit the device:
  - **Lights**: on/off, brightness, and colour temperature or colour where the
    light supports them
  - **Blinds**: position
  - **Outlets**: on/off, with power and energy readings where available
  - **Sensors and other devices**: their current state
- **Scenes**: list and trigger the scenes stored on the hub
- **Energy**: live power use of outlets and electrical sensors with metering
- **Auto refresh**: data refreshes every 30 seconds while connected; the
  Refresh button fetches immediately. If the hub cannot be reached, the last
  good data stays visible with the time it is from.
- **Inline errors**: problems (bad IP, wrong token, unreachable hub) show as
  messages in the window, not as pop-up dialogs
- **Hub discovery**: scans your local network for hubs

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

## License

MIT. See [LICENSE](LICENSE).
