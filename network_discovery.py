"""Network discovery utilities for finding Dirigera hubs on the local network."""

import ipaddress
import logging
import socket
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Callable, Dict, List, Optional, Tuple, cast

import netifaces
import requests
import urllib3
from getmac import get_mac_address

log = logging.getLogger(__name__)

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

# Upper bound for the number of addresses probed in one scan.
MAX_SCAN_HOSTS = 4096

# Networks up to this many addresses (a /23) are scanned completely; larger
# ones are split into their /24 subnets.
_MAX_UNSPLIT_ADDRESSES = 512

# Interface name prefixes of virtual adapters (containers, VMs, VPN tunnels).
# Only applied where names are readable; Windows reports GUIDs instead.
VIRTUAL_INTERFACE_PREFIXES = (
    "docker",
    "veth",
    "vbox",
    "vmnet",
    "tun",
    "tap",
    "wg",
    "utun",
)

_LINK_LOCAL = ipaddress.IPv4Network("169.254.0.0/16")


def _is_virtual_interface(name: str) -> bool:
    """True for a readable interface name that looks like a virtual adapter."""
    if name.startswith("{"):  # Windows GUID: the name says nothing
        return False
    return name.lower().startswith(VIRTUAL_INTERFACE_PREFIXES)


def get_local_networks() -> List[str]:
    """Get the local network ranges worth scanning.

    Skips loopback, link-local (169.254.0.0/16), single-host (/32) networks
    and, where the interface name is readable, virtual adapters.
    """
    networks: List[str] = []
    for interface in netifaces.interfaces():
        if _is_virtual_interface(interface):
            continue
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
                        if network.prefixlen == 32 or network.subnet_of(_LINK_LOCAL):
                            continue
                        if str(network) not in networks:
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
    except OSError:  # includes socket.timeout
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


def hosts_to_scan(networks: List[str], max_hosts: int = MAX_SCAN_HOSTS) -> List[str]:
    """Return the host addresses to probe for the given networks.

    Networks of up to 512 addresses contribute all their hosts, larger ones
    contribute the hosts of every /24 they contain. Duplicates are dropped
    (order preserved), invalid network strings are skipped, and the result
    stops at ``max_hosts`` addresses.
    """
    hosts: List[str] = []
    seen = set()
    for network_str in networks:
        try:
            network = ipaddress.IPv4Network(network_str, strict=False)
        except ValueError:
            continue
        if network.num_addresses > _MAX_UNSPLIT_ADDRESSES:
            subnets = network.subnets(new_prefix=24)
        else:
            subnets = iter([network])
        for subnet in subnets:
            for host in subnet.hosts():
                ip = str(host)
                if ip in seen:
                    continue
                if len(hosts) >= max_hosts:
                    return hosts
                seen.add(ip)
                hosts.append(ip)
    return hosts


def discover_dirigera_hubs(
    max_workers: int = 50,
    timeout_per_ip: float = 1.0,
    should_stop: Optional[Callable[[], bool]] = None,
) -> List[Tuple[str, Optional[str]]]:
    """
    Discover Dirigera hubs on the local network.

    ``should_stop`` is polled while results are collected; once it returns
    True the pending probes are cancelled and the hubs found so far are
    returned. Only probes already in flight keep running, each for at most
    its own timeout.

    Returns:
        List of tuples (ip_address, mac_address) for discovered hubs. The MAC
        is None when the hub was identified via its API but no MAC could be
        resolved.
    """
    ips_to_scan = hosts_to_scan(get_local_networks())
    if not ips_to_scan:
        return []

    discovered_hubs: List[Tuple[str, Optional[str]]] = []

    # No `with` block: its exit would wait for every queued probe.
    executor = ThreadPoolExecutor(max_workers=max_workers)
    try:
        pending = {executor.submit(scan_ip, ip) for ip in ips_to_scan}
        while pending:
            if should_stop is not None and should_stop():
                break
            done, pending = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
            for future in done:
                try:
                    result = future.result()
                except Exception:  # one failing probe must not abort the scan
                    log.exception("Probe failed; skipping that address")
                    continue
                if result:
                    discovered_hubs.append(result)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    return discovered_hubs
