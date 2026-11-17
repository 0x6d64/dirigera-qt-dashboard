import configparser
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, override

from dirigera import Hub
from dirigera.devices.blinds import Blind, BlindsStateEnum
from dirigera.devices.light import Light
from dirigera.devices.outlet import Outlet
from dirigera.devices.scene import Scene
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import theme
from network_discovery import discover_dirigera_hubs
from widgets.card import DeviceCard, device_sort_key
from widgets.chip import StatusChip
from widgets.connection import ConnectionBlock
from widgets.energy import EnergyView
from widgets.grid import CardGrid
from widgets.scene import SceneTile
from widgets.segments import SegmentedControl
from widgets.slider import LabeledSlider
from widgets.switch import ToggleSwitch

# Constants
DEFAULT_BRIGHTNESS = 50

# View switcher segments, in display order (design-doc.md §4.2).
VIEW_ROOMS = 0
VIEW_SCENES = 1
VIEW_ENERGY = 2


def widget_name(widget: QWidget) -> str:
    """Return the display name a card or scene tile is filtered by (t-50)."""
    return str(getattr(widget, "full_name", "") or "")


class DiscoveryThread(QThread):
    """Background thread for network discovery."""

    # Named discovery_done to avoid shadowing the built-in QThread.finished.
    discovery_done = pyqtSignal(list)  # type: ignore[call-arg]  # (ip, mac)

    def run(self):
        """Run the discovery process."""
        try:
            hubs = discover_dirigera_hubs()
            self.discovery_done.emit(hubs)
        except Exception:
            self.discovery_done.emit([])


class ConnectWorker(QThread):
    """Verify hub credentials off the GUI thread (req-1, req-4)."""

    connected = pyqtSignal(object, str)  # type: ignore[call-arg]
    failed = pyqtSignal(str)  # type: ignore[call-arg]

    def __init__(self, token: str, ip_address: str, parent=None):
        super().__init__(parent)
        self._token = token
        self._ip_address = ip_address

    def run(self):
        """Probe the hub and emit either the verified hub or the error text."""
        try:
            hub = Hub(token=self._token, ip_address=self._ip_address)
            # Hub() never contacts the hub, so verify the credentials with a
            # lightweight authenticated probe before claiming success (req-1).
            hub.get("/home")
        except Exception as e:
            self.failed.emit(str(e))
            return
        self.connected.emit(hub, self._ip_address)


class SceneTriggerWorker(QThread):
    """Trigger a scene off the GUI thread (req-4, t-51)."""

    triggered = pyqtSignal(object)  # type: ignore[call-arg]
    failed = pyqtSignal(object, str)  # type: ignore[call-arg]

    def __init__(self, scene: Scene, parent=None):
        super().__init__(parent)
        self._scene = scene

    def run(self):
        """Trigger the scene and emit it back, or the scene plus the error."""
        try:
            self._scene.trigger()
        except Exception as e:
            self.failed.emit(self._scene, str(e))
            return
        self.triggered.emit(self._scene)


class RefreshWorker(QThread):
    """Fetch devices and scenes off the GUI thread (req-2, req-4)."""

    refreshed = pyqtSignal(list, list)  # type: ignore[call-arg]
    failed = pyqtSignal(str)  # type: ignore[call-arg]

    def __init__(self, hub: Hub, parent=None):
        super().__init__(parent)
        self._hub = hub

    def run(self):
        """Fetch both collections and emit them together, or the error text."""
        try:
            devices = self._hub.get_all_devices()
            scenes = self._hub.get_scenes()
        except Exception as e:
            self.failed.emit(str(e))
            return
        self.refreshed.emit(devices, scenes)


