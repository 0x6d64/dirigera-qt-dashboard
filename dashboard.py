from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QGroupBox,
    QSlider,
    QMessageBox,
    QTabWidget,
    QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from dirigera import Hub
from dirigera.devices.light import Light
from dirigera.devices.blinds import Blind
from dirigera.devices.outlet import Outlet
from dirigera.devices.scene import Scene


class DirigeraDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.hub: Optional[Hub] = None
        self.devices: List[Any] = []
        self.scenes: List[Scene] = []
        self.device_widgets: Dict[str, QWidget] = {}
        self.init_ui()

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
                room_name = getattr(device, "room", {}).get("name", "Unknown Room")
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
        name_label = QLabel(
            getattr(device, "custom_name", None)
            or getattr(device.attributes, "custom_name", "Unknown Device")
        )
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
            lambda state: self.toggle_light(light, state == Qt.CheckState.Checked.value)
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
            brightness_slider.setValue(light.attributes.light_level or 50)
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
        position_slider.setValue(current_position or 0)
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
            lambda state: self.toggle_outlet(
                outlet, state == Qt.CheckState.Checked.value
            )
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
