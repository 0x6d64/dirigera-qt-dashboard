"""Network discovery utilities for finding Dirigera hubs on the local network."""

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

import netifaces
from getmac import get_mac_address

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


def get_local_networks() -> List[str]:
    """Get all local network ranges from all interfaces."""
    networks = []
    for interface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addrs:
            for addr_info in addrs[netifaces.AF_INET]:
                ip_addr = addr_info.get("addr")
                netmask = addr_info.get("netmask")
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


def scan_ip(ip: str) -> Optional[Tuple[str, str]]:
    """
    Scan a single IP address for Dirigera hub.
    Returns (ip, mac) tuple if found, None otherwise.
    """
    # First check if port 8443 is open (faster than MAC lookup)
    if not check_dirigera_port(ip):
        return None

    # Then check MAC address
    mac = get_mac_address(ip=ip)
    if mac and is_ikea_device(mac):
        return (ip, mac)

    return None


def discover_dirigera_hubs(
    max_workers: int = 50, timeout_per_ip: float = 1.0
) -> List[Tuple[str, str]]:
    """
    Discover Dirigera hubs on the local network.

    Returns:
        List of tuples (ip_address, mac_address) for discovered hubs.
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
