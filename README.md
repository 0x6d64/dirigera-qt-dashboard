# dirigera-qt-dashboard

A PyQt based dashboard for IKEA Dirigera hubs

## Features

- **Network Discovery**: Automatically scans your local network to find Dirigera hubs
- **Device Discovery**: Automatically discovers all devices connected to your Dirigera hub
- **Room Organization**: Displays devices sorted by room for easy management
- **Device Controls**: Provides appropriate controls for different device types:
  - **Lights**: On/Off toggle and brightness slider
  - **Blinds**: Position slider
  - **Outlets**: On/Off toggle
  - **Other devices**: Status indicator
- **Scene Management**: Lists all available scenes with the ability to trigger them

## Requirements

- Python 3.12 or higher
- A Dirigera hub on your local network
- Dirigera authentication token

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for package management.

1. Install uv if you haven't already:
```bash
pip install uv
```

2. Clone the repository:
```bash
git clone https://github.com/0x6d64/dirigera-qt-dashboard.git
cd dirigera-qt-dashboard
```

3. Install dependencies:
```bash
uv sync
```

## Getting Your Dirigera Token

To connect to your Dirigera hub, you need an authentication token. Use the included helper script:

```bash
uv run python generate_token.py <hub_ip_address>
```

For example:
```bash
uv run python generate_token.py 192.168.1.100
```

When prompted, press the pairing button on your Dirigera hub and then press ENTER in the terminal. The script will display your token, which you should save securely.

## Saved Credentials (optional)

Copy `config.ini.example` to `config.ini` in the same folder as `dashboard.py`
and fill in the hub IP and token. The dashboard reads it from there regardless
of the directory you start it from, and pre-fills the connection fields.

### Limiting the scan (optional)

Add a `[discovery]` section to `config.ini` to scan specific networks instead
of the detected ones, or to tune the scan (see `config.ini.example`):

```ini
[discovery]
networks = 192.168.1.0/24, 10.0.0.0/24
max_workers = 50
timeout = 1.0
```

Invalid values are ignored with a message in the status line and the defaults
are used.

## Usage

Run the dashboard:
```bash
uv run python main.py
```

### Finding Your Dirigera Hub

The dashboard offers two ways to find your hub:

1. **Automatic Discovery** (Recommended):
   - Click the "Discover" button
   - The app will scan your local network for Dirigera hubs; the progress
     text names the addresses and networks being scanned
   - Link-local (169.254.x.x) and single-host networks are skipped, and so are
     virtual adapters (docker, veth, vbox, vmnet, tun, tap, wg, utun) where
     the operating system reports readable interface names (Windows does not)
   - If one hub is found, its IP will be filled in automatically
   - If multiple hubs are found, you can select which one to use
   - If no hubs are found, you can enter the IP manually

2. **Manual Entry**:
   - Enter your Dirigera hub's IP address directly in the text field

### Connecting to Your Hub

1. Click "Discover" to find your hub, or enter the IP address manually
2. Enter your authentication token (see "Getting Your Dirigera Token" above)
3. Click "Connect"
4. Browse your devices organized by room in the "Devices" tab
5. Trigger scenes in the "Scenes" tab
6. Use the "Refresh" button to update the device list

## Development

See [AGENTS.md](AGENTS.md) for the repository's working rules — task and
requirement ID conventions, the implementation-plan branch workflow, code
gates, and git rules. Read it before contributing.

### Code Formatting

This project uses `black` for code formatting:
```bash
uv run black .
```

### Linting

Check code with `ruff`:
```bash
uv run ruff check .
```

Fix issues automatically:
```bash
uv run ruff check --fix .
```

### Type Checking

Run type checking with `mypy`:
```bash
uv run mypy .
```

## License

See [LICENSE](LICENSE) file for details.
