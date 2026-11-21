"""Settings: the [energy] parser and UI settings kept out of the real ones."""

import configparser
from pathlib import Path

import pytest

from settings import (
    DEFAULT_CURRENCY,
    DEFAULT_PRICE_PER_KWH,
    EnergySettings,
    parse_energy_settings,
    ui_settings,
)


def test_ui_settings_write_into_the_temp_dir(isolated_ui_settings: Path) -> None:
    store = ui_settings()
    store.setValue("scenes/show_automatic", True)
    store.sync()
    files = list(isolated_ui_settings.rglob("*.ini"))
    assert files, "no ini file written"
    assert "show_automatic" in files[0].read_text(encoding="utf-8")
    assert ui_settings().value("scenes/show_automatic", type=bool) is True


@pytest.mark.parametrize(
    "body, price, currency",
    [
        ("", DEFAULT_PRICE_PER_KWH, DEFAULT_CURRENCY),
        ("price_per_kwh = 1.20\ncurrency = EUR", 1.2, "EUR"),
        ("price_per_kwh = 1,35", 1.35, DEFAULT_CURRENCY),
        ("currency = lei", DEFAULT_PRICE_PER_KWH, "lei"),
        ("price_per_kwh =\ncurrency =", DEFAULT_PRICE_PER_KWH, DEFAULT_CURRENCY),
        ("price_per_kwh = 100", 100.0, DEFAULT_CURRENCY),
    ],
)
def test_valid_energy_values_are_read(body: str, price: float, currency: str) -> None:
    settings, problems = parse_energy_settings(configparser_section(body))
    assert problems == []
    assert settings.price_per_kwh == price
    assert settings.currency == currency


@pytest.mark.parametrize(
    "body, problem",
    [
        ("price_per_kwh = 0", "price_per_kwh"),
        ("price_per_kwh = -1", "price_per_kwh"),
        ("price_per_kwh = 100.5", "price_per_kwh"),
        ("price_per_kwh = cheap", "price_per_kwh"),
        ("price_per_kwh = nan", "price_per_kwh"),
        ("currency = RON-RON-RON", "currency"),
    ],
)
def test_bad_energy_values_fall_back_and_are_reported(body: str, problem: str) -> None:
    settings, problems = parse_energy_settings(configparser_section(body))
    assert settings == EnergySettings()
    assert len(problems) == 1
    assert problems[0].startswith(problem)


def configparser_section(body: str) -> configparser.SectionProxy:
    """An [energy] section read the way load_config reads config.ini."""
    config = configparser.ConfigParser()
    config.read_string(f"[energy]\n{body}\n")
    return config["energy"]
