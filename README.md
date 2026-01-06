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

You'll need to press the pairing button on your Dirigera hub when prompted. The script will display your token, which you should save securely.

## Usage

Run the dashboard:
```bash
uv run python main.py
```

### Finding Your Dirigera Hub

The dashboard offers two ways to find your hub:

1. **Automatic Discovery** (Recommended):
   - Click the "Discover" button
   - The app will scan your local network for Dirigera hubs
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
