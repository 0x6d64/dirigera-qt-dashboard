"""config.ini loading: location and error reporting."""

from pathlib import Path
from typing import Any

import pytest

import dashboard


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
