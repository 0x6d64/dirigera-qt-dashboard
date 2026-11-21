import configparser
import ipaddress
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, cast, override

from dirigera import Hub
from dirigera.devices.air_purifier import FanModeEnum
from dirigera.devices.blinds import BlindsStateEnum
from dirigera.devices.scene import Scene
from PyQt6 import sip
from PyQt6.QtCore import QEvent, Qt, QThread, QTimer
from PyQt6.QtGui import QCloseEvent, QResizeEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
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
from adaptive import active_profile_id, profile_options
from network_discovery import (
    get_local_networks,
    hosts_to_scan,
)
from rooms import (
    format_room_label,
    get_room,
    group_by_room,
    is_energy_device,
    room_colour_name,
)
from settings import (
    DiscoverySettings,
    EnergySettings,
    parse_discovery_settings,
    parse_energy_settings,
    ui_settings,
)
from widgets.card import DeviceCard, device_sort_key
from widgets.cardbase import RoomSectionHeader, label_style
from widgets.chip import StatusChip
from widgets.connection import ConnectionBlock
from widgets.energy import EnergyCard, EnergyView
from widgets.grid import CardGrid
from widgets.scene import SCENE_MIN_WIDTH, SceneTile
from widgets.segments import SegmentedControl
from widgets.switch import ToggleSwitch
from workers import (
    CommandTarget,
    CommandWorker,
    ConnectWorker,
    DiscoveryThread,
    EventWorker,
    RefreshWorker,
    SceneTriggerWorker,
)

log = logging.getLogger(__name__)

# Seconds between automatic background refreshes (req-13, t-56).
POLL_INTERVAL_S = 30
# While live events arrive the poll is only a safety net (t-16).
LIVE_POLL_INTERVAL_S = 300
# Events within this window cost one refresh; a metering plug can report every
# second, and each refresh is a full fetch from the hub (t-16).
EVENT_COALESCE_MS = 1000
# Delay before the refresh that follows a scene activation: the hub applies a
# scene asynchronously, so an immediate fetch can miss the change.
SCENE_REFRESH_DELAY_MS = 1500
# The hub applies an adaptive profile a few seconds after the command; the
# card then learns what it really did (t-15, doc/dirigera-api.md §5 item 7).
ADAPTIVE_REFRESH_DELAY_MS = 5000
# First-load placeholders: how many, and how tall (about one device card).
SKELETON_CARDS = 3
SKELETON_HEIGHT = theme.SP24 * 5
# Header: one 56 px row from this window width up, two 48 px rows below it
# (design-doc.md §4.2, §11). This is only a floor: the single row needs about
# 870 px with the offscreen fonts and more with larger fonts or scaling, so the
# switch point is derived from the row's contents (`_header_row_width`).
HEADER_BREAKPOINT = 900
HEADER_HEIGHT = 56
HEADER_HEIGHT_COMPACT = 96
QWIDGETSIZE_MAX = 16777215

# Saved credentials live next to this file, whatever the working directory.
CONFIG_PATH = Path(__file__).resolve().parent / "config.ini"

# The fan mode the hub reports for each fan motor state (req-15); used to
# update a purifier's `fan_mode` right after a successful speed change.
FAN_MODE_FOR_MOTOR_STATE = {
    0: FanModeEnum.OFF,
    1: FanModeEnum.AUTO,
    10: FanModeEnum.LOW,
    20: FanModeEnum.LOW,
    30: FanModeEnum.MEDIUM,
    40: FanModeEnum.MEDIUM,
    50: FanModeEnum.HIGH,
}


def is_hidden_device(device: Any) -> bool:
    """True when the hub flags the device hidden; the IKEA app hides it too (t-89)."""
    return getattr(device, "is_hidden", False) is True


# Scenes the IKEA app creates itself are hidden unless this is on (t-90).
AUTOMATIC_SCENES_LABEL = "Show automatic scenes"
AUTOMATIC_SCENES_KEY = "scenes/show_automatic"

# Room colour dots and card edges are shown only while this is on (req-22, t-86).
ROOM_COLOURS_LABEL = "Room colours"
ROOM_COLOURS_KEY = "rooms/colours"


def is_user_scene(scene: Any) -> bool:
    """True for scenes the user made: type `userScene`, or no type reported."""
    scene_type = getattr(scene, "type", None)
    if scene_type is None:
        return True
    return bool(getattr(scene_type, "value", scene_type) == "userScene")


def load_show_automatic() -> bool:
    """The remembered "Show automatic scenes" choice, off by default."""
    return bool(ui_settings().value(AUTOMATIC_SCENES_KEY, False, type=bool))


def load_room_colours() -> bool:
    """The remembered "Room colours" choice, off by default (req-22)."""
    return bool(ui_settings().value(ROOM_COLOURS_KEY, False, type=bool))


def widget_name(widget: QWidget) -> str:
    """Return the display name a card or scene tile is filtered by (t-50)."""
    return str(getattr(widget, "full_name", "") or "")


def _is_deleted(target: CommandTarget) -> bool:
    """True once Qt has destroyed the widget behind `target`."""
    return sip.isdeleted(cast(Any, target))


def _scroll_value(area: QScrollArea) -> int:
    """Return the vertical scroll position of `area` (0 without a bar)."""
    bar = area.verticalScrollBar()
    return bar.value() if bar is not None else 0


def scan_scope_text(networks: List[str]) -> str:
    """Progress text naming what a scan covers."""
    if not networks:
        return "No local networks to scan."
    count = len(hosts_to_scan(networks))
    return f"Scanning {count} addresses on {', '.join(networks)}…"


