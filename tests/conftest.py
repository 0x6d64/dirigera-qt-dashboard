"""Shared fixtures: offscreen Qt, silent dialogs, stub devices and hub.

Tests talk to the app through its behaviour (state a user could see), not
through layout, stylesheet or widget-tree details, so UI polish does not
break them.
"""

import os
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app: Any = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    return app


@pytest.fixture(autouse=True)
def isolated_ui_settings(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Point the UI settings at a temp dir so no test touches the real ones."""
    path = tmp_path_factory.mktemp("ui-settings")
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(path))
    return path


@pytest.fixture
def dialogs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Replace modal message boxes (they would block) and record them."""
    shown: list[tuple[str, str]] = []

    def record(kind: str) -> Callable[..., None]:
        def _show(parent: Any, title: str, text: str, *a: Any, **k: Any) -> None:
            shown.append((kind, text))

        return _show

    for kind in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, kind, staticmethod(record(kind)))
    return shown


@pytest.fixture
def pump(qapp: QApplication) -> Callable[[int], None]:
    """Run the event loop for `ms` milliseconds (for timers that must elapse)."""

    def _pump(ms: int) -> None:
        end = time.monotonic() + ms / 1000
        while time.monotonic() < end:
            qapp.processEvents()
            time.sleep(0.005)

    return _pump


@pytest.fixture
def wait_until(qapp: QApplication) -> Callable[..., None]:
    """Pump the event loop until `condition()` holds (default 5 s)."""

    def _wait(condition: Callable[[], bool], timeout: float = 5.0) -> None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            qapp.processEvents()
            if condition():
                return
            time.sleep(0.005)
        raise AssertionError("condition not met in time")

    return _wait


def make_device(
    device_type: str,
    id_: str = "d1",
    name: str = "Device",
    room: tuple[str, str] | None = ("r1", "Kitchen"),
    reachable: bool = True,
    **attributes: Any,
) -> SimpleNamespace:
    """A minimal stand-in shaped like a `dirigera` device."""
    attributes.setdefault("custom_name", name)
    return SimpleNamespace(
        id=id_,
        device_type=device_type,
        is_reachable=reachable,
        room=SimpleNamespace(id=room[0], name=room[1]) if room else None,
        capabilities=SimpleNamespace(can_receive=[]),
        attributes=SimpleNamespace(**attributes),
    )


class StubLight:
    """A light whose commands record their thread and can be made to fail.

    A failing command leaves the hub-side state untouched, like the real
    library; `reload()` is where the real state would be fetched again.
    """

    attributes: Any

    def __init__(
        self,
        fail: bool = False,
        can_receive: list[str] | None = None,
        **kw: Any,
    ) -> None:
        base = make_device("light", is_on=False, light_level=50, **kw)
        self.__dict__.update(base.__dict__)
        self.capabilities = SimpleNamespace(can_receive=can_receive or [])
        self.colour_calls: list[tuple[float, float]] = []
        self.fail = fail
        self.threads: list[threading.Thread] = []
        self.sent: list[tuple[str, Any]] = []  # commands in the order sent

    def _command(self) -> None:
        self.threads.append(threading.current_thread())
        if self.fail:
            raise RuntimeError("hub said no")

    def set_light(self, lamp_on: bool) -> None:
        self._command()
        self.sent.append(("on", lamp_on))
        self.attributes.is_on = lamp_on

    def set_light_level(self, level: int) -> None:
        self._command()
        self.sent.append(("level", level))
        self.attributes.light_level = level

    def set_color_temperature(self, color_temp: int) -> None:
        self._command()
        self.attributes.color_temperature = color_temp

    def set_light_color(self, hue: float, saturation: float) -> None:
        self._command()
        self.colour_calls.append((hue, saturation))
        self.attributes.color_hue = hue
        self.attributes.color_saturation = saturation

    def reload(self) -> "StubLight":
        return self


class StubScene:
    """A scene; `type_` is the hub's scene type (`userScene` unless told otherwise)."""

    def __init__(
        self,
        id_: str = "s1",
        name: str = "Evening",
        fail: bool = False,
        type_: str = "userScene",
    ):
        self.id = id_
        self.info = SimpleNamespace(name=name)
        # Like the library's SceneType enum: the string is in `.value`.
        self.type = SimpleNamespace(value=type_)
        self.fail = fail
        self.triggered = 0

    def trigger(self) -> None:
        if self.fail:
            raise RuntimeError("scene failed")
        self.triggered += 1


class StubHub:
    """Replacement for `dirigera.Hub`; set `fail` to simulate an outage."""

    def __init__(
        self, devices: list[Any] | None = None, scenes: list[Any] | None = None
    ):
        self.devices = devices or []
        self.scenes = scenes or []
        self.fail = False
        self.calls: list[threading.Thread] = []
        # The event listener blocks until stopped; tests call the callbacks
        # kept in `listener` themselves (nothing opens or fires by default).
        self.listener: dict[str, Any] = {}
        self.listener_started = threading.Event()
        self.listener_stop = threading.Event()

    def get(self, route: str) -> dict[str, Any]:
        self.calls.append(threading.current_thread())
        if self.fail:
            raise RuntimeError("unreachable")
        return {}

    def get_all_devices(self) -> list[Any]:
        self.get("/devices")
        return self.devices

    def get_scenes(self) -> list[Any]:
        return self.scenes

    def create_event_listener(self, **callbacks: Any) -> None:
        self.listener = callbacks
        self.listener_started.set()
        self.listener_stop.wait(10)

    def stop_event_listener(self) -> None:
        self.listener_stop.set()


@pytest.fixture
def window(
    qapp: QApplication,
    dialogs: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[Any]:
    """A dashboard that never reads the developer's real config.ini."""
    import dashboard
    from dashboard import DirigeraDashboard

    monkeypatch.setattr(dashboard, "CONFIG_PATH", tmp_path / "config.ini")

    win = DirigeraDashboard()
    yield win
    win._stop_events()  # the listener blocks until it is told to stop
    # Let in-flight workers deliver their signals now, not during the next test.
    end = time.monotonic() + 5
    while win._running_workers() and time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.005)
    qapp.processEvents()
    win._close_pending = False
    win.hide()
    win.deleteLater()
