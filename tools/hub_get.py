"""Print the raw JSON a DIRIGERA hub returns for a GET route (read-only).

A tryout tool for finding data the `dirigera` library does not expose, such
as air quality history (t-82). It only sends GET requests, so it changes
nothing on the hub.

Usage (from the repo root):

    uv run python tools/hub_get.py /devices
    uv run python tools/hub_get.py /devices/<device-id>
    uv run python tools/hub_get.py /home

In Git Bash, leave out the leading slash (`devices`): MSYS rewrites `/devices`
into a Windows path. The script adds the slash itself.

Credentials come from the DIRIGERA_IP and DIRIGERA_TOKEN environment variables,
or else from config.ini next to dashboard.py. The token is never printed.
Serial numbers are replaced with "<redacted>" so the output can be shared.
"""

import argparse
import configparser
import json
import os
import sys
from pathlib import Path
from typing import Any, Tuple

from dirigera import Hub

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.ini"
REDACTED_KEYS = {"serialNumber"}


def credentials() -> Tuple[str, str]:
    """Return (ip, token) from the environment or config.ini."""
    ip = os.environ.get("DIRIGERA_IP", "")
    token = os.environ.get("DIRIGERA_TOKEN", "")
    if ip and token:
        return ip, token
    # No interpolation: a "%" in a token must stay literal.
    config = configparser.ConfigParser(interpolation=None)
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8-sig") as file:
            config.read_file(file)
    hub = config["hub"] if "hub" in config else {}
    return ip or hub.get("ip_address", ""), token or hub.get("token", "")


def redact(value: Any) -> Any:
    """Return `value` with serial numbers replaced, recursively."""
    if isinstance(value, dict):
        return {
            key: "<redacted>" if key in REDACTED_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("route", help='hub route, e.g. "/devices"')
    args = parser.parse_args()

    ip, token = credentials()
    if not ip or not token or token == "YOUR_TOKEN_HERE":
        print("Set DIRIGERA_IP and DIRIGERA_TOKEN, or fill in config.ini.")
        return 2

    route = args.route if args.route.startswith("/") else f"/{args.route}"
    hub = Hub(token=token, ip_address=ip)
    try:
        data = hub.get(route)
    except Exception as error:  # report any failure, e.g. 404 for unknown routes
        print(f"GET {route} failed: {error}")
        return 1
    print(json.dumps(redact(data), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
