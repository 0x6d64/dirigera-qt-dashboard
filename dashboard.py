import configparser
import os
from typing import Any, Dict, List, Optional, Tuple

from dirigera import Hub
from dirigera.devices.blinds import Blind
from dirigera.devices.light import Light
from dirigera.devices.outlet import Outlet
from dirigera.devices.scene import Scene
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
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
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from network_discovery import discover_dirigera_hubs

# Constants
DEFAULT_BRIGHTNESS = 50


class DiscoveryThread(QThread):
    """Background thread for network discovery."""

    finished = pyqtSignal(list)  # List of (ip, mac) tuples

    def run(self):
        """Run the discovery process."""
        try:
            hubs = discover_dirigera_hubs()
            self.finished.emit(hubs)
        except Exception:
            self.finished.emit([])


class HubSelectionDialog(QDialog):
    """Dialog for selecting a discovered hub or entering IP manually."""

    def __init__(self, discovered_hubs: List[Tuple[str, str]], parent=None):
        super().__init__(parent)
        self.selected_ip: Optional[str] = None
        self.discovered_hubs = discovered_hubs
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Select Dirigera Hub")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        if self.discovered_hubs:
            # Show discovered hubs
            label = QLabel(
                f"Found {len(self.discovered_hubs)} Dirigera hub(s) on your network:"
            )
            layout.addWidget(label)

            self.hub_list = QListWidget()
            for ip, mac in self.discovered_hubs:
                item = QListWidgetItem(f"{ip} (MAC: {mac})")
                item.setData(Qt.ItemDataRole.UserRole, ip)
                self.hub_list.addItem(item)
            self.hub_list.itemDoubleClicked.connect(self.on_hub_selected)
            layout.addWidget(self.hub_list)

            select_button = QPushButton("Select")
            select_button.clicked.connect(self.on_hub_selected)
            layout.addWidget(select_button)

            layout.addWidget(QLabel("Or enter IP address manually:"))
        else:
            label = QLabel("No Dirigera hubs found automatically.")
            layout.addWidget(label)
            layout.addWidget(QLabel("Please enter the IP address manually:"))

        # Manual IP entry
        manual_layout = QHBoxLayout()
        self.manual_ip_input = QLineEdit()
        self.manual_ip_input.setPlaceholderText("e.g., 192.168.1.100")
        manual_layout.addWidget(self.manual_ip_input)

        manual_button = QPushButton("Use This IP")
        manual_button.clicked.connect(self.on_manual_ip)
        manual_layout.addWidget(manual_button)

        layout.addLayout(manual_layout)

        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(cancel_button)

    def on_hub_selected(self):
        """Handle hub selection from list."""
        current_item = self.hub_list.currentItem()
        if current_item:
            self.selected_ip = current_item.data(Qt.ItemDataRole.UserRole)
            self.accept()

    def on_manual_ip(self):
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
        self.device_widgets: Dict[str, QWidget] = {}
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
        self.token_input.setPlaceholderText("Your Dirigera token")
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
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        main_layout.addWidget(self.status_label)

        # Tab widget for devices and scenes
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Devices tab
        self.devices_tab = QWidget()
        devices_layout = QVBoxLayout(self.devices_tab)

        # Scroll area for devices
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.devices_layout = QVBoxLayout(scroll_widget)
        self.devices_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        devices_layout.addWidget(scroll_area)

        self.tab_widget.addTab(self.devices_tab, "Devices")

        # Scenes tab
        self.scenes_tab = QWidget()
        scenes_layout = QVBoxLayout(self.scenes_tab)

        # Scroll area for scenes
        scenes_scroll_area = QScrollArea()
        scenes_scroll_area.setWidgetResizable(True)
        scenes_scroll_widget = QWidget()
        self.scenes_layout = QVBoxLayout(scenes_scroll_widget)
        self.scenes_layout.addStretch()
        scenes_scroll_area.setWidget(scenes_scroll_widget)
        scenes_layout.addWidget(scenes_scroll_area)

        self.tab_widget.addTab(self.scenes_tab, "Scenes")

    def discover_hubs(self):
        """Discover Dirigera hubs on the network."""
        # Show progress dialog
        progress = QProgressDialog(
            "Scanning network for Dirigera hubs...", "Cancel", 0, 0, self
        )
        progress.setWindowTitle("Discovering Hubs")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        # Create and start discovery thread
        self.discovery_thread = DiscoveryThread()
        self.discovery_thread.finished.connect(
            lambda hubs: self.on_discovery_complete(hubs, progress)
        )
        self.discovery_thread.start()

    def on_discovery_complete(
        self, discovered_hubs: List[Tuple[str, str]], progress: QProgressDialog
    ):
        """Handle completion of hub discovery."""
        progress.close()

        if not discovered_hubs:
            # No hubs found - show dialog to enter manually
            dialog = HubSelectionDialog([], self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_ip:
                self.ip_input.setText(dialog.selected_ip)
        elif len(discovered_hubs) == 1:
            # Exactly one hub found - use it automatically
            ip, mac = discovered_hubs[0]
            self.ip_input.setText(ip)
            QMessageBox.information(
                self,
                "Hub Discovered",
                f"Found Dirigera hub at {ip}\n(MAC: {mac})\n\n"
                "IP address has been filled in. Please enter your token and connect.",
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
            # Clear existing widgets
            self.clear_layout(self.devices_layout)
            self.clear_layout(self.scenes_layout)
            self.device_widgets.clear()

            # Get all devices
            self.devices = self.hub.get_all_devices()

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

                for device in devices_by_room[room_name]:
                    device_widget = self.create_device_widget(device)
                    if device_widget:
                        room_layout.addWidget(device_widget)
                        self.device_widgets[device.id] = device_widget

                self.devices_layout.insertWidget(
                    self.devices_layout.count() - 1, room_group
                )

            # Get and display scenes
            self.scenes = self.hub.get_scenes()
            for scene in self.scenes:
                scene_widget = self.create_scene_widget(scene)
                self.scenes_layout.insertWidget(
                    self.scenes_layout.count() - 1, scene_widget
                )

            self.status_label.setText(
                f"Found {len(self.devices)} devices in {len(devices_by_room)} rooms "
                f"and {len(self.scenes)} scenes"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh devices: {str(e)}")
            self.status_label.setText(f"Refresh failed: {str(e)}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")

    def create_device_widget(self, device: Any) -> Optional[QWidget]:
        """Create appropriate widget based on device type"""
        device_type = (
            device.device_type if hasattr(device, "device_type") else "unknown"
        )

        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Device name
        name_label = QLabel(self.get_device_name(device))
        name_label.setMinimumWidth(200)
        font = QFont()
        font.setBold(True)
        name_label.setFont(font)
        layout.addWidget(name_label)

        # Type label
        type_label = QLabel(f"({device_type})")
        type_label.setStyleSheet("color: gray;")
        layout.addWidget(type_label)

        layout.addStretch()

        # Add controls based on device type
        if device_type == "light":
            self.add_light_controls(layout, device)
        elif device_type == "blinds":
            self.add_blind_controls(layout, device)
        elif device_type == "outlet":
            self.add_outlet_controls(layout, device)
        else:
            # Generic device - just show it's present
            status_label = QLabel("✓")
            status_label.setStyleSheet("color: green; font-size: 16px;")
            layout.addWidget(status_label)

        return widget

    def add_light_controls(self, layout: QHBoxLayout, light: Light):
        """Add controls for a light device"""
        # On/Off toggle
        on_off_checkbox = QCheckBox("On")
        on_off_checkbox.setChecked(light.is_on)
        on_off_checkbox.stateChanged.connect(
            lambda state: self.toggle_light(light, state == Qt.CheckState.Checked)
        )
        layout.addWidget(on_off_checkbox)

        # Brightness slider if supported
        if (
            hasattr(light.attributes, "light_level")
            and light.attributes.light_level is not None
        ):
            brightness_label = QLabel("Brightness:")
            layout.addWidget(brightness_label)

            brightness_slider = QSlider(Qt.Orientation.Horizontal)
            brightness_slider.setMinimum(1)
            brightness_slider.setMaximum(100)
            brightness_slider.setValue(
                light.attributes.light_level or DEFAULT_BRIGHTNESS
            )
            brightness_slider.setMaximumWidth(200)
            brightness_slider.valueChanged.connect(
                lambda value: self.set_light_brightness(light, value)
            )
            layout.addWidget(brightness_slider)

            brightness_value_label = QLabel(f"{light.attributes.light_level}%")
            brightness_slider.valueChanged.connect(
                lambda value: brightness_value_label.setText(f"{value}%")
            )
            layout.addWidget(brightness_value_label)

    def add_blind_controls(self, layout: QHBoxLayout, blind: Blind):
        """Add controls for a blind device"""
        position_label = QLabel("Position:")
        layout.addWidget(position_label)

        position_slider = QSlider(Qt.Orientation.Horizontal)
        position_slider.setMinimum(0)
        position_slider.setMaximum(100)
        current_position = getattr(blind.attributes, "blinds_current_level", 0)
        position_slider.setValue(current_position)
        position_slider.setMaximumWidth(200)
        position_slider.valueChanged.connect(
            lambda value: self.set_blind_position(blind, value)
        )
        layout.addWidget(position_slider)

        position_value_label = QLabel(f"{current_position}%")
        position_slider.valueChanged.connect(
            lambda value: position_value_label.setText(f"{value}%")
        )
        layout.addWidget(position_value_label)

    def add_outlet_controls(self, layout: QHBoxLayout, outlet: Outlet):
        """Add controls for an outlet device"""
        on_off_checkbox = QCheckBox("On")
        on_off_checkbox.setChecked(outlet.is_on)
        on_off_checkbox.stateChanged.connect(
            lambda state: self.toggle_outlet(outlet, state == Qt.CheckState.Checked)
        )
        layout.addWidget(on_off_checkbox)

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
        if hasattr(scene.info, "icon") and scene.info.icon:
            icon_label = QLabel(f"[{scene.info.icon}]")
            icon_label.setStyleSheet("color: gray;")
            layout.addWidget(icon_label)

        layout.addStretch()

        # Trigger button
        trigger_button = QPushButton("Activate")
        trigger_button.clicked.connect(lambda: self.trigger_scene(scene))
        layout.addWidget(trigger_button)

        return widget

    def toggle_light(self, light: Light, turn_on: bool):
        """Toggle light on/off"""
        try:
            if turn_on:
                light.set_light(lamp_on=True)
            else:
                light.set_light(lamp_on=False)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to toggle light: {str(e)}")

    def set_light_brightness(self, light: Light, brightness: int):
        """Set light brightness"""
        try:
            light.set_light_level(brightness)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to set brightness: {str(e)}")

    def set_blind_position(self, blind: Blind, position: int):
        """Set blind position"""
        try:
            blind.set_target_level(position)
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"Failed to set blind position: {str(e)}"
            )

    def toggle_outlet(self, outlet: Outlet, turn_on: bool):
        """Toggle outlet on/off"""
        try:
            if turn_on:
                outlet.set_on(True)
            else:
                outlet.set_on(False)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to toggle outlet: {str(e)}")

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
    def get_device_name(device: Any) -> str:
        """Get the display name for a device"""
        return (
            getattr(device, "custom_name", None)
            or getattr(getattr(device, "attributes", None), "custom_name", None)
            or "Unknown Device"
        )

    @staticmethod
    def get_room_name(device: Any) -> str:
        """Get the room name for a device"""
        room = getattr(device, "room", None) or {}
        return room.get("name", "Unknown Room")
