import configparser
import os
from typing import Any, Dict, List, Optional, Tuple

from dirigera import Hub
from dirigera.devices.blinds import Blind, BlindsStateEnum
from dirigera.devices.light import Light
from dirigera.devices.outlet import Outlet
from dirigera.devices.scene import Scene
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QGroupBox,
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from network_discovery import discover_dirigera_hubs
from widgets.card import DeviceCard, device_sort_key
from widgets.slider import LabeledSlider
from widgets.switch import ToggleSwitch

# Constants
DEFAULT_BRIGHTNESS = 50


class DiscoveryThread(QThread):
    """Background thread for network discovery."""

    # Named discovery_done to avoid shadowing the built-in QThread.finished.
    discovery_done = pyqtSignal(list)  # List of (ip, mac) tuples

    def run(self):
        """Run the discovery process."""
        try:
            hubs = discover_dirigera_hubs()
            self.discovery_done.emit(hubs)
        except Exception:
            self.discovery_done.emit([])


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
                        self.ip_input.setText(config["hub"]["ip_address"])
                    if "token" in config["hub"]:
                        token = config["hub"]["token"]
                        if token and token != "YOUR_TOKEN_HERE":
                            self.token_input.setText(token)
            except Exception:
                pass  # Silently ignore config errors

    def init_ui(self):
        self.setWindowTitle("Dirigera Dashboard")
        self.setGeometry(100, 100, 1000, 700)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Connection section
        connection_group = QGroupBox("Hub Connection")
        connection_layout = QHBoxLayout()
        connection_group.setLayout(connection_layout)

        self.ip_label = QLabel("Hub IP:")
        connection_layout.addWidget(self.ip_label)

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("e.g., 192.168.1.100")
        connection_layout.addWidget(self.ip_input)

        self.discover_button = QPushButton("Discover")
        self.discover_button.clicked.connect(self.discover_hubs)
        connection_layout.addWidget(self.discover_button)

        self.token_label = QLabel("Token:")
        connection_layout.addWidget(self.token_label)

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Dirigera authentication token")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        connection_layout.addWidget(self.token_input)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_to_hub)
        connection_layout.addWidget(self.connect_button)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.refresh_button.setEnabled(False)
        connection_layout.addWidget(self.refresh_button)

        main_layout.addWidget(connection_group)

        # Status label
        self.status_label = QLabel("Not connected")
        main_layout.addWidget(self.status_label)

        # Tabs for Devices and Scenes
        self.tab_widget = QTabWidget()

        # Devices tab
        self.devices_tab = QWidget()
        self.devices_scroll = QScrollArea()
        self.devices_scroll.setWidgetResizable(True)
        self.devices_content = QWidget()
        self.devices_layout = QVBoxLayout(self.devices_content)
        self.devices_layout.addStretch()
        self.devices_scroll.setWidget(self.devices_content)

        devices_tab_layout = QVBoxLayout(self.devices_tab)
        devices_tab_layout.addWidget(self.devices_scroll)
        self.tab_widget.addTab(self.devices_tab, "Devices")

        # Scenes tab
        self.scenes_tab = QWidget()
        self.scenes_scroll = QScrollArea()
        self.scenes_scroll.setWidgetResizable(True)
        self.scenes_content = QWidget()
        self.scenes_layout = QVBoxLayout(self.scenes_content)
        self.scenes_layout.addStretch()
        self.scenes_scroll.setWidget(self.scenes_content)

        scenes_tab_layout = QVBoxLayout(self.scenes_tab)
        scenes_tab_layout.addWidget(self.scenes_scroll)
        self.tab_widget.addTab(self.scenes_tab, "Scenes")

        main_layout.addWidget(self.tab_widget)

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
        self.status_label.setText("Discovery canceled")

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
            self.status_label.setText("No hubs discovered")
            return

        if len(discovered_hubs) == 1:
            # Single hub found - use it directly
            ip, mac = discovered_hubs[0]
            self.ip_input.setText(ip)
            mac_info = f" ({mac})" if mac else ""
            self.status_label.setText(f"Discovered hub at {ip}{mac_info}")
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
                self.ip_input.setText(dialog.selected_ip)

    def connect_to_hub(self):
        ip_address = self.ip_input.text().strip()
        token = self.token_input.text().strip()

        if not ip_address or not token:
            QMessageBox.warning(
                self, "Input Error", "Please enter both IP address and token."
            )
            return

        try:
            self.hub = Hub(token=token, ip_address=ip_address)
            # Hub() never contacts the hub, so verify the credentials with a
            # lightweight authenticated probe before claiming success.
            self.hub.get("/home")
            self.status_label.setText(f"Connected to hub at {ip_address}")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.refresh_button.setEnabled(True)
            self.refresh_devices()
        except Exception as e:
            QMessageBox.critical(
                self, "Connection Error", f"Failed to connect to hub: {str(e)}"
            )
            self.status_label.setText(f"Connection failed: {str(e)}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")

    def refresh_devices(self):
        if not self.hub:
            return

        try:
            # Fetch everything before touching the UI, so a failed refresh
            # keeps the current view instead of leaving it blank.
            devices = self.hub.get_all_devices()
            scenes = self.hub.get_scenes()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh devices: {str(e)}")
            self.status_label.setText(f"Refresh failed: {str(e)}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            return

        # Clear existing widgets and rebuild from the fetched data
        self.clear_layout(self.devices_layout)
        self.clear_layout(self.scenes_layout)

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
        for room_name in sorted(devices_by_room.keys()):
            room_group = QGroupBox(room_name)
            room_layout = QVBoxLayout()
            room_group.setLayout(room_layout)

            # Sort devices in room for stable order (design-doc.md §8.1 rule 3)
            room_devices = sorted(devices_by_room[room_name], key=device_sort_key)

            for device in room_devices:
                card = self.create_device_widget(device)
                if card:
                    room_layout.addWidget(card)

            self.devices_layout.insertWidget(
                self.devices_layout.count() - 1, room_group
            )

        # Display scenes
        for scene in self.scenes:
            scene_widget = self.create_scene_widget(scene)
            self.scenes_layout.insertWidget(
                self.scenes_layout.count() - 1, scene_widget
            )

        self.status_label.setText(
            f"Found {len(self.devices)} devices in {len(devices_by_room)} rooms "
            f"and {len(self.scenes)} scenes"
        )

    def create_device_widget(self, device: Any) -> Optional[QWidget]:
        """Create a DeviceCard instance with connected action handlers."""
        return DeviceCard(
            device=device,
            on_toggle=self.toggle_device_power,
            on_brightness=self.set_light_brightness,
            on_blind_position=self.set_blind_position,
            on_blind_state=self.set_blind_state,
        )

    def create_scene_widget(self, scene: Scene) -> QWidget:
        """Create widget for a scene"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Scene name
        name_label = QLabel(scene.info.name)
        name_label.setMinimumWidth(300)
        font = QFont()
        font.setBold(True)
        name_label.setFont(font)
        layout.addWidget(name_label)

        # Scene icon if available
        icon_text = self.format_scene_icon(scene.info.icon)
        if icon_text:
            icon_label = QLabel(f"[{icon_text}]")
            icon_label.setStyleSheet("color: gray;")
            layout.addWidget(icon_label)

        layout.addStretch()

        # Trigger button
        trigger_button = QPushButton("Activate")
        trigger_button.clicked.connect(lambda: self.trigger_scene(scene))
        layout.addWidget(trigger_button)

        return widget

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

    def trigger_scene(self, scene: Scene):
        """Trigger a scene"""
        try:
            scene.trigger()
            QMessageBox.information(
                self,
                "Scene Activated",
                f"Scene '{scene.info.name}' has been activated.",
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to trigger scene: {str(e)}")

    def clear_layout(self, layout: QVBoxLayout):
        """Clear all widgets from a layout"""
        while layout.count() > 1:  # Keep the stretch at the end
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    @staticmethod
    def format_scene_icon(icon: Any) -> str:
        """Convert a scene icon enum value into a readable label."""
        if not icon:
            return ""
        val = getattr(icon, "value", str(icon))
        clean = str(val).removeprefix("scenes_").replace("_", " ").strip()
        return clean

    @staticmethod
    def get_device_name(device: Any) -> str:
        """Get the display name for a device"""
        return str(
            getattr(device, "custom_name", None)
            or getattr(getattr(device, "attributes", None), "custom_name", None)
            or "Unknown Device"
        )

    @staticmethod
    def get_room_name(device: Any) -> str:
        """Get the room name for a device"""
        # device.room is a pydantic Room model (or None), not a dict.
        room = getattr(device, "room", None)
        if room is None:
            return "Unknown Room"
        return room.name or "Unknown Room"