class HubSelectionDialog(QDialog):
    """Dialog for selecting a discovered hub or entering IP manually."""

    def __init__(
        self, hubs: List[Tuple[str, str]], parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.selected_ip: Optional[str] = None
        self.init_ui(hubs)

    def init_ui(self, hubs: List[Tuple[str, str]]) -> None:
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

    def accept_selection(self) -> None:
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


class DirigeraDashboard(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.hub: Optional[Hub] = None
        self.devices: List[Any] = []
        self.scenes: List[Scene] = []
        self.adaptive_profiles: List[Any] = []  # t-15; only the hub changes them
        self._show_automatic = load_show_automatic()
        self._room_colours = load_room_colours()
        self._hub_ip: Optional[str] = None
        self._last_refresh: Optional[datetime] = None
        self._connect_worker: Optional[ConnectWorker] = None
        self._refresh_worker: Optional[RefreshWorker] = None
        self._scene_workers: List[SceneTriggerWorker] = []
        self._command_workers: List[CommandWorker] = []
        # The live-event listener (t-16); stopped ones stay listed until their
        # thread has ended, so a close can wait for them.
        self._event_worker: Optional[EventWorker] = None
        self._event_workers: List[EventWorker] = []
        self._live = False
        # True after the socket dropped: the next open must refetch, because
        # events during the gap are lost.
        self._event_gap = False
        # Set while a close waits for running workers (see closeEvent).
        self._close_pending = False
        # (room section, its card grid), in display order, for search filtering.
        self._room_sections: List[Tuple[QWidget, CardGrid]] = []
        # Live widgets, so a refresh updates them in place (t-19): room id ->
        # (section, grid, label) and device id -> card.
        self._sections: Dict[str, Tuple[QWidget, CardGrid, RoomSectionHeader]] = {}
        self._device_cards: Dict[str, DeviceCard] = {}
        # Fingerprint of the last applied fetch; an equal fetch is a no-op.
        self._signature: Optional[Tuple[Any, ...]] = None
        # Placeholder cards shown until the first successful fetch.
        self.skeleton: Optional[CardGrid] = None
        self._summary_text = ""
        self._status_is_failure = False
        # True while the running fetch was started by the timer, not the user.
        self._poll_interval = POLL_INTERVAL_S
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(self._poll_interval * 1000)
        self.refresh_timer.timeout.connect(self._poll)
        # Single-shot: restarted by each successful scene activation.
        self._scene_refresh_timer = QTimer(self)
        self._scene_refresh_timer.setSingleShot(True)
        self._scene_refresh_timer.timeout.connect(self._request_background_refresh)
        self._adaptive_refresh_timer = QTimer(self)
        self._adaptive_refresh_timer.setSingleShot(True)
        self._adaptive_refresh_timer.timeout.connect(self._request_background_refresh)
        # Set when a scene refresh came due while a fetch was already running.
        self._refresh_pending = False
        # Single-shot: the first event of a burst starts it (t-16).
        self._event_timer = QTimer(self)
        self._event_timer.setSingleShot(True)
        self._event_timer.timeout.connect(self._request_background_refresh)
        self.init_ui()
        self.load_config()

    def load_config(self) -> None:
        """Load saved credentials from config.ini next to dashboard.py.

        A missing file is normal. An unreadable or malformed one is reported
        in the status caption and leaves the fields empty.
        """
        self.discovery_settings = DiscoverySettings()
        self.energy_settings = EnergySettings()
        self.energy_view.set_price(
            self.energy_settings.price_per_kwh, self.energy_settings.currency
        )
        if not CONFIG_PATH.exists():
            return
        config = configparser.ConfigParser()
        try:
            config.read(CONFIG_PATH, encoding="utf-8-sig")
        except (configparser.Error, OSError, UnicodeDecodeError) as error:
            self.set_status_text(f"Could not read config.ini: {error}", "danger")
            return
        ignored: List[str] = []
        if "discovery" in config:
            self.discovery_settings, problems = parse_discovery_settings(
                config["discovery"]
            )
            ignored += [f"[discovery] {p}" for p in problems]
        if "energy" in config:
            self.energy_settings, problems = parse_energy_settings(config["energy"])
            self.energy_view.set_price(
                self.energy_settings.price_per_kwh, self.energy_settings.currency
            )
            ignored += [f"[energy] {p}" for p in problems]
        if ignored:
            self.set_status_text(
                "Ignored invalid settings in config.ini ("
                + "; ".join(ignored)
                + "); using defaults",
                "danger",
            )
        if "hub" not in config:
            return
        hub = config["hub"]
        if "ip_address" in hub:
            self.connection_block.ip_input.setText(hub["ip_address"])
        token = hub.get("token", "")
        if token and token != "YOUR_TOKEN_HERE":
            self.connection_block.token_input.setText(token)

    def init_ui(self) -> None:
        self.setWindowTitle("Dirigera Dashboard")
        self.resize(1080, 700)
        self.setMinimumSize(640, 480)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar (design-doc.md §4.2)
        self.header = self.build_header()
        self._apply_header_layout(self._header_compact_needed())
        main_layout.addWidget(self.header)

        # Caption line for detailed status messages
        status_row = QWidget()
        status_row_layout = QHBoxLayout(status_row)
        status_row_layout.setContentsMargins(theme.SP20, theme.SP8, theme.SP20, 0)
        self.status_label = QLabel("")
        self.status_label.setProperty("role", "caption")
        status_row_layout.addWidget(self.status_label)
        status_row_layout.addStretch()
        # Last successful update and polling schedule (design-doc.md §10.2).
        self.update_label = QLabel("")
        self.update_label.setProperty("role", "caption")
        status_row_layout.addWidget(self.update_label)
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

        # Room colour toggle above the sections, outside the scroll area so it
        # stays in view (req-22). Its margins line up with the sections.
        self.room_colours_switch = ToggleSwitch(accessible_name=ROOM_COLOURS_LABEL)
        self.room_colours_switch.setChecked(self._room_colours)
        self.room_colours_switch.toggled.connect(self._on_room_colours_toggled)
        room_colours_label = QLabel(ROOM_COLOURS_LABEL)
        room_colours_label.setStyleSheet(label_style(theme.TEXT2, theme.FONT_LABEL))
        room_colours_row = QHBoxLayout()
        room_colours_row.setContentsMargins(theme.SP24, theme.SP20, theme.SP24, 0)
        room_colours_row.setSpacing(theme.SP12)
        room_colours_row.addWidget(room_colours_label)
        room_colours_row.addWidget(self.room_colours_switch)
        room_colours_row.addStretch()

        devices_tab_layout = QVBoxLayout(self.devices_tab)
        devices_tab_layout.setContentsMargins(0, 0, 0, 0)
        devices_tab_layout.addLayout(room_colours_row)
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
        self.scenes_grid = CardGrid(min_width=SCENE_MIN_WIDTH)
        # Automatic scenes stay hidden unless the remembered toggle is on (t-90).
        self.automatic_switch = ToggleSwitch(accessible_name=AUTOMATIC_SCENES_LABEL)
        self.automatic_switch.setChecked(self._show_automatic)
        self.automatic_switch.toggled.connect(self._on_automatic_toggled)
        automatic_label = QLabel(AUTOMATIC_SCENES_LABEL)
        automatic_label.setStyleSheet(label_style(theme.TEXT2, theme.FONT_LABEL))
        automatic_row = QHBoxLayout()
        automatic_row.setSpacing(theme.SP12)
        automatic_row.addWidget(automatic_label)
        automatic_row.addWidget(self.automatic_switch)
        automatic_row.addStretch()
        self.scenes_layout.addLayout(automatic_row)
        self.scenes_layout.addWidget(self.scenes_grid)
        self.scenes_layout.addStretch()
        self.scenes_scroll.setWidget(self.scenes_content)

        scenes_tab_layout = QVBoxLayout(self.scenes_tab)
        scenes_tab_layout.setContentsMargins(0, 0, 0, 0)
        scenes_tab_layout.addWidget(self.scenes_scroll)
        self.tab_widget.addTab(self.scenes_tab, "Scenes")

        # Energy tab (t-49)
        self.energy_view = EnergyView(on_reset=self.reset_energy)
        self.energy_view.set_room_colours(self._room_colours)
        self.tab_widget.addTab(self.energy_view, "Energy")

        # The segmented switcher is the only navigation; a visible tab bar
        # would duplicate it (design-doc.md §4.2).
        tab_bar = self.tab_widget.tabBar()
        if tab_bar is not None:
            tab_bar.hide()

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
        """Build the header bar (design-doc.md §4.2).

        Row 1 holds title, status chip, search and Refresh. The view switcher
        sits in row 1 too, except below `HEADER_BREAKPOINT`, where it moves to
        a second row (design-doc.md §11); see `_apply_header_layout`.
        """
        header = QWidget()
        header.setProperty("role", "header")
        header.setFixedHeight(HEADER_HEIGHT)

        outer = QVBoxLayout(header)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header_row1 = QWidget()
        self.header_row1_layout = QHBoxLayout(self.header_row1)
        self.header_row1_layout.setSpacing(theme.SP12)
        layout = self.header_row1_layout

        self.header_title = QLabel("Dirigera")
        self.header_title.setProperty("role", "appTitle")
        layout.addWidget(self.header_title)

        self.status_chip = StatusChip("Not connected", "neutral")
        layout.addWidget(self.status_chip)

        # Index 2 is the flexible gap; index 3 is the search field.
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

        self.header_row2 = QWidget()
        self.header_row2_layout = QHBoxLayout(self.header_row2)
        self.header_row2_layout.setContentsMargins(
            theme.SP20, theme.SP8, theme.SP20, theme.SP8
        )
        self.header_row2_layout.addStretch(1)
        self.header_row2.hide()

        outer.addWidget(self.header_row1)
        outer.addWidget(self.header_row2)

        self._header_compact: Optional[bool] = None
        return header

    def _apply_header_layout(self, compact: bool) -> None:
        """Move the view switcher between the header rows.

        Normal: one 56 px row with the switcher before Refresh. Compact: a
        second 48 px row holds the switcher, left-aligned, and the search
        field takes the free width of row 1. The one switcher instance is
        re-parented, never copied.
        """
        if compact == self._header_compact:
            return
        self._header_compact = compact
        row1 = self.header_row1_layout
        row2 = self.header_row2_layout
        switcher = self.view_switcher
        if compact:
            row1.removeWidget(switcher)
            row2.insertWidget(0, switcher)
            self.search_input.setMaximumWidth(QWIDGETSIZE_MAX)
            row1.setStretch(2, 0)
            row1.setStretch(3, 1)
            margin = theme.SP8
        else:
            row2.removeWidget(switcher)
            row1.insertWidget(row1.indexOf(self.refresh_button), switcher)
            self.search_input.setMaximumWidth(260)
            row1.setStretch(2, 1)
            row1.setStretch(3, 0)
            margin = theme.SP12
        row1.setContentsMargins(theme.SP20, margin, theme.SP20, margin)
        self.header_row2.setVisible(compact)
        self.header.setFixedHeight(HEADER_HEIGHT_COMPACT if compact else HEADER_HEIGHT)

    def _header_row_width(self) -> int:
        """Width the one-row header needs with the current fonts.

        Summed from the size hints of its parts (search field at its minimum)
        plus spacing and margins, so it holds whichever row the switcher
        currently sits in.
        """
        widgets = (
            self.header_title,
            self.status_chip,
            self.view_switcher,
            self.refresh_button,
        )
        width = sum(w.minimumSizeHint().width() for w in widgets)
        width += self.search_input.minimumWidth()
        # Five gaps: title, chip, flexible space, search, switcher, Refresh.
        width += 5 * self.header_row1_layout.spacing() + 2 * theme.SP20
        return width

    def _header_compact_needed(self) -> bool:
        """True when the window is too narrow for the single-row header."""
        return self.width() < max(HEADER_BREAKPOINT, self._header_row_width())

    @override
    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Switch the header layout when the width crosses the breakpoint."""
        super().resizeEvent(event)
        self._apply_header_layout(self._header_compact_needed())

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
        self._set_caption(self.status_label, text, tone)

    @staticmethod
    def _set_caption(label: QLabel, text: str, tone: Optional[str]) -> None:
        label.setText(text)
        label.setProperty("tone", tone or "")
        style = label.style()
        if style is not None:
            style.unpolish(label)
            style.polish(label)

    def _update_caption(self) -> None:
        """Show the last successful update and the polling schedule.

        The caption turns to warn tone when the last success is older than two
        intervals, so silently stale data is marked without a dialog.
        """
        if self._last_refresh is None or self.hub is None:
            self._set_caption(self.update_label, "", None)
            return
        age = (datetime.now() - self._last_refresh).total_seconds()
        stale = age > 2 * self._poll_interval
        updated = f"{self._last_refresh:%H:%M}"
        text = (
            f"Live · updated {updated}"
            if self._live
            else f"Updated {updated} · every {self._poll_interval} s"
        )
        self._set_caption(self.update_label, text, "warn" if stale else None)

    def discover_hubs(self) -> None:
        """Start the hub discovery process in a background thread."""
        thread = getattr(self, "discovery_thread", None)
        if thread is not None and thread.isRunning():
            return
        self.connection_block.discover_button.setEnabled(False)
        self.connection_block.set_message("")

        settings = self.discovery_settings
        networks = (
            settings.networks if settings.networks is not None else get_local_networks()
        )
        # Resolved here so the scan and the text naming it share one scope.
        scan_settings = DiscoverySettings(
            networks, settings.max_workers, settings.timeout
        )

        # Create and configure the progress dialog
        self.progress_dialog = QProgressDialog(
            scan_scope_text(networks), "Cancel", 0, 0, self
        )
        self.progress_dialog.setWindowTitle("Discovering Hubs")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)

        # Create and start the discovery thread
        self.discovery_thread = DiscoveryThread(scan_settings)
        self.discovery_thread.discovery_done.connect(self.on_discovery_finished)
        self.discovery_thread.discovery_failed.connect(self.on_discovery_failed)

        # Handle dialog cancellation
        self.progress_dialog.canceled.connect(self.on_discovery_canceled)

        # Show the dialog and start the thread
        self.progress_dialog.show()
        self.discovery_thread.start()

    def on_discovery_canceled(self) -> None:
        """Handle cancellation of the discovery process."""
        thread = getattr(self, "discovery_thread", None)
        if thread is not None and thread.isRunning():
            thread.request_stop()
        self.set_status_text("Discovery canceled")

    def _end_discovery_ui(self) -> None:
        """Close the progress dialog and re-enable the Discover button."""
        # QProgressDialog.close() emits canceled, which would terminate the
        # thread that just finished and report a cancel, so disconnect the
        # cancel handler first.
        if hasattr(self, "progress_dialog"):
            self.progress_dialog.canceled.disconnect(self.on_discovery_canceled)
            self.progress_dialog.close()
        self.connection_block.discover_button.setEnabled(True)

    def on_discovery_failed(self, message: str) -> None:
        """Report a scan that raised, so it never reads as "no hubs found"."""
        self._end_discovery_ui()
        if self.discovery_thread.stop_requested():
            return  # canceled (or closing): nobody is waiting for the result
        self.connection_block.set_message(f"Discovery failed: {message}", "danger")
        self.set_status_text("Discovery failed", "danger")

    def on_discovery_finished(self, discovered_hubs: List[Tuple[str, str]]) -> None:
        """Handle completion of the discovery process."""
        self._end_discovery_ui()

        if self.discovery_thread.stop_requested():
            return  # canceled (or closing): drop the partial result

        if not discovered_hubs:
            self.connection_block.set_message(
                "No hubs found on the local network. "
                "If you know the hub's IP address, enter it manually.",
                "warn",
            )
            self.set_status_text("No hubs discovered")
            return

        if len(discovered_hubs) == 1:
            # Single hub found - use it directly
            ip, mac = discovered_hubs[0]
            self.connection_block.ip_input.setText(ip)
            mac_info = f" ({mac})" if mac else ""
            self.set_status_text(f"Discovered hub at {ip}{mac_info}")
            self.connection_block.set_message(
                f"Found a hub at {ip}; enter your token and connect.", "ok"
            )
        else:
            # Multiple hubs found - let user choose
            dialog = HubSelectionDialog(discovered_hubs, self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_ip:
                self.connection_block.ip_input.setText(dialog.selected_ip)

    def connect_to_hub(self) -> None:
        """Verify the entered credentials in a background thread (t-17)."""
        if self._connect_worker is not None:
            return  # a probe is already in flight

        ip_address, token = self.connection_block.credentials()

        if not ip_address or not token:
            self.connection_block.set_message(
                "Enter both the IP address and the token.", "danger"
            )
            return
        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            self.connection_block.set_message("Enter a valid IP address", "danger")
            return
        self.connection_block.set_message("")

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
        self._stop_events()  # a listener of an earlier hub must not outlive it
        self.hub = hub
        self._hub_ip = ip_address
        self.status_chip.set_status(f"Hub online · {ip_address}", "ok")
        self.set_status_text(f"Connected to hub at {ip_address}", "ok")
        self.refresh_button.setEnabled(True)
        self.show_views()
        self._show_skeleton()
        self.refresh_devices()
        self.refresh_timer.start()
        self._start_events()

    def _show_skeleton(self) -> None:
        """Show placeholder cards until the first fetch arrives (§8.13).

        Plain sunken frames, no animation. Skipped when cards from an earlier
        connection are still on screen.
        """
        if self.skeleton is not None or self._device_cards:
            return
        grid = CardGrid()
        cards: List[QWidget] = []
        for _ in range(SKELETON_CARDS):
            card = QFrame()
            card.setMinimumHeight(SKELETON_HEIGHT)
            card.setStyleSheet(
                f"QFrame {{ background-color: {theme.SUNKEN};"
                f" border-radius: {theme.RADIUS_CARD}px; }}"
            )
            cards.append(card)
        grid.set_cards(cards)
        self.skeleton = grid
        self.devices_layout.insertWidget(0, grid)

    def _remove_skeleton(self) -> None:
        """Drop the placeholder cards, if any."""
        grid = self.skeleton
        if grid is None:
            return
        self.skeleton = None
        self.devices_layout.removeWidget(grid)
        grid.hide()
        grid.deleteLater()

    def _on_connect_failed(self, message: str) -> None:
        """Report a failed attempt and hand the form back to the user."""
        # A half-built hub must not look connected.
        self.hub = None
        self.refresh_timer.stop()
        self._stop_events()
        self.show_connection_block()
        self.status_chip.set_status("Hub unreachable", "warn")
        self.set_status_text(f"Connection failed: {message}", "danger")
        self.connection_block.set_message(
            f"Couldn't connect to the hub: {message}", "danger"
        )

    def _on_connect_worker_done(self) -> None:
        self._connect_worker = None

    def refresh_devices(self) -> None:
        """Start a refresh the user asked for (t-17); connect uses it too."""
        self._start_refresh(with_profiles=True)

    def _poll(self) -> None:
        """Timer tick: refresh unless that would be wasteful or stack up.

        Skipped without a hub, while a connect or fetch is in flight, and
        while the window is minimised (t-56).
        """
        self._update_caption()
        if (
            self.hub is None
            or self._connect_worker is not None
            or self._refresh_worker is not None
            or self.isMinimized()
        ):
            return
        self._start_refresh(with_profiles=True)

    def _start_refresh(self, with_profiles: bool = False) -> None:
        """Start the fetch worker. Failures are reported inline, never in a dialog.

        Adaptive profiles change only in the IKEA app, so only connect, manual
        and timer refreshes fetch them, not the event-driven ones (t-15).
        """
        hub = self.hub
        if hub is None:
            return
        if self._refresh_worker is not None:
            return  # one fetch at a time

        # Disable Refresh while loading so clicks cannot stack up fetches.
        self.refresh_button.setText("Refreshing…")
        self.refresh_button.setEnabled(False)

        worker = RefreshWorker(hub, self, with_profiles=with_profiles)
        worker.refreshed.connect(self._on_refreshed)
        worker.failed.connect(self._on_refresh_failed)
        worker.finished.connect(self._on_refresh_worker_done)
        self._refresh_worker = worker
        worker.start()

    def _start_events(self) -> None:
        """Listen for hub events; they only prompt a refresh (t-16)."""
        hub = self.hub
        if hub is None:
            return
        self._event_workers = [w for w in self._event_workers if w.isRunning()]
        worker = EventWorker(hub, self)
        worker.opened.connect(self._on_events_opened)
        worker.received.connect(self._on_hub_event)
        worker.lost.connect(self._on_events_lost)
        self._event_worker = worker
        self._event_workers.append(worker)
        worker.start()

    def _stop_events(self) -> None:
        """Stop the listener and fall back to plain polling."""
        worker = self._event_worker
        self._event_worker = None
        self._event_timer.stop()
        self._event_gap = False
        self._set_live(False)
        if worker is not None:
            worker.request_stop()

    def _from_current_listener(self) -> bool:
        """False for a signal that a stopped listener queued before it ended."""
        sender = self.sender()
        return sender is None or sender is self._event_worker

    def _set_live(self, live: bool) -> None:
        """Switch between live updates and polling, and retime the poll."""
        if live == self._live:
            return
        self._live = live
        self._poll_interval = LIVE_POLL_INTERVAL_S if live else POLL_INTERVAL_S
        self.refresh_timer.setInterval(self._poll_interval * 1000)
        self._update_caption()

    def _on_events_opened(self) -> None:
        if not self._from_current_listener():
            return
        self._set_live(True)
        if self._event_gap:
            self._event_gap = False
            self._request_background_refresh()  # catch up on what was missed

    def _on_events_lost(self) -> None:
        if not self._from_current_listener():
            return
        self._event_gap = True
        self._set_live(False)

    def _on_hub_event(self, _event: object) -> None:
        """Any hub event means something changed: refresh once per window."""
        if not self._from_current_listener():
            return
        if self.hub is None or self.isMinimized() or self._event_timer.isActive():
            return  # restoring a minimised window polls at once
        self._event_timer.start(EVENT_COALESCE_MS)

    def _request_background_refresh(self) -> None:
        """Refresh in the background now, or once the running fetch ends."""
        if self.hub is None:
            return
        if self._refresh_worker is not None:
            self._refresh_pending = True
            return
        self._start_refresh()

    @override
    def changeEvent(self, event: Optional[QEvent]) -> None:
        """Pause polling while minimised; catch up when restored (t-56)."""
        super().changeEvent(event)
        if (
            event is not None
            and event.type() == QEvent.Type.WindowStateChange
            and self.hub is not None
        ):
            if self.isMinimized():
                self.refresh_timer.stop()
            elif not self.refresh_timer.isActive():
                self.refresh_timer.start()
                self._poll()

    @staticmethod
    def _data_signature(
        devices: List[Any], scenes: List[Scene], profiles: Iterable[Any] = ()
    ) -> Tuple[Any, ...]:
        """Return a cheap fingerprint of a fetch, to skip no-op refreshes.

        A light's adaptive profile state is not on `attributes`, so it is
        part of the fingerprint on its own (t-15).
        """
        device_part = sorted(
            (
                str(getattr(d, "id", "")),
                bool(getattr(d, "is_reachable", True)),
                repr(getattr(d, "room", None)),
                repr(getattr(d, "attributes", None)),
                repr(getattr(d, "adaptive_profile", None)),
            )
            for d in devices
        )
        scene_part = [
            (
                str(getattr(s, "id", "")),
                str(getattr(getattr(s, "info", None), "name", "")),
            )
            for s in scenes
        ]
        return (tuple(device_part), tuple(scene_part), tuple(profile_options(profiles)))

    def _on_refreshed(
        self,
        devices: List[Any],
        scenes: List[Scene],
        profiles: Optional[List[Any]] = None,
    ) -> None:
        """Bring the views up to date with a successful fetch (t-19).

        Existing cards are updated in place, so scroll position, order, focus
        and a slider being dragged survive; only new ids add cards and only
        vanished ids remove them. Devices the hub marks hidden are left out
        everywhere: cards, energy view and the status counts (t-89). `profiles`
        is `None` when this fetch did not ask for them or failed: the earlier
        list stays (t-15).
        """
        if profiles is not None:
            self.adaptive_profiles = profiles
        devices = [device for device in devices if not is_hidden_device(device)]
        self._remove_skeleton()
        self._last_refresh = datetime.now()
        self._update_caption()
        self.stale_label.hide()
        if self._hub_ip:
            self.status_chip.set_status(f"Hub online · {self._hub_ip}", "ok")

        signature = self._data_signature(devices, scenes, self.adaptive_profiles)
        if signature == self._signature:
            # Nothing changed: leave the widget tree and caption alone, except
            # for undoing an earlier failure message.
            if self._status_is_failure:
                self._status_is_failure = False
                self.set_status_text(self._summary_text)
            return
        self._signature = signature

        self.devices = devices
        self.scenes = scenes

        focus = QApplication.focusWidget()
        areas = (self.devices_scroll, self.scenes_scroll)
        scroll_values = [_scroll_value(area) for area in areas]

        self._update_rooms(devices)
        self._update_scenes(self._visible_scenes(scenes))

        # Energy view: outlets and electrical sensors grouped by room (§9.4).
        energy_by_room = group_by_room(
            [device for device in self.devices if is_energy_device(device)]
        )
        self.energy_view.update_rooms(
            [
                (format_room_label(room), sorted(devs, key=device_sort_key))
                for room, devs in energy_by_room
            ]
        )

        self._summary_text = self._summary()
        self._status_is_failure = False
        self.set_status_text(self._summary_text)

        # New cards start visible, so put the active filter back (t-50).
        self.filter_devices(self.search_input.text())

        # Restore the view state when the widgets survived.
        for area, value in zip(areas, scroll_values):
            bar = area.verticalScrollBar()
            if bar is not None and bar.value() != value:
                bar.setValue(value)
        if (
            focus is not None
            and not sip.isdeleted(focus)
            and QApplication.focusWidget() is not focus
        ):
            focus.setFocus()

    def _update_rooms(self, devices: List[Any]) -> List[Tuple[str, List[Any]]]:
        """Reconcile room sections and device cards with `devices`."""
        groups = group_by_room(devices)
        old_cards = self._device_cards
        new_cards: Dict[str, DeviceCard] = {}
        wanted: List[Tuple[str, str, List[QWidget]]] = []
        section_colours: Dict[str, Optional[str]] = {}
        profiles = profile_options(self.adaptive_profiles)

        for room_name, room_devices in groups:
            room_key = get_room(room_devices[0])[0]
            section_colours[room_key] = theme.room_colour(
                room_colour_name(room_devices[0])
            )
            cards: List[QWidget] = []
            for device in sorted(room_devices, key=device_sort_key):
                device_id = str(getattr(device, "id", ""))
                card = old_cards.get(device_id)
                if card is None:
                    card = self.create_device_widget(device)
                else:
                    card.update_from_device(device)
                    card.set_profiles(profiles)
                card.set_room_colour(theme.room_colour(room_colour_name(device)))
                card.set_marker_shown(self._room_colours)
                new_cards[device_id] = card
                cards.append(card)
            wanted.append((room_key, room_name, cards))

        # Sections for rooms that are gone.
        wanted_keys = {key for key, _, _ in wanted}
        for key in [k for k in self._sections if k not in wanted_keys]:
            section, _grid, _label = self._sections.pop(key)
            self.devices_layout.removeWidget(section)
            section.hide()
            section.deleteLater()
        # Cards for devices that are gone (their section may live on).
        for device_id, card in old_cards.items():
            if device_id not in new_cards:
                card.hide()
                card.deleteLater()
        self._device_cards = new_cards

        for key, room_name, cards in wanted:
            if key not in self._sections:
                self._sections[key] = self._new_room_section(room_name)
            _section, grid, header = self._sections[key]
            header.set_text(format_room_label(room_name))
            header.set_room_colour(section_colours[key])
            header.set_marker_shown(self._room_colours)
            if grid.cards() != cards:
                grid.set_cards(cards)

        # Section order: rebuild the layout order only when it differs.
        ordered = [self._sections[key][0] for key, _, _ in wanted]
        current = []
        for index in range(self.devices_layout.count() - 1):
            item = self.devices_layout.itemAt(index)
            current.append(item.widget() if item is not None else None)
        if current != ordered:
            for section in ordered:
                self.devices_layout.removeWidget(section)
            for index, section in enumerate(ordered):
                self.devices_layout.insertWidget(index, section)
                section.show()
        self._room_sections = [
            (self._sections[key][0], self._sections[key][1]) for key, _, _ in wanted
        ]
        return groups

    def _update_scenes(self, scenes: List[Scene]) -> None:
        """Reconcile scene tiles with `scenes`, keeping the hub's order."""
        old_tiles = {
            str(getattr(t.scene, "id", "")): t
            for t in self.scenes_grid.cards()
            if isinstance(t, SceneTile)
        }
        tiles: List[QWidget] = []
        for scene in scenes:
            tile = old_tiles.pop(str(getattr(scene, "id", "")), None)
            if tile is None:
                tile = self.create_scene_tile(scene)
            else:
                tile.update_from_scene(scene)
            tiles.append(tile)
        for tile in old_tiles.values():
            tile.hide()
            tile.deleteLater()
        if self.scenes_grid.cards() != tiles:
            self.scenes_grid.set_cards(tiles)

    def _visible_scenes(self, scenes: List[Scene]) -> List[Scene]:
        """The scenes the grid shows: automatic ones only while the toggle is on."""
        if self._show_automatic:
            return list(scenes)
        return [scene for scene in scenes if is_user_scene(scene)]

    def _summary(self) -> str:
        """The status line counts: devices, rooms and the scenes on screen."""
        scenes = len(self._visible_scenes(self.scenes))
        return (
            f"Found {len(self.devices)} devices in {len(self._room_sections)} rooms "
            f"and {scenes} scenes"
        )

    def _on_automatic_toggled(self, shown: bool) -> None:
        """Show or hide automatic scenes and remember the choice (t-90).

        Only the scene grid, the search filter and the counts change; no hub
        command is sent.
        """
        self._show_automatic = shown
        settings = ui_settings()
        settings.setValue(AUTOMATIC_SCENES_KEY, shown)
        settings.sync()
        self._update_scenes(self._visible_scenes(self.scenes))
        self.filter_devices(self.search_input.text())
        self._summary_text = self._summary()
        if not self._status_is_failure:
            self.set_status_text(self._summary_text)

    def _on_room_colours_toggled(self, shown: bool) -> None:
        """Show or hide the room colours and remember the choice (req-22).

        Restyles the existing cards and section labels in place. No hub
        command is sent.
        """
        self._room_colours = shown
        settings = ui_settings()
        settings.setValue(ROOM_COLOURS_KEY, shown)
        settings.sync()
        for card in self._device_cards.values():
            card.set_marker_shown(shown)
        for _section, _grid, header in self._sections.values():
            header.set_marker_shown(shown)
        self.energy_view.set_room_colours(shown)

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
        self._status_is_failure = True
        if self._last_refresh is not None:
            self.stale_label.setText(f"Showing data from {self._last_refresh:%H:%M}")
            self.stale_label.show()
        self._update_caption()

    def _on_refresh_worker_done(self) -> None:
        self._refresh_worker = None
        self.refresh_button.setText("Refresh")
        self.refresh_button.setEnabled(self.hub is not None)
        if self._refresh_pending:
            self._refresh_pending = False
            self._start_refresh()

    def _new_room_section(
        self, room_name: str
    ) -> Tuple[QWidget, CardGrid, RoomSectionHeader]:
        """Build one empty room section: section label plus reflowing grid.

        Cards are placed by `_update_rooms`, already sorted for a stable order
        (design-doc.md §8.1 rule 3).
        """
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SP12)  # label-to-grid gap (design-doc.md §4.3)

        header = RoomSectionHeader(format_room_label(room_name))
        layout.addWidget(header)

        grid = CardGrid()
        layout.addWidget(grid)
        self.devices_layout.insertWidget(self.devices_layout.count() - 1, section)
        return section, grid, header

    def create_device_widget(self, device: Any) -> DeviceCard:
        """Create a DeviceCard instance with connected action handlers."""
        return DeviceCard(
            device=device,
            on_toggle=self.toggle_device_power,
            on_brightness=self.set_light_brightness,
            on_blind_position=self.set_blind_position,
            on_temperature=self.set_light_temperature,
            on_blind_state=self.set_blind_state,
            on_colour=self.set_light_colour,
            on_fan_speed=self.set_fan_speed,
            on_profile=self.set_adaptive_profile,
            profiles=profile_options(self.adaptive_profiles),
        )

    def create_scene_tile(self, scene: Scene) -> SceneTile:
        """Create a scene tile wired to the activation handler (§8.10)."""
        return SceneTile(scene, on_activate=self.trigger_scene)

    def run_device_command(
        self, card: CommandTarget, command: Callable[[], None], action: str
    ) -> CommandWorker:
        """Run a device command in a worker and resync the card afterwards.

        Hub calls block for up to the library's 10 s timeout, so they never
        run on the GUI thread (req-4). The card shows "Sending…" meanwhile.
        Returns the worker, so a caller can attach its own success handler.
        """
        self._command_workers = [w for w in self._command_workers if w.isRunning()]
        card.set_pending(True)
        worker = CommandWorker(card, command, action, self)
        worker.succeeded.connect(self._on_command_done)
        worker.failed.connect(self._on_command_failed)
        self._command_workers.append(worker)
        worker.start()
        return worker

    def reset_energy(self, card: EnergyCard) -> None:
        """Reset a metering plug's usage counter on the hub (req-18).

        The hub copies its running total into the reset value and sets the
        reset time to now. Success triggers a refresh to fetch those values.
        """
        device = card.device

        def command() -> None:
            device.dirigera_client.patch(
                route=f"/devices/{device.id}",
                data=[{"attributes": {"energyConsumedAtLastReset": 0}}],
            )

        worker = self.run_device_command(card, command, "reset energy")
        worker.succeeded.connect(self._on_energy_reset_done)

    def _on_energy_reset_done(self, _card: object) -> None:
        """Fetch the values the hub stored for the reset."""
        self._request_background_refresh()

    def _on_command_done(self, card: CommandTarget) -> None:
        """Redraw the card from the value the library stored on success."""
        if not _is_deleted(card):
            card.sync_from_device()

    def _on_command_failed(
        self, card: CommandTarget, action: str, message: str
    ) -> None:
        """Report the failure and show the device's real state (req-3)."""
        if not _is_deleted(card):
            card.sync_from_device()
            card.show_error(f"Couldn't {action}: {message}")

    def toggle_device_power(self, card: DeviceCard, turn_on: bool) -> None:
        """Switch a light or outlet on or off."""
        device = card.device
        dtype = getattr(device, "device_type", "unknown")
        if dtype == "light":
            self.run_device_command(
                card, lambda: device.set_light(lamp_on=turn_on), f"toggle {dtype}"
            )
        elif dtype == "outlet":
            self.run_device_command(
                card, lambda: device.set_on(turn_on), f"toggle {dtype}"
            )

    def set_light_brightness(self, card: DeviceCard, brightness: int) -> None:
        """Set a light's brightness, switching an off light on first.

        The hub ignores a level sent to an off light, and a level sent before
        the on command, so the order is on, then level (t-94; seen on a real
        hub, `doc/dirigera-api.md` §5 item 6).
        """
        device = card.device

        def command() -> None:
            if not getattr(device.attributes, "is_on", True):
                device.set_light(lamp_on=True)
            device.set_light_level(brightness)

        self._run_light_command(card, command, "set brightness")

    def set_light_temperature(self, card: DeviceCard, kelvin: int) -> None:
        """Set a light's colour temperature in Kelvin."""
        device = card.device
        self._run_light_command(
            card, lambda: device.set_color_temperature(kelvin), "set colour temperature"
        )

    def set_light_colour(self, card: DeviceCard, hue: float, saturation: float) -> None:
        """Set a light's hue (0 to 360) and saturation (0.0 to 1.0)."""
        device = card.device
        self._run_light_command(
            card, lambda: device.set_light_color(hue, saturation), "set colour"
        )

    def set_adaptive_profile(self, card: DeviceCard, profile_id: Optional[str]) -> None:
        """Let a light follow an adaptive profile (t-15).

        "Off" (`None`) sends nothing: the library has no call to leave
        adaptive mode (doc/dirigera-api.md §5 item 7). The card shows the
        state the library stored, then the hub's own after a delay.
        """
        if profile_id is None:
            return
        device = card.device
        worker = self.run_device_command(
            card,
            lambda: device.activate_adaptive_profile(profile_id),
            "set adaptive profile",
        )
        worker.succeeded.connect(self._schedule_adaptive_refresh)

    def _run_light_command(
        self, card: DeviceCard, command: Callable[[], None], action: str
    ) -> CommandWorker:
        """Run a manual light change; on a light that follows a profile, refresh.

        The hub decides whether the change ended the profile, so the card
        asks it after a delay instead of guessing. Whether the light follows
        a profile is read before the command starts.
        """
        following = active_profile_id(card.device) is not None
        worker = self.run_device_command(card, command, action)
        if following:
            worker.succeeded.connect(self._schedule_adaptive_refresh)
        return worker

    def _schedule_adaptive_refresh(self, _card: object = None) -> None:
        """(Re)start the delayed refresh that shows what the hub applied."""
        self._adaptive_refresh_timer.start(ADAPTIVE_REFRESH_DELAY_MS)

    def set_fan_speed(self, card: DeviceCard, motor_state: int) -> None:
        """Set an air purifier's fan: 0 off, 1 auto, 10 to 50 speeds 1 to 5.

        On success the fan mode the hub would report is stored on the device,
        so the resync shows the new setting before the next refresh.
        """
        device = card.device

        def command() -> None:
            device.set_motor_state(motor_state)
            device.attributes.fan_mode = FAN_MODE_FOR_MOTOR_STATE[motor_state]

        self.run_device_command(card, command, "set fan speed")

    def set_blind_position(self, card: DeviceCard, position: int) -> None:
        """Move a blind to a target level."""
        device = card.device
        self.run_device_command(
            card, lambda: device.set_target_level(position), "set blind position"
        )

    def set_blind_state(self, card: DeviceCard, action: str) -> None:
        """Trigger blind movement state (Up, Down, Stop)."""
        action_map = {
            "Up": BlindsStateEnum.UP,
            "Down": BlindsStateEnum.DOWN,
            "Stop": BlindsStateEnum.STOPPED,
        }
        state = action_map.get(action)
        if state is None:
            return
        device = card.device
        self.run_device_command(
            card, lambda: device.set_state(state), "set blind state"
        )

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
        # Restarting coalesces quick activations into one fetch.
        self._scene_refresh_timer.start(SCENE_REFRESH_DELAY_MS)

    def _on_scene_failed(self, scene: Scene, message: str) -> None:
        """Report a failed activation inline instead of with a dialog."""
        tile = self._scene_tile_for(scene)
        if tile is not None:
            tile.show_error(message)

    def _scene_tile_for(self, scene: Scene) -> Optional[SceneTile]:
        """Return the tile displaying `scene`, if it is still on screen.

        Matches by scene id, not identity: a refresh during activation rebuilds
        the tiles from new Scene objects, and the result belongs on the new
        tile.
        """
        scene_id = getattr(scene, "id", None)
        for card in self.scenes_grid.cards():
            if isinstance(card, SceneTile) and (
                card.scene is scene or getattr(card.scene, "id", None) == scene_id
            ):
                return card
        return None

    def _running_workers(self) -> List[QThread]:
        """Return every worker thread that is still running."""
        workers: List[Optional[QThread]] = [
            self._connect_worker,
            self._refresh_worker,
            getattr(self, "discovery_thread", None),
            *self._event_workers,
            *self._scene_workers,
            *self._command_workers,
        ]
        return [w for w in workers if w is not None and w.isRunning()]

    @override
    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        """Close without destroying a worker thread that is still running.

        Hub calls cannot be interrupted and may last the library's 10 s
        timeout, and destroying a running QThread aborts the process. So
        while any worker runs, the window only hides; the close completes,
        and the application quits, once the last worker has finished.
        """
        self.refresh_timer.stop()
        self._scene_refresh_timer.stop()
        self._adaptive_refresh_timer.stop()
        self._stop_events()
        discovery = getattr(self, "discovery_thread", None)
        if discovery is not None and discovery.isRunning():
            discovery.request_stop()
        running = self._running_workers()
        if not running:
            super().closeEvent(event)
            return
        if event is not None:
            event.ignore()
        self.hide()
        if not self._close_pending:
            self._close_pending = True
            for worker in running:
                worker.finished.connect(self._finish_pending_close)

    def _finish_pending_close(self) -> None:
        """Complete a deferred close once no worker is running any more."""
        sender = self.sender()
        if isinstance(sender, QThread):
            sender.wait()  # finished is emitted just before run() returns
        if self._running_workers():
            return
        self.close()
        # A hidden window closing does not trigger quit-on-last-window.
        QApplication.quit()
