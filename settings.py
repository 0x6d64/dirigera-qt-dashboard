"""Settings: the [discovery] section of config.ini and the UI preferences.

Only `QtCore` is imported here, so the parsers stay free of widgets.
"""

import ipaddress
from dataclasses import dataclass
from typing import List, Mapping, Optional, Tuple

from PyQt6.QtCore import QSettings

DEFAULT_DISCOVERY_WORKERS = 50
DEFAULT_DISCOVERY_TIMEOUT = 1.0

# Romania, March 2026, residential price including network costs and taxes.
DEFAULT_PRICE_PER_KWH = 1.54
DEFAULT_CURRENCY = "RON"
MAX_CURRENCY_LENGTH = 8


@dataclass
class DiscoverySettings:
    """Scan scope from the optional [discovery] section of config.ini (t-22)."""

    networks: Optional[List[str]] = None  # None: detect the local networks
    max_workers: int = DEFAULT_DISCOVERY_WORKERS
    timeout: float = DEFAULT_DISCOVERY_TIMEOUT


def parse_discovery_settings(
    section: Mapping[str, str],
) -> Tuple[DiscoverySettings, List[str]]:
    """Read a [discovery] section; return the settings and any problems.

    Every bad value is reported and replaced by its default.
    """
    settings = DiscoverySettings()
    problems: List[str] = []

    raw = section.get("networks", "").strip()
    if raw:
        networks: List[str] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                networks.append(str(ipaddress.IPv4Network(part, strict=False)))
            except ValueError:
                problems.append(f"networks: '{part}' is not an IPv4 network")
                networks = []
                break
        settings.networks = networks or None

    raw = section.get("max_workers", "").strip()
    if raw:
        try:
            workers = int(raw)
            if not 1 <= workers <= 500:
                raise ValueError
            settings.max_workers = workers
        except ValueError:
            problems.append("max_workers: use a whole number from 1 to 500")

    raw = section.get("timeout", "").strip()
    if raw:
        try:
            timeout = float(raw)
            if not 0.1 <= timeout <= 30:
                raise ValueError
            settings.timeout = timeout
        except ValueError:
            problems.append("timeout: use seconds from 0.1 to 30")

    return settings, problems


@dataclass
class EnergySettings:
    """Energy price from the optional [energy] section of config.ini (req-19)."""

    price_per_kwh: float = DEFAULT_PRICE_PER_KWH
    currency: str = DEFAULT_CURRENCY


def parse_energy_settings(
    section: Mapping[str, str],
) -> Tuple[EnergySettings, List[str]]:
    """Read an [energy] section; return the settings and any problems.

    A comma is accepted as the decimal separator. A blank value means the
    default, as in [discovery]; every other bad value is reported and replaced
    by its default.
    """
    settings = EnergySettings()
    problems: List[str] = []

    raw = section.get("price_per_kwh", "").strip()
    if raw:
        try:
            price = float(raw.replace(",", "."))
            if not 0 < price <= 100:
                raise ValueError
            settings.price_per_kwh = price
        except ValueError:
            problems.append("price_per_kwh: use a number above 0 and up to 100")

    raw = section.get("currency", "").strip()
    if raw:
        if len(raw) <= MAX_CURRENCY_LENGTH:
            settings.currency = raw
        else:
            problems.append(f"currency: use 1 to {MAX_CURRENCY_LENGTH} characters")

    return settings, problems


def ui_settings() -> QSettings:
    """The one store for UI preferences (an ini file in the user's config dir)."""
    return QSettings(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        "dirigera-qt-dashboard",
        "dashboard",
    )
