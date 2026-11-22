"""Reproduce the two measurements behind the upstream proposal on a real hub.

Reads need no flag. Every write needs --yes and changes the hub: ask the owner of
the hub first. The token is read from DIRIGERA_TOKEN and the address from
DIRIGERA_IP; neither is printed.

    python measure_hub.py list
    python measure_hub.py leave-adaptive <device-id> --yes
    python measure_hub.py reset-energy <device-id> --yes

Needs only the `dirigera` package (>= 1.6.1).
"""

import argparse
import os
import sys
import time
from typing import Any, Dict

from dirigera import Hub

SETTLE_SECONDS = 6  # the hub applies a change after a few seconds


def device(hub: Hub, device_id: str) -> Dict[str, Any]:
    data: Dict[str, Any] = hub.get(f"/devices/{device_id}")
    return data


def list_candidates(hub: Hub) -> None:
    for item in hub.get("/devices"):
        attributes = item.get("attributes", {})
        can_receive = item.get("capabilities", {}).get("canReceive", [])
        if "adaptiveProfile" in item:
            print(
                item["id"][:8],
                "light",
                attributes.get("customName"),
                item["adaptiveProfile"],
            )
        if "energyConsumedAtLastReset" in attributes:
            print(
                item["id"][:8],
                "metering",
                attributes.get("customName"),
                "total",
                attributes.get("totalEnergyConsumed"),
                "at reset",
                attributes.get("energyConsumedAtLastReset"),
                "resettable",
                "energyConsumedAtLastReset" in can_receive,
            )


def leave_adaptive(hub: Hub, device_id: str) -> None:
    before = device(hub, device_id)
    profile = before.get("adaptiveProfile") or {}
    if not profile.get("active") or not profile.get("id"):
        print("The light is not following a profile; nothing to leave.")
        return
    print("before:", before["attributes"].get("lightLevel"), before["adaptiveProfile"])
    hub.patch(
        f"/devices/{device_id}",
        data=[{"adaptiveProfile": {"id": profile["id"], "active": False}}],
    )
    time.sleep(SETTLE_SECONDS)
    after = device(hub, device_id)
    print(
        "after: ", after["attributes"].get("lightLevel"), after.get("adaptiveProfile")
    )


def reset_energy(hub: Hub, device_id: str) -> None:
    keys = ("totalEnergyConsumed", "energyConsumedAtLastReset", "timeOfLastEnergyReset")
    before = device(hub, device_id)["attributes"]
    print("before:", {key: before.get(key) for key in keys})
    hub.patch(
        f"/devices/{device_id}",
        data=[{"attributes": {"energyConsumedAtLastReset": 0}}],
    )
    time.sleep(3)
    after = device(hub, device_id)["attributes"]
    print("after: ", {key: after.get(key) for key in keys})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["list", "leave-adaptive", "reset-energy"])
    parser.add_argument("device_id", nargs="?")
    parser.add_argument("--yes", action="store_true", help="allow hub writes")
    args = parser.parse_args()

    token, ip = os.environ.get("DIRIGERA_TOKEN"), os.environ.get("DIRIGERA_IP")
    if not token or not ip:
        print("Set DIRIGERA_IP and DIRIGERA_TOKEN.")
        return 2
    hub = Hub(token=token, ip_address=ip)

    if args.action == "list":
        list_candidates(hub)
        return 0
    if not args.device_id or not args.yes:
        print("This writes to the hub: give a device id and --yes.")
        return 2
    if args.action == "leave-adaptive":
        leave_adaptive(hub, args.device_id)
    else:
        reset_energy(hub, args.device_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
