"""config.ini loading: location and error reporting."""

from pathlib import Path
from typing import Any

import pytest

import dashboard
from settings import (
    DEFAULT_CURRENCY,
    DEFAULT_DISCOVERY_TIMEOUT,
    DEFAULT_DISCOVERY_WORKERS,
    DEFAULT_PRICE_PER_KWH,
    EnergySettings,
)


def write_config(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def fields(win: Any) -> tuple[str, str]:
    return (
        win.connection_block.ip_input.text(),
        win.connection_block.token_input.text(),
    )


def test_valid_file_fills_ip_and_token(window: Any, tmp_path: Path) -> None:
    write_config(
        tmp_path / "config.ini", "[hub]\nip_address = 10.0.0.5\ntoken = abc123\n"
    )
    window.load_config()
    assert fields(window) == ("10.0.0.5", "abc123")


def test_placeholder_token_is_ignored(window: Any, tmp_path: Path) -> None:
    write_config(
        tmp_path / "config.ini",
        "[hub]\nip_address = 10.0.0.5\ntoken = YOUR_TOKEN_HERE\n",
    )
    window.load_config()
    assert fields(window) == ("10.0.0.5", "")


def test_missing_file_shows_no_error(window: Any) -> None:
    window.load_config()
    assert fields(window) == ("", "")
    assert window.status_label.property("tone") != "danger"


def test_file_without_hub_section_is_not_an_error(window: Any, tmp_path: Path) -> None:
    write_config(tmp_path / "config.ini", "[other]\nkey = value\n")
    window.load_config()
    assert fields(window) == ("", "")
    assert window.status_label.property("tone") != "danger"


def test_empty_hub_section_is_not_an_error(window: Any, tmp_path: Path) -> None:
    write_config(tmp_path / "config.ini", "[hub]\n")
    window.load_config()
    assert fields(window) == ("", "")
    assert window.status_label.property("tone") != "danger"


def test_malformed_file_is_reported_inline(
    window: Any, tmp_path: Path, dialogs: list[tuple[str, str]]
) -> None:
    write_config(tmp_path / "config.ini", "ip_address = 10.0.0.5\n[hub]\n")
    window.load_config()
    assert fields(window) == ("", "")
    assert window.status_label.text().startswith("Could not read config.ini")
    assert window.status_label.property("tone") == "danger"
    assert dialogs == []


def test_undecodable_file_is_reported_inline(window: Any, tmp_path: Path) -> None:
    (tmp_path / "config.ini").write_bytes(b"[hub]\ntoken = \xff\xfe\x80\n")
    window.load_config()
    assert fields(window) == ("", "")
    assert window.status_label.text().startswith("Could not read config.ini")
    assert window.status_label.property("tone") == "danger"


def test_found_regardless_of_working_directory(
    window: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(tmp_path / "config.ini", "[hub]\nip_address = 10.0.0.9\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    window.load_config()
    assert fields(window)[0] == "10.0.0.9"


def test_config_path_is_next_to_dashboard() -> None:
    expected = Path(dashboard.__file__).resolve().parent / "config.ini"
    assert dashboard.CONFIG_PATH == expected


def test_discovery_section_sets_the_scan_scope(window: Any, tmp_path: Path) -> None:
    write_config(
        tmp_path / "config.ini",
        "[discovery]\nnetworks = 10.0.0.0/24, 192.168.5.7/24\n"
        "max_workers = 20\ntimeout = 0.5\n",
    )
    window.load_config()
    settings = window.discovery_settings
    assert settings.networks == ["10.0.0.0/24", "192.168.5.0/24"]
    assert settings.max_workers == 20
    assert settings.timeout == 0.5
    assert window.status_label.property("tone") != "danger"


def test_discovery_defaults_without_a_section(window: Any, tmp_path: Path) -> None:
    write_config(tmp_path / "config.ini", "[hub]\nip_address = 10.0.0.5\n")
    window.load_config()
    settings = window.discovery_settings
    assert settings.networks is None
    assert settings.max_workers == DEFAULT_DISCOVERY_WORKERS
    assert settings.timeout == DEFAULT_DISCOVERY_TIMEOUT


@pytest.mark.parametrize(
    "body",
    [
        "networks = not-a-network",
        "networks = 10.0.0.0/24, junk",
        "max_workers = many",
        "max_workers = 0",
        "timeout = soon",
        "timeout = -1",
    ],
)
def test_invalid_discovery_values_fall_back_with_a_message(
    window: Any,
    tmp_path: Path,
    dialogs: list[tuple[str, str]],
    body: str,
) -> None:
    write_config(tmp_path / "config.ini", f"[discovery]\n{body}\n")
    window.load_config()
    settings = window.discovery_settings
    assert settings.networks is None
    assert settings.max_workers == DEFAULT_DISCOVERY_WORKERS
    assert settings.timeout == DEFAULT_DISCOVERY_TIMEOUT
    assert window.status_label.property("tone") == "danger"
    assert "[discovery]" in window.status_label.text()
    assert dialogs == []


def test_one_bad_discovery_value_keeps_the_good_ones(
    window: Any, tmp_path: Path
) -> None:
    write_config(
        tmp_path / "config.ini", "[discovery]\nmax_workers = 12\ntimeout = soon\n"
    )
    window.load_config()
    assert window.discovery_settings.max_workers == 12
    assert window.discovery_settings.timeout == DEFAULT_DISCOVERY_TIMEOUT
    assert window.status_label.property("tone") == "danger"


def test_energy_section_sets_the_price(window: Any, tmp_path: Path) -> None:
    write_config(
        tmp_path / "config.ini", "[energy]\nprice_per_kwh = 1,20\ncurrency = EUR\n"
    )
    window.load_config()
    assert window.energy_settings.price_per_kwh == 1.2
    assert window.energy_settings.currency == "EUR"
    assert window.energy_view.price_per_kwh == 1.2
    assert window.energy_view.currency == "EUR"
    assert window.status_label.property("tone") != "danger"


def test_energy_defaults_without_a_section(window: Any, tmp_path: Path) -> None:
    write_config(tmp_path / "config.ini", "[hub]\nip_address = 10.0.0.5\n")
    window.load_config()
    assert window.energy_settings == EnergySettings()
    assert window.energy_view.price_per_kwh == DEFAULT_PRICE_PER_KWH
    assert window.energy_view.currency == DEFAULT_CURRENCY


def test_invalid_energy_value_is_reported_in_the_status(
    window: Any, tmp_path: Path, dialogs: list[tuple[str, str]]
) -> None:
    write_config(
        tmp_path / "config.ini",
        "[discovery]\ntimeout = soon\n[energy]\nprice_per_kwh = -2\n",
    )
    window.load_config()
    assert window.energy_settings.price_per_kwh == DEFAULT_PRICE_PER_KWH
    assert window.status_label.property("tone") == "danger"
    text = window.status_label.text()
    assert "[energy] price_per_kwh" in text
    assert "[discovery] timeout" in text
    assert dialogs == []
