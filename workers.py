"""Worker threads: every blocking hub or network call runs here (req-4).

Each worker catches its own errors at the thread boundary and reports them
through a signal, so nothing is lost when a thread ends.
"""

import json
import logging
import threading
from typing import Any, Callable, Dict, Optional, Protocol

from dirigera import Hub
from dirigera.devices.scene import Scene
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QWidget

from network_discovery import discover_dirigera_hubs
from settings import DiscoverySettings

log = logging.getLogger(__name__)

# Seconds the websocket library waits before it reconnects a dropped socket.
EVENT_RECONNECT_S = 5


def parse_event(message: Any) -> Optional[Dict[str, Any]]:
    """Decode one websocket message; `None` unless it is a JSON object with a `type`.

    Never raises: the hub may send anything, and the listener thread must go on.
    """
    if not isinstance(message, (str, bytes, bytearray)):
        return None
    try:
        data = json.loads(message)
    except ValueError:  # includes JSONDecodeError and bad UTF-8
        return None
    if isinstance(data, dict) and isinstance(data.get("type"), str):
        return data
    return None


class CommandTarget(Protocol):
    """What `run_device_command` needs from a card: a device and its feedback."""

    device: Any

    def set_pending(self, pending: bool) -> None: ...

    def sync_from_device(self) -> None: ...

    def show_error(self, message: str) -> None: ...


