"""Discovery decisions, with every network call mocked (req-5, req-10)."""

from typing import Any

import pytest
import requests

import network_discovery as nd


@pytest.mark.parametrize(
    "mac, expected",
    [
        ("00:1e:c0:12:34:56", True),  # case-insensitive
        ("CC-86-EC-00-00-01", True),  # dash separators
        ("aa:bb:cc:dd:ee:ff", False),
        ("", False),
        (None, False),
    ],
)
def test_is_ikea_device(mac: str | None, expected: bool) -> None:
    assert nd.is_ikea_device(mac) is expected


def test_get_local_networks_skips_loopback_and_bad_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inet = nd.netifaces.AF_INET
    ifaces: dict[str, Any] = {
        "lo": {inet: [{"addr": "127.0.0.1", "netmask": "255.0.0.0"}]},
        "eth0": {
            inet: [
                {"addr": "192.168.1.20", "netmask": "255.255.255.0"},
                {"addr": "10.0.0.5", "mask": "255.255.0.0"},  # netifaces2 key
                {"addr": "garbage", "netmask": "255.255.255.0"},
            ]
        },
        "wlan0": {},  # no IPv4
    }
    monkeypatch.setattr(nd.netifaces, "interfaces", lambda: list(ifaces))
    monkeypatch.setattr(nd.netifaces, "ifaddresses", lambda name: ifaces[name])
    assert nd.get_local_networks() == ["192.168.1.0/24", "10.0.0.0/16"]


class _Response:
    def __init__(self, status: int, headers: dict[str, str]):
        self.status_code = status
        self.headers = headers


@pytest.mark.parametrize(
    "status, headers, expected",
    [
        (401, {"Api-Version": "1"}, True),
        (200, {"Api-Version": "1"}, True),
        (401, {}, False),  # some other service on 8443
        (500, {"Api-Version": "1"}, False),
    ],
)
def test_api_probe(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    headers: dict[str, str],
    expected: bool,
) -> None:
    monkeypatch.setattr(nd.requests, "get", lambda *a, **k: _Response(status, headers))
    assert nd.looks_like_dirigera_api("10.0.0.2") is expected


def test_api_probe_network_error_is_not_a_hub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*a: Any, **k: Any) -> None:
        raise requests.ConnectionError

    monkeypatch.setattr(nd.requests, "get", boom)
    assert nd.looks_like_dirigera_api("10.0.0.2") is False


def _scan(
    monkeypatch: pytest.MonkeyPatch, port: bool, api: bool, mac: str | None
) -> Any:
    monkeypatch.setattr(nd, "check_dirigera_port", lambda ip: port)
    monkeypatch.setattr(nd, "looks_like_dirigera_api", lambda ip: api)
    monkeypatch.setattr(nd, "get_mac_address", lambda ip: mac)
    return nd.scan_ip("10.0.0.2")


def test_scan_closed_port_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _scan(monkeypatch, port=False, api=True, mac="00:1E:C0:00:00:01") is None


def test_scan_api_identifies_hub_even_without_mac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _scan(monkeypatch, port=True, api=True, mac=None) == ("10.0.0.2", None)


def test_scan_oui_is_only_a_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    mac = "00:1E:C0:00:00:01"
    assert _scan(monkeypatch, port=True, api=False, mac=mac) == ("10.0.0.2", mac)
    assert _scan(monkeypatch, port=True, api=False, mac="aa:bb:cc:00:00:01") is None


def test_discover_collects_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nd, "get_local_networks", lambda: ["192.168.1.0/30"])
    monkeypatch.setattr(
        nd, "scan_ip", lambda ip: (ip, None) if ip.endswith(".2") else None
    )
    assert nd.discover_dirigera_hubs() == [("192.168.1.2", None)]


def test_discover_without_networks_returns_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(nd, "get_local_networks", lambda: [])
    assert nd.discover_dirigera_hubs() == []


def test_hosts_to_scan_covers_every_24_of_a_large_network() -> None:
    hosts = nd.hosts_to_scan(["10.1.0.0/22"])
    assert len(hosts) == 4 * 254
    for third in range(4):
        assert f"10.1.{third}.1" in hosts
        assert f"10.1.{third}.254" in hosts


def test_hosts_to_scan_keeps_a_23_whole() -> None:
    assert len(nd.hosts_to_scan(["10.1.0.0/23"])) == 510


def test_hosts_to_scan_respects_the_cap() -> None:
    hosts = nd.hosts_to_scan(["10.0.0.0/8"], max_hosts=600)
    assert len(hosts) == 600
    assert hosts[0] == "10.0.0.1"


def test_hosts_to_scan_default_cap() -> None:
    assert len(nd.hosts_to_scan(["10.0.0.0/8"])) == nd.MAX_SCAN_HOSTS


def test_hosts_to_scan_scans_duplicates_once() -> None:
    hosts = nd.hosts_to_scan(["192.168.1.0/24", "192.168.1.0/24", "192.168.1.0/25"])
    assert len(hosts) == 254
    assert len(set(hosts)) == 254


def test_hosts_to_scan_small_network_and_bad_input() -> None:
    assert nd.hosts_to_scan(["junk", "192.168.1.0/30"]) == [
        "192.168.1.1",
        "192.168.1.2",
    ]


def test_get_local_networks_lists_a_shared_subnet_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inet = nd.netifaces.AF_INET
    ifaces: dict[str, Any] = {
        "eth0": {inet: [{"addr": "192.168.1.20", "netmask": "255.255.255.0"}]},
        "wlan0": {inet: [{"addr": "192.168.1.21", "netmask": "255.255.255.0"}]},
    }
    monkeypatch.setattr(nd.netifaces, "interfaces", lambda: list(ifaces))
    monkeypatch.setattr(nd.netifaces, "ifaddresses", lambda name: ifaces[name])
    assert nd.get_local_networks() == ["192.168.1.0/24"]


def test_should_stop_ends_the_scan_early(monkeypatch: pytest.MonkeyPatch) -> None:
    import threading
    import time

    monkeypatch.setattr(nd, "get_local_networks", lambda: ["10.9.0.0/22"])
    scanned: list[str] = []
    stop = threading.Event()

    def slow_scan(ip: str) -> None:
        scanned.append(ip)
        if len(scanned) >= 10:
            stop.set()
        time.sleep(0.01)

    monkeypatch.setattr(nd, "scan_ip", slow_scan)
    started = time.monotonic()
    result = nd.discover_dirigera_hubs(max_workers=4, should_stop=stop.is_set)
    assert result == []
    assert time.monotonic() - started < 5
    assert len(scanned) < 1016 // 2  # far fewer than the 1016 addresses


def test_one_failing_probe_does_not_abort_the_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(nd, "get_local_networks", lambda: ["10.9.0.0/29"])

    def scan(ip: str) -> tuple[str, str | None] | None:
        if ip == "10.9.0.2":
            raise RuntimeError("probe blew up")
        return (ip, None) if ip in ("10.9.0.1", "10.9.0.3") else None

    monkeypatch.setattr(nd, "scan_ip", scan)
    result = nd.discover_dirigera_hubs(max_workers=2)
    assert sorted(result) == [("10.9.0.1", None), ("10.9.0.3", None)]