class HubSelectionDialog(QDialog):
    """Dialog for selecting a discovered hub or entering IP manually."""

    def __init__(self, hubs: List[Tuple[str, str]], parent=None):
        super().__init__(parent)
        self.selected_ip: Optional[str] = None
        self.init_ui(hubs)

    def init_ui(self, hubs: List[Tuple[str, str]]):
        self.setWindowTitle("Select Dirigera Hub")
        self.setModal(True)
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        # Instructions
        label = QLabel("Select a Dirigera hub from the list below:")
        layout.addWidget(label)

        # Hub list
        self.hub_list = QListWidget()
        for ip, mac in hubs:
            item_text = f"Hub at {ip}"
            if mac:
                item_text += f" ({mac})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, ip)
            self.hub_list.addItem(item)

        if hubs:
            self.hub_list.setCurrentRow(0)

        layout.addWidget(self.hub_list)

        # Manual entry option
        manual_layout = QHBoxLayout()
        manual_label = QLabel("Or enter IP manually:")
        self.manual_ip_input = QLineEdit()
        self.manual_ip_input.setPlaceholderText("192.168.1.100")
        manual_layout.addWidget(manual_label)
        manual_layout.addWidget(self.manual_ip_input)
        layout.addLayout(manual_layout)

        # Buttons
        button_layout = QHBoxLayout()
        select_button = QPushButton("Select")
        select_button.clicked.connect(self.accept_selection)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(select_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def accept_selection(self):
        """Handle hub selection."""
        # Check if manual IP was entered
        manual_ip = self.manual_ip_input.text().strip()
        if manual_ip:
            self.selected_ip = manual_ip
            self.accept()
            return

        # Otherwise use selected item from list
        current_item = self.hub_list.currentItem()
        if current_item:
            self.selected_ip = current_item.data(Qt.ItemDataRole.UserRole)
            self.accept()
        else:
            QMessageBox.warning(
                self, "Selection Error", "Please select a hub or enter an IP."
            )

    def handle_manual_ip(self):
        """Handle manual IP entry."""
        ip = self.manual_ip_input.text().strip()
        if ip:
            self.selected_ip = ip
            self.accept()
        else:
            QMessageBox.warning(self, "Input Error", "Please enter an IP address.")


class DirigeraDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.hub: Optional[Hub] = None
        self.devices: List[Any] = []
        self.scenes: List[Scene] = []
        self._hub_ip: Optional[str] = None
        self._last_refresh: Optional[datetime] = None
        self._connect_worker: Optional[ConnectWorker] = None
        self._refresh_worker: Optional[RefreshWorker] = None
        self._scene_workers: List[SceneTriggerWorker] = []
        # (room section, its card grid), in display order, for search filtering.
        self._room_sections: List[Tuple[QWidget, CardGrid]] = []
        self.init_ui()
        self.load_config()

    def load_config(self):
        """Load configuration from config.ini if it exists"""
        config_path = "config.ini"
        if os.path.exists(config_path):
            try:
                config = configparser.ConfigParser()
                config.read(config_path)
                if "hub" in config:
                    if "ip_address" in config["hub"]:
                        self.connection_block.ip_input.setText(
                            config["hub"]["ip_address"]
                        )
                    if "token" in config["hub"]:
                        token = config["hub"]["token"]
                        if token and token != "YOUR_TOKEN_HERE":
                            self.connection_block.token_input.setText(token)
            except Exception:
                pass  # Silently ignore config errors

    def init_ui(self):
        self.setWindowTitle("Dirigera Dashboard")
        self.setGeometry(100, 100, 1000, 700)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar (design-doc.md §4.2)
        self.header = self.build_header()
        main_layout.addWidget(self.header)

        # Caption line for detailed status messages
        status_row = QWidget()
        status_row_layout = QHBoxLayout(status_row)
        status_row_layout.setContentsMargins(theme.SP20, theme.SP8, theme.SP20, 0)
        self.status_label = QLabel("")
        self.status_label.setProperty("role", "caption")
        status_row_layout.addWidget(self.status_label)
        status_row_layout.addStretch()
        main_layout.addWidget(status_row)

        # Content area: the centred connection block until a hub is
        # connected, then the device and scene views (design-doc.md §9.1).
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, 1)

        self.connection_block = ConnectionBlock()
        self.connection_block.discover_requested.connect(self.discover_hubs)
        self.connection_block.connect_requested.connect(self.connect_to_hub)
        self.content_stack.addWidget(self.connection_block)

        # Tabs for Devices and Scenes (become views with t-49)
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        # Devices tab
        self.devices_tab = QWidget()
        self.devices_scroll = QScrollArea()
        self.devices_scroll.setWidgetResizable(True)
        self.devices_content = QWidget()
        self.devices_layout = QVBoxLayout(self.devices_content)
        # Content padding 24/20/24 and 24 px between room sections
        # (design-doc.md §4.3).
        self.devices_layout.setContentsMargins(
            theme.SP24, theme.SP20, theme.SP24, theme.SP24
        )
        self.devices_layout.setSpacing(theme.SP24)
        self.devices_layout.addStretch()
        self.devices_scroll.setWidget(self.devices_content)

        devices_tab_layout = QVBoxLayout(self.devices_tab)
        devices_tab_layout.addWidget(self.devices_scroll)
        self.tab_widget.addTab(self.devices_tab, "Devices")

        # Scenes tab: same flow grid as the rooms view (§8.10, §4.3).
        self.scenes_tab = QWidget()
        self.scenes_scroll = QScrollArea()
        self.scenes_scroll.setWidgetResizable(True)
        self.scenes_content = QWidget()
        self.scenes_layout = QVBoxLayout(self.scenes_content)
        self.scenes_layout.setContentsMargins(
            theme.SP24, theme.SP20, theme.SP24, theme.SP24
        )
        self.scenes_layout.setSpacing(theme.SP24)
        self.scenes_grid = CardGrid()
        self.scenes_layout.addWidget(self.scenes_grid)
        self.scenes_layout.addStretch()
        self.scenes_scroll.setWidget(self.scenes_content)

        scenes_tab_layout = QVBoxLayout(self.scenes_tab)
        scenes_tab_layout.addWidget(self.scenes_scroll)
        self.tab_widget.addTab(self.scenes_tab, "Scenes")

        # Energy tab (t-49)
        self.energy_view = EnergyView()
        self.tab_widget.addTab(self.energy_view, "Energy")

        # The segmented switcher is the only navigation; a visible tab bar
        # would duplicate it (design-doc.md §4.2).
        self.tab_widget.tabBar().hide()

        # Views page: stale-data caption above the tabs, so a failed refresh
        # can say how old the visible data is (design-doc.md §3.1 row 4).
        self.views_page = QWidget()
        views_layout = QVBoxLayout(self.views_page)
        views_layout.setContentsMargins(0, 0, 0, 0)
        views_layout.setSpacing(0)

        self.stale_label = QLabel("")
        self.stale_label.setProperty("role", "caption")
        self.stale_label.setContentsMargins(theme.SP24, theme.SP12, theme.SP24, 0)
        self.stale_label.hide()
        views_layout.addWidget(self.stale_label)
        views_layout.addWidget(self.tab_widget, 1)
        self.content_stack.addWidget(self.views_page)

        # Start in the not-connected state (design-doc.md §9.1).
        self.show_connection_block()

    def build_header(self) -> QWidget:
        """Build the fixed-height header bar (design-doc.md §4.2)."""
        header = QWidget()
        header.setProperty("role", "header")
        header.setFixedHeight(56)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(theme.SP20, theme.SP12, theme.SP20, theme.SP12)
        layout.setSpacing(theme.SP12)

        title = QLabel("Dirigera")
        title.setProperty("role", "appTitle")
        layout.addWidget(title)

        self.status_chip = StatusChip("Not connected", "neutral")
        layout.addWidget(self.status_chip)

        layout.addStretch(1)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search devices and scenes")
        # 260 px at rest, shrinking at narrow widths (design-doc.md §8.8, §11).
        self.search_input.setMinimumWidth(160)
        self.search_input.setMaximumWidth(260)
        # Live filtering; the field stays disabled until a hub is connected,
        # which is when there is something to filter (design-doc.md §9.1).
        self.search_input.setEnabled(False)
        self.search_input.textChanged.connect(self.filter_devices)
        layout.addWidget(self.search_input)

        self.view_switcher = SegmentedControl(["Rooms", "Scenes", "Energy"])
        self.view_switcher.current_changed.connect(self.on_view_selected)
        layout.addWidget(self.view_switcher)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.refresh_button.setEnabled(False)
        layout.addWidget(self.refresh_button)

        return header

    def show_connection_block(self, busy: bool = False) -> None:
        """Show the not-connected block instead of the views (§9.1).

        `busy` keeps the form visible but disabled while a connection attempt
        is in flight.
        """
        self.connection_block.set_busy(busy)
        self.content_stack.setCurrentWidget(self.connection_block)
        self._set_view_controls_enabled(False)

    def show_views(self) -> None:
        """Switch the content area to the device and scene views."""
        self.connection_block.set_busy(False)
        self.content_stack.setCurrentWidget(self.views_page)
        self._set_view_controls_enabled(True)

    def _set_view_controls_enabled(self, enabled: bool) -> None:
        """Enable view controls only while a hub is connected (§9.1).

        The search field is inert without data, so it is disabled and cleared
        in the not-connected state; clearing also drops any active filter so
        reconnecting starts from the full list.
        """
        for button in self.view_switcher.buttons():
            button.setEnabled(enabled)
        self.search_input.setEnabled(enabled)
        if not enabled:
            self.search_input.clear()

    def on_view_selected(self, index: int) -> None:
        """Drive the tab widget from the segmented view switcher."""
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(index)

    def on_tab_changed(self, index: int) -> None:
        """Keep the view switcher in sync when the tab changes elsewhere."""
        if self.view_switcher.current_index() != index:
            self.view_switcher.set_current(index)

    def set_status_text(self, text: str, tone: Optional[str] = None) -> None:
        """Set the caption under the header, optionally coloured by token."""
        self.status_label.setText(text)
        self.status_label.setProperty("tone", tone or "")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def discover_hubs(self):
        """Start the hub discovery process in a background thread."""
        # Create and configure the progress dialog
        self.progress_dialog = QProgressDialog(
            "Scanning local network for Dirigera hubs...", "Cancel", 0, 0, self
        )
        self.progress_dialog.setWindowTitle("Discovering Hubs")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)

        # Create and start the discovery thread
        self.discovery_thread = DiscoveryThread()
        self.discovery_thread.discovery_done.connect(self.on_discovery_finished)

        # Handle dialog cancellation
        self.progress_dialog.canceled.connect(self.on_discovery_canceled)

        # Show the dialog and start the thread
        self.progress_dialog.show()
        self.discovery_thread.start()

    def on_discovery_canceled(self):
        """Handle cancellation of the discovery process."""
        if hasattr(self, "discovery_thread") and self.discovery_thread.isRunning():
            self.discovery_thread.terminate()
            self.discovery_thread.wait()
        self.set_status_text("Discovery canceled")

    def on_discovery_finished(self, discovered_hubs: List[Tuple[str, str]]):
        """Handle completion of the discovery process."""
        # Close the progress dialog
        if hasattr(self, "progress_dialog"):
            self.progress_dialog.close()

        if not discovered_hubs:
            QMessageBox.information(
                self,
                "Discovery Result",
                "No Dirigera hubs found on the local network.\n\n"
                "Please ensure:\n"
                "1. Your Dirigera hub is powered on and connected to the network\n"
                "2. Your computer is on the same network subnet as the hub\n"
                "3. You can also enter the IP address manually if you know it",
            )
            self.set_status_text("No hubs discovered")
            return

        if len(discovered_hubs) == 1:
            # Single hub found - use it directly
            ip, mac = discovered_hubs[0]
            self.connection_block.ip_input.setText(ip)
            mac_info = f" ({mac})" if mac else ""
            self.set_status_text(f"Discovered hub at {ip}{mac_info}")
            QMessageBox.information(
                self,
                "Hub Discovered",
                f"Found Dirigera hub at {ip}{mac_info}!\n\n"
                "The IP address has been filled in. Please enter your "
                "authentication token and click Connect.",
            )
        else:
            # Multiple hubs found - let user choose
            dialog = HubSelectionDialog(discovered_hubs, self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_ip:
                self.connection_block.ip_input.setText(dialog.selected_ip)

    def connect_to_hub(self):
        """Verify the entered credentials in a background thread (t-17)."""
        if self._connect_worker is not None:
            return  # a probe is already in flight

        ip_address, token = self.connection_block.credentials()

        if not ip_address or not token:
            QMessageBox.warning(
                self, "Input Error", "Please enter both IP address and token."
            )
            return

        # State 2 of design-doc.md §3.1: the form is disabled and the chip
        # reports progress while the credentials are verified.
        self.status_chip.set_status("Connecting…", "neutral")
        self.show_connection_block(busy=True)

        worker = ConnectWorker(token, ip_address, self)
        worker.connected.connect(self._on_connected)
        worker.failed.connect(self._on_connect_failed)
        worker.finished.connect(self._on_connect_worker_done)
        self._connect_worker = worker
        worker.start()

    def _on_connected(self, hub: Hub, ip_address: str) -> None:
        """Adopt the verified hub and load its data."""
        self.hub = hub
        self._hub_ip = ip_address
        self.status_chip.set_status(f"Hub online · {ip_address}", "ok")
        self.set_status_text(f"Connected to hub at {ip_address}", "ok")
        self.refresh_button.setEnabled(True)
        self.show_views()
        self.refresh_devices()

    def _on_connect_failed(self, message: str) -> None:
        """Report a failed attempt and hand the form back to the user."""
        # A half-built hub must not look connected.
        self.hub = None
        self.show_connection_block()
        self.status_chip.set_status("Hub unreachable", "warn")
        self.set_status_text(f"Connection failed: {message}", "danger")
        QMessageBox.critical(
            self, "Connection Error", f"Failed to connect to hub: {message}"
        )

    def _on_connect_worker_done(self) -> None:
        self._connect_worker = None

    def refresh_devices(self):
        """Start a background refresh (t-17)."""
        hub = self.hub
        if hub is None:
            return
        if self._refresh_worker is not None:
            return  # one fetch at a time

        # Disable Refresh while loading so clicks cannot stack up fetches.
        self.refresh_button.setEnabled(False)

        worker = RefreshWorker(hub, self)
        worker.refreshed.connect(self._on_refreshed)
        worker.failed.connect(self._on_refresh_failed)
        worker.finished.connect(self._on_refresh_worker_done)
        self._refresh_worker = worker
        worker.start()

    def _on_refreshed(self, devices: List[Any], scenes: List[Scene]) -> None:
        """Rebuild the views from a successful fetch."""
        self._last_refresh = datetime.now()
        self.stale_label.hide()
        if self._hub_ip:
            self.status_chip.set_status(f"Hub online · {self._hub_ip}", "ok")

        # Clear existing widgets and rebuild from the fetched data
        self.clear_layout(self.devices_layout)
        self.scenes_grid.clear()

        self.devices = devices
        self.scenes = scenes

        # Group devices by room
        devices_by_room: Dict[str, List[Any]] = {}
        for device in self.devices:
            room_name = self.get_room_name(device)
            if room_name not in devices_by_room:
                devices_by_room[room_name] = []
            devices_by_room[room_name].append(device)

        # Create UI for each room
        sections: List[Tuple[QWidget, CardGrid]] = []
        for room_name in sorted(devices_by_room.keys()):
            section, grid = self.create_room_section(
                room_name, devices_by_room[room_name]
            )
            self.devices_layout.insertWidget(self.devices_layout.count() - 1, section)
            sections.append((section, grid))
        self._room_sections = sections

        # Display scenes as tiles in the same reflowing grid as the rooms.
        self.scenes_grid.set_cards(
            [self.create_scene_tile(scene) for scene in self.scenes]
        )

        # Energy view: outlets and electrical sensors grouped by room (§9.4).
        energy_by_room: Dict[str, List[Any]] = {}
        for device in self.devices:
            if not self.is_energy_device(device):
                continue
            room_name = self.get_room_name(device)
            energy_by_room.setdefault(room_name, []).append(device)
        self.energy_view.set_rooms(
            [
                (self.format_room_label(room), sorted(devices, key=device_sort_key))
                for room, devices in sorted(energy_by_room.items())
            ]
        )

        self.set_status_text(
            f"Found {len(self.devices)} devices in {len(devices_by_room)} rooms "
            f"and {len(self.scenes)} scenes"
        )

        # A rebuild resets every card to visible, so put the active filter back
        # on the fresh widgets (t-50).
        self.filter_devices(self.search_input.text())

    def filter_devices(self, query: str) -> None:
        """Filter device cards and scene tiles by name as the user types (§8.8).

        Matching is case-insensitive and applies to the whole name. A room
        section hides only when none of its cards match, and hidden cards keep
        their position so clearing the filter restores the previous order.
        Scenes are filtered on their own grid; the Energy view is unaffected.
        """
        needle = query.strip().casefold()

        def matches(name: str) -> bool:
            return not needle or needle in name.casefold()

        for section, grid in self._room_sections:
            visible = grid.apply_filter(lambda card: matches(widget_name(card)))
            section.setVisible(visible > 0 or not needle)

        for tile in self.scenes_grid.cards():
            tile.setVisible(matches(widget_name(tile)))
        self.scenes_grid.updateGeometry()

    def _on_refresh_failed(self, message: str) -> None:
        """Keep the last good data and say how old it is (§3.1 row 4)."""
        self.status_chip.set_status("Hub unreachable", "warn")
        self.set_status_text(f"Refresh failed: {message}", "danger")
        if self._last_refresh is not None:
            self.stale_label.setText(f"Showing data from {self._last_refresh:%H:%M}")
            self.stale_label.show()
        QMessageBox.critical(self, "Error", f"Failed to refresh devices: {message}")

    def _on_refresh_worker_done(self) -> None:
        self._refresh_worker = None
        self.refresh_button.setEnabled(self.hub is not None)

    def create_room_section(
        self, room_name: str, devices: List[Any]
    ) -> Tuple[QWidget, CardGrid]:
        """Build one room section: section label plus reflowing card grid."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SP12)  # label-to-grid gap (design-doc.md §4.3)

        label = QLabel(self.format_room_label(room_name))
        label.setProperty("role", "section")
        layout.addWidget(label)

        # Sort devices in room for stable order (design-doc.md §8.1 rule 3);
        # the sort key is deterministic, so refresh cycles keep the same order.
        cards = [
            self.create_device_widget(device)
            for device in sorted(devices, key=device_sort_key)
        ]
        grid = CardGrid()
        grid.set_cards([card for card in cards if card is not None])
        layout.addWidget(grid)

        return section, grid

    def create_device_widget(self, device: Any) -> Optional[QWidget]:
        """Create a DeviceCard instance with connected action handlers."""
        return DeviceCard(
            device=device,
            on_toggle=self.toggle_device_power,
            on_brightness=self.set_light_brightness,
            on_blind_position=self.set_blind_position,
            on_blind_state=self.set_blind_state,
        )

    def create_scene_tile(self, scene: Scene) -> SceneTile:
        """Create a scene tile wired to the activation handler (§8.10)."""
        return SceneTile(scene, on_activate=self.trigger_scene)

    def toggle_device_power(self, device: Any, turn_on: bool, control: ToggleSwitch):
        """Toggle power for a light or outlet device."""
        dtype = getattr(device, "device_type", "unknown")
        try:
            if dtype == "light":
                device.set_light(lamp_on=turn_on)
            elif dtype == "outlet":
                device.set_on(turn_on)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to toggle {dtype}: {str(e)}")
            self.sync_control_from_device(device, control)

    def toggle_light(self, light: Light, turn_on: bool, control: ToggleSwitch):
        """Toggle light on/off (kept for backwards compatibility)."""
        self.toggle_device_power(light, turn_on, control)

    def set_light_brightness(
        self, light: Light, brightness: int, control: LabeledSlider
    ):
        """Set light brightness."""
        try:
            light.set_light_level(brightness)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to set brightness: {str(e)}")
            self.sync_control_from_device(light, control)

    def set_blind_position(self, blind: Blind, position: int, control: LabeledSlider):
        """Set blind position."""
        try:
            blind.set_target_level(position)
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"Failed to set blind position: {str(e)}"
            )
            self.sync_control_from_device(blind, control)

    def set_blind_state(self, blind: Blind, action: str) -> None:
        """Trigger blind movement state (Up, Down, Stop)."""
        action_map = {
            "Up": BlindsStateEnum.UP,
            "Down": BlindsStateEnum.DOWN,
            "Stop": BlindsStateEnum.STOPPED,
        }
        enum_val = action_map.get(action)
        if not enum_val:
            return
        try:
            blind.set_state(enum_val)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to set blind state: {str(e)}")

    def toggle_outlet(self, outlet: Outlet, turn_on: bool, control: ToggleSwitch):
        """Toggle outlet on/off (kept for backwards compatibility)."""
        self.toggle_device_power(outlet, turn_on, control)

    def sync_control_from_device(self, device: Any, control: QWidget) -> None:
        """Restore a control's value from the device's actual state.

        Used after a failed command so the UI reflects reality instead of the
        intended value. Reloads the device first; if that fails too, the
        in-memory state is the best available truth.
        """
        try:
            device.reload()
        except Exception:
            pass
        if isinstance(control, ToggleSwitch):
            control.blockSignals(True)
            control.setChecked(bool(getattr(device.attributes, "is_on", False)))
            control.blockSignals(False)
        elif isinstance(control, LabeledSlider):
            level = getattr(device.attributes, "light_level", None)
            if level is None:
                level = getattr(device.attributes, "blinds_current_level", None)
            control.blockSignals(True)
            control.set_value(level or 0)
            control.blockSignals(False)

    def trigger_scene(self, tile: SceneTile) -> None:
        """Trigger a scene in a worker thread (req-4, t-51).

        Feedback stays inline in the tile: the design forbids a modal dialog
        for scene activation (§8.10.3).
        """
        self._scene_workers = [w for w in self._scene_workers if w.isRunning()]
        tile.set_busy(True)

        worker = SceneTriggerWorker(tile.scene, self)
        worker.triggered.connect(self._on_scene_triggered)
        worker.failed.connect(self._on_scene_failed)
        self._scene_workers.append(worker)
        worker.start()

    def _on_scene_triggered(self, scene: Scene) -> None:
        """Show the transient "Activated" confirmation on the tile."""
        tile = self._scene_tile_for(scene)
        if tile is not None:
            tile.show_activated()

    def _on_scene_failed(self, scene: Scene, message: str) -> None:
        """Report a failed activation inline instead of with a dialog."""
        tile = self._scene_tile_for(scene)
        if tile is not None:
            tile.show_error(message)

    def _scene_tile_for(self, scene: Scene) -> Optional[SceneTile]:
        """Return the tile displaying `scene`, if it is still on screen."""
        for card in self.scenes_grid.cards():
            if isinstance(card, SceneTile) and card.scene is scene:
                return card
        return None

    def clear_layout(self, layout: QVBoxLayout) -> None:
        """Clear all widgets from a layout."""
        while layout.count() > 1:  # Keep the stretch at the end
            item = layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @override
    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        """Wait for in-flight hub calls so no worker outlives the window."""
        workers: List[Optional[QThread]] = [
            self._connect_worker,
            self._refresh_worker,
            *self._scene_workers,
        ]
        for worker in workers:
            if worker is not None and worker.isRunning():
                worker.requestInterruption()
                worker.wait(2000)
        super().closeEvent(event)

    @staticmethod
    def get_device_name(device: Any) -> str:
        """Get the display name for a device"""
        return str(
            getattr(device, "custom_name", None)
            or getattr(getattr(device, "attributes", None), "custom_name", None)
            or "Unknown Device"
        )

    @staticmethod
    def format_room_label(room_name: str) -> str:
        """Sentence-case a room name for a section label (design-doc.md §8.9).

        Only the first character is capitalised so acronyms and proper nouns a
        user typed into the IKEA app keep their casing.
        """
        name = room_name.strip()
        if not name:
            return "Unknown room"
        return name[0].upper() + name[1:]

    @staticmethod
    def is_energy_device(device: Any) -> bool:
        """Return True for devices that can report energy data (§9.4)."""
        return getattr(device, "device_type", "") in ("outlet", "electrical_sensor")

    @staticmethod
    def get_room_name(device: Any) -> str:
        """Get the room name for a device"""
        # device.room is a pydantic Room model (or None), not a dict.
        room = getattr(device, "room", None)
        if room is None:
            return "Unknown Room"
        return room.name or "Unknown Room"