class DiscoveryThread(QThread):
    """Background thread for network discovery."""

    # Named discovery_done to avoid shadowing the built-in QThread.finished.
    discovery_done = pyqtSignal(list)  # type: ignore[call-arg]  # (ip, mac)
    discovery_failed = pyqtSignal(str)  # type: ignore[call-arg]

    def __init__(
        self,
        settings: Optional[DiscoverySettings] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._stop = threading.Event()
        self._settings = settings or DiscoverySettings()

    def request_stop(self) -> None:
        """Ask the scan to stop; it ends cooperatively, never forcibly."""
        self._stop.set()

    def stop_requested(self) -> bool:
        return self._stop.is_set()

    def run(self) -> None:
        """Run the discovery process."""
        try:
            hubs = discover_dirigera_hubs(
                max_workers=self._settings.max_workers,
                timeout_per_ip=self._settings.timeout,
                should_stop=self._stop.is_set,
                networks=self._settings.networks,
            )
            self.discovery_done.emit(hubs)
        except Exception as e:  # thread boundary: an escape would be lost
            log.exception("Hub discovery failed")
            self.discovery_failed.emit(str(e))


class ConnectWorker(QThread):
    """Verify hub credentials off the GUI thread (req-1, req-4)."""

    connected = pyqtSignal(object, str)  # type: ignore[call-arg]
    failed = pyqtSignal(str)  # type: ignore[call-arg]

    def __init__(
        self, token: str, ip_address: str, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._token = token
        self._ip_address = ip_address

    def run(self) -> None:
        """Probe the hub and emit either the verified hub or the error text."""
        try:
            hub = Hub(token=self._token, ip_address=self._ip_address)
            # Hub() never contacts the hub, so verify the credentials with a
            # lightweight authenticated probe before claiming success (req-1).
            hub.get("/home")
        except Exception as e:  # thread boundary: an escape would be lost
            log.exception("Connecting to the hub at %s failed", self._ip_address)
            self.failed.emit(str(e))
            return
        self.connected.emit(hub, self._ip_address)


class SceneTriggerWorker(QThread):
    """Trigger a scene off the GUI thread (req-4, t-51)."""

    triggered = pyqtSignal(object)  # type: ignore[call-arg]
    failed = pyqtSignal(object, str)  # type: ignore[call-arg]

    def __init__(self, scene: Scene, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._scene = scene

    def run(self) -> None:
        """Trigger the scene and emit it back, or the scene plus the error."""
        try:
            self._scene.trigger()
        except Exception as e:  # thread boundary: an escape would be lost
            log.exception("Triggering a scene failed")
            self.failed.emit(self._scene, str(e))
            return
        self.triggered.emit(self._scene)


class CommandWorker(QThread):
    """Send one device command off the GUI thread (req-4).

    On failure the device is reloaded here as well, since that is a hub call
    too; the GUI slot then only redraws the card from the real state (req-3).
    The card travels through the signals untouched: only the GUI thread uses
    it.
    """

    succeeded = pyqtSignal(object)  # type: ignore[call-arg]  # card
    failed = pyqtSignal(object, str, str)  # type: ignore[call-arg]

    def __init__(
        self,
        card: CommandTarget,
        command: Callable[[], None],
        action: str,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._card = card
        self._device = card.device
        self._command = command
        self._action = action

    def run(self) -> None:
        """Send the command; on error reload the device and emit the message."""
        try:
            self._command()
        except Exception as e:  # thread boundary: an escape would be lost
            log.exception("Command %r failed", self._action)
            try:
                self._device.reload()
            except Exception as reload_error:  # thread boundary, as above
                # The in-memory state is the best truth left.
                log.warning("Reloading the device failed: %s", reload_error)
            self.failed.emit(self._card, self._action, str(e))
            return
        self.succeeded.emit(self._card)


class RefreshWorker(QThread):
    """Fetch devices and scenes off the GUI thread (req-2, req-4)."""

    refreshed = pyqtSignal(list, list)  # type: ignore[call-arg]
    failed = pyqtSignal(str)  # type: ignore[call-arg]

    def __init__(self, hub: Hub, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._hub = hub

    def run(self) -> None:
        """Fetch both collections and emit them together, or the error text."""
        try:
            devices = self._hub.get_all_devices()
            scenes = self._hub.get_scenes()
        except Exception as e:  # thread boundary: an escape would be lost
            log.exception("Refreshing from the hub failed")
            self.failed.emit(str(e))
            return
        self.refreshed.emit(devices, scenes)


class EventWorker(QThread):
    """Listen to the hub websocket and report what arrives (t-16).

    `create_event_listener` blocks until the socket is closed for good and
    reconnects dropped sockets itself. The library callbacks run on this
    thread: they only emit signals and never raise or touch widgets. Events
    are a hint that something changed; the GUI answers with a refresh.
    """

    opened = pyqtSignal()  # type: ignore[call-arg]  # on every (re)connect: events in a gap are lost
    received = pyqtSignal(object)  # type: ignore[call-arg]  # parsed event
    lost = pyqtSignal()  # type: ignore[call-arg]  # the socket dropped or failed

    def __init__(self, hub: Hub, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._hub = hub
        self._stop = threading.Event()

    def request_stop(self) -> None:
        """Close the socket and end the thread; safe from any thread, repeatable."""
        self._stop.set()
        try:
            self._hub.stop_event_listener()
        except Exception as e:  # closing must never raise into the caller
            log.warning("Stopping the event listener failed: %s", e)

    def stop_requested(self) -> bool:
        return self._stop.is_set()

    def _on_open(self, *args: Any) -> None:
        if self._stop.is_set():
            # A stop that came before the socket existed could not close it.
            self.request_stop()
            return
        self.opened.emit()

    def _on_message(self, *args: Any) -> None:
        if self._stop.is_set() or not args:
            return
        event = parse_event(args[-1])
        if event is None:
            log.debug("Ignored an unreadable hub message")
            return
        log.debug("Hub event %s: %s", event["type"], event)
        self.received.emit(event)

    def _on_lost(self, *args: Any) -> None:
        if not self._stop.is_set():
            self.lost.emit()

    def run(self) -> None:
        """Block in the listener until it ends; report an unexpected end."""
        if self._stop.is_set():
            return
        try:
            self._hub.create_event_listener(
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_lost,
                on_close=self._on_lost,
                reconnect=EVENT_RECONNECT_S,
            )
        except Exception:  # thread boundary: an escape would be lost
            log.exception("The hub event listener failed")
        self._on_lost()
