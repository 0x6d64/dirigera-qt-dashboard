"""UI settings: stored in an ini file, kept out of the real user settings."""

from pathlib import Path

from settings import ui_settings


def test_ui_settings_write_into_the_temp_dir(isolated_ui_settings: Path) -> None:
    store = ui_settings()
    store.setValue("scenes/show_automatic", True)
    store.sync()
    files = list(isolated_ui_settings.rglob("*.ini"))
    assert files, "no ini file written"
    assert "show_automatic" in files[0].read_text(encoding="utf-8")
    assert ui_settings().value("scenes/show_automatic", type=bool) is True
