"""Network discovery utilities for finding Dirigera hubs on the local network."""

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, cast

import netifaces
import requests
import urllib3
from getmac import get_mac_address

# The hub uses a self-signed certificate, so the identification probe must
# skip TLS verification (same behavior as the dirigera library itself).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# IKEA MAC address prefixes (OUI - Organizationally Unique Identifier)
# IKEA devices typically use these MAC prefixes
IKEA_MAC_PREFIXES = [
    "00:1E:C0",  # IKEA Systems AB
    "CC:86:EC",  # IKEA of Sweden AB
    "E0:DC:FF",  # IKEA (some devices)
    "54:EF:44",  # Espressif (used by IKEA for some IoT devices)
]

# Dirigera hub uses port 8443 for API
DIRIGERA_PORT = 8443

# The hub reports its API firmware version in this response header, even on
# unauthenticated requests (verified against a real hub).
DIRIGERA_API_VERSION_HEADER = "Api-Version"


def get_local_networks() -> List[str]:
    """Get all local network ranges from all interfaces."""
    networks = []
    for interface in netifaces.interfaces():
        # netifaces2 ships type hints that do not match its runtime API, so cast
        # to the plain dict shape both netifaces and netifaces2 return.
        addrs = cast(Dict[int, List[Dict[str, str]]], netifaces.ifaddresses(interface))
        if netifaces.AF_INET in addrs:
            for addr_info in addrs[netifaces.AF_INET]:
                ip_addr = addr_info.get("addr")
                # netifaces calls it "netmask", netifaces2 calls it "mask".
                netmask = addr_info.get("netmask") or addr_info.get("mask")
                if ip_addr and netmask and not ip_addr.startswith("127."):
                    try:
                        network = ipaddress.IPv4Network(
                            f"{ip_addr}/{netmask}", strict=False
                        )
                        networks.append(str(network))
                    except (ValueError, ipaddress.AddressValueError):
                        continue
    return networks


def is_ikea_device(mac_address: Optional[str]) -> bool:
    """Check if a MAC address belongs to an IKEA device."""
    if not mac_address:
        return False

    mac_upper = mac_address.upper().replace("-", ":").replace(".", ":")
    for prefix in IKEA_MAC_PREFIXES:
        if mac_upper.startswith(prefix):
            return True
    return False


def check_dirigera_port(ip: str, timeout: float = 1.0) -> bool:
    """Check if the Dirigera API port (8443) is open on the given IP."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, DIRIGERA_PORT))
            return result == 0
    except (socket.error, socket.timeout):
        return False


def looks_like_dirigera_api(ip: str, timeout: float = 1.0) -> bool:
    """Identify a DIRIGERA hub by its unauthenticated API response.

    The hub answers ``GET /v1/home`` with HTTP 401 (or 200 with a valid token)
    and always includes an ``Api-Version`` response header. Other services
    that happen to listen on 8443 do not (verified against a real hub and a
    non-hub service). No hub state is changed by this request.
    """
    try:
        response = requests.get(
            f"https://{ip}:{DIRIGERA_PORT}/v1/home",
            verify=False,
            timeout=timeout,
        )
    except requests.RequestException:
        return False
    return DIRIGERA_API_VERSION_HEADER in response.headers and response.status_code in (
        200,
        401,
    )


def scan_ip(ip: str) -> Optional[Tuple[str, Optional[str]]]:
    """
    Scan a single IP address for Dirigera hub.
    Returns (ip, mac) tuple if found, None otherwise. The MAC may be None
    when the hub was identified via its API but no MAC could be resolved.
    """
    # Fast check first: the hub's API port.
    if not check_dirigera_port(ip):
        return None

    # Preferred identification: unauthenticated API probe. Works even when
    # the MAC is masked (routed segments, Wi-Fi bridges, virtualization).
    if looks_like_dirigera_api(ip):
        return (ip, get_mac_address(ip=ip))

    # Fallback when HTTPS probing is impossible: MAC OUI check.
    mac = get_mac_address(ip=ip)
    if mac and is_ikea_device(mac):
        return (ip, mac)

    return None


def discover_dirigera_hubs(
    max_workers: int = 50, timeout_per_ip: float = 1.0
) -> List[Tuple[str, Optional[str]]]:
    """
    Discover Dirigera hubs on the local network.

    Returns:
        List of tuples (ip_address, mac_address) for discovered hubs. The MAC
        is None when the hub was identified via its API but no MAC could be
        resolved.
    """
    networks = get_local_networks()
    if not networks:
        return []

    discovered_hubs = []
    ips_to_scan = []

    # Collect all IPs to scan from all local networks
    for network_str in networks:
        try:
            network = ipaddress.IPv4Network(network_str)
            # Skip very large networks to avoid long scans
            if network.num_addresses > 512:
                # For large networks, only scan common ranges
                base_ip = str(network.network_address)
                for i in range(1, 255):
                    octets = base_ip.split(".")
                    octets[-1] = str(i)
                    ips_to_scan.append(".".join(octets))
            else:
                # For smaller networks, scan all hosts
                ips_to_scan.extend([str(ip) for ip in network.hosts()])
        except (ValueError, ipaddress.AddressValueError):
            continue

    # Scan IPs in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ip = {executor.submit(scan_ip, ip): ip for ip in ips_to_scan}

        for future in as_completed(future_to_ip):
            result = future.result()
            if result:
                discovered_hubs.append(result)

    return discovered_hubs
