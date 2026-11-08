"""
Copyright (C) 2026 Sergei Vostrikov

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0


Main-window composition for the desktop application.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from . import APP_NAME, APP_VERSION
from .acquisition import AcquisitionTab
from .configuration import ConfigEditor
from .connection import ConnectionBar
from .controller import SessionController, default_links
from .data_viewer import NpzViewerTab
from .debug_log import BatchedFileHandler
from .device_config import DeviceConfigTab
from .firmware import FirmwareTab
from .service import ServiceTab
from .style import (
    DARK_STYLESHEET,
    LIGHT_STYLESHEET,
    TX_RX_STYLESHEET,
    _compact_controls,
    _expanding_field,
    _style_plot,
)

logger = logging.getLogger(__name__)

PROJECT_URL = "https://github.com/Sergio5714/wulpus-pro-max"
DOCUMENTATION_URL = "https://sergio5714.github.io/wulpus-pro-max/"


class MainWindow(QtWidgets.QMainWindow):
    """Composition root: wire panel signals and apply shared application policy."""

    def __init__(self, include_simulator=False, *, session=None):
        """Construct the main window and wire all shared panel dependencies."""
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1350, 900)
        self.settings = QtCore.QSettings()
        self.debug_handler = None
        self.previous_log_level = None
        self.pool = QtCore.QThreadPool.globalInstance()
        self.session = (
            session
            if session is not None
            else SessionController(default_links(include_simulator))
        )
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        self.connection = ConnectionBar(self.session, self.pool)
        layout.addWidget(self.connection)
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.configuration = ConfigEditor()
        self.acquisition = AcquisitionTab(self.session, self.configuration)
        self.viewer = NpzViewerTab()
        self.device_config = DeviceConfigTab(self.session, self.pool)
        self.service = ServiceTab(self.session, self.pool)
        self.firmware = FirmwareTab(self.session, self.pool)
        self.tabs.addTab(self.configuration, "Ultrasound Configuration")
        self.tabs.addTab(self.acquisition, "Acquisition")
        self.tabs.addTab(self.viewer, "Data Viewer")
        self.tabs.addTab(self.device_config, "WiFi Host Configuration")
        self.tabs.addTab(self.service, "Service")
        self.tabs.addTab(self.firmware, "Firmware Update")
        self.setCentralWidget(central)
        self.connection.state_changed.connect(self.update_capabilities)
        self.acquisition.running_changed.connect(self.operation_changed)
        self._firmware_info_link = None
        self.update_capabilities()
        self.acquisition.session_changed.connect(self.connection.reflect_session)
        self.firmware.session_changed.connect(self.connection.reflect_session)
        _compact_controls(self)
        self.connection.transport.setMaximumWidth(170)
        self.connection.device.setMinimumWidth(240)
        self.connection.device.setMaximumWidth(360)
        for path_field in (
            self.acquisition.output,
            self.viewer.path,
            self.firmware.esp_path,
            self.firmware.msp_path,
        ):
            _expanding_field(path_field)
        self._create_theme_menu()
        self._create_debug_menu()
        self._create_help_menu()
        self.set_theme(self.settings.value("appearance/theme", "light", type=str))

    def _create_theme_menu(self):
        """Create the persistent light and dark appearance actions."""
        theme_menu = self.menuBar().addMenu("Appearance").addMenu("Theme")
        self.theme_actions = {}
        group = QtGui.QActionGroup(self)
        group.setExclusive(True)
        for key, label in (
            ("system", "System default"),
            ("light", "Light"),
            ("dark", "Dark"),
        ):
            action = theme_menu.addAction(label)
            action.setCheckable(True)
            action.setData(key)
            group.addAction(action)
            action.triggered.connect(
                lambda checked=False, name=key: self.set_theme(name)
            )
            self.theme_actions[key] = action

    def set_theme(self, theme):
        """Apply a named Qt/plot theme and persist the selected preference."""
        if theme not in self.theme_actions:
            theme = "dark"
        self.setStyleSheet(
            {
                "system": TX_RX_STYLESHEET,
                "light": LIGHT_STYLESHEET,
                "dark": DARK_STYLESHEET,
            }[theme]
        )
        _style_plot(self.acquisition.plot, theme)
        _style_plot(self.viewer.plot, theme)
        self.theme_actions[theme].setChecked(True)
        self.settings.setValue("appearance/theme", theme)

    def _create_debug_menu(self):
        """Create debug-log controls and their persistent action state."""
        debug_menu = self.menuBar().addMenu("Debug")
        self.debug_action = debug_menu.addAction("Enable debug logging…")
        self.debug_action.setCheckable(True)
        self.debug_action.toggled.connect(self.toggle_debug_logging)

    def _create_help_menu(self):
        """Create application-information and third-party notice actions."""
        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction("About", self.show_about)
        help_menu.addAction("Third-party notices", self.show_third_party_notices)

    def show_about(self):
        """Show the application name, version, and project license."""
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("About WULPUS Pro Max")
        box.setIcon(QtWidgets.QMessageBox.Information)
        box.setTextFormat(QtCore.Qt.RichText)
        box.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        box.setText(
            f"<p><b>{APP_NAME} {APP_VERSION}</b></p>"
            "<p>Copyright &copy; 2026 Sergei Vostrikov and contributors.</p>"
            "<p>Includes software Copyright &copy; 2023 ETH Zurich.</p>"
            "<p>Project-authored source code is licensed under the Apache License "
            "2.0.<br>This application includes third-party software under their "
            "respective licenses.</p>"
            f'<p><a href="{PROJECT_URL}">WULPUS Pro Max source repository</a><br>'
            f'<a href="{DOCUMENTATION_URL}">WULPUS Pro Max documentation</a></p>'
            "<p>See Third-party notices for copyright and license details.</p>"
        )
        for label in box.findChildren(QtWidgets.QLabel):
            if "href=" in label.text():
                label.setOpenExternalLinks(True)
        box.exec()

    def show_third_party_notices(self):
        """Show the third-party notices bundled with the application."""
        source_path = Path(__file__).with_name("THIRD_PARTY_NOTICES.txt")
        bundled_path = (
            Path(getattr(sys, "_MEIPASS", source_path.parent)) / source_path.name
        )
        path = bundled_path if bundled_path.is_file() else source_path
        try:
            notices = path.read_text(encoding="utf-8")
        except OSError as error:
            QtWidgets.QMessageBox.warning(
                self, "Third-party notices unavailable", str(error)
            )
            return
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Third-party notices")
        dialog.resize(760, 620)
        layout = QtWidgets.QVBoxLayout(dialog)
        text = QtWidgets.QPlainTextEdit(notices)
        text.setReadOnly(True)
        layout.addWidget(text)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def toggle_debug_logging(self, enabled):
        """Prompt for a destination and attach or detach the batched log handler."""
        if enabled:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Write debug log",
                "wulpus-debug.log",
                "Log (*.log);;All files (*)",
            )
            if not path:
                self.debug_action.blockSignals(True)
                self.debug_action.setChecked(False)
                self.debug_action.blockSignals(False)
                return
            try:
                handler = BatchedFileHandler(path)
            except OSError as error:
                self.debug_action.blockSignals(True)
                self.debug_action.setChecked(False)
                self.debug_action.blockSignals(False)
                QtWidgets.QMessageBox.critical(
                    self, "Debug logging unavailable", str(error)
                )
                return
            root = logging.getLogger()
            self.previous_log_level = root.level
            root.setLevel(logging.DEBUG)
            root.addHandler(handler)
            self.debug_handler = handler
            self.debug_action.setText("Disable debug logging")
            logger.info("Debug logging enabled: %s", path)
            self.statusBar().showMessage(f"Debug logging to {path}", 5000)
        else:
            self.stop_debug_logging()

    def stop_debug_logging(self):
        """Detach logging, restore the prior level, and drain accepted records."""
        handler, self.debug_handler = self.debug_handler, None
        if handler is None:
            return
        logger.info("Debug logging disabled")
        root = logging.getLogger()
        root.removeHandler(handler)
        if self.previous_log_level is not None:
            root.setLevel(self.previous_log_level)
        self.previous_log_level = None
        handler.close()
        self.debug_action.setText("Enable debug logging…")
        if handler.error is not None:
            QtWidgets.QMessageBox.warning(
                self, "Debug logging error", str(handler.error)
            )

    def update_capabilities(self):
        """Recompute panel availability when connection state changes."""
        connected = self.session.connected
        caps = self.session.capabilities
        self.acquisition.set_device_actions_available(
            connected and caps.reset_device, connected and caps.reset_msp
        )
        self.device_config.set_available(connected and caps.device_config)
        self.service.set_available(
            connected and caps.runtime_status and not self.session.busy_operation
        )
        self.firmware.set_available(
            connected and caps.msp_update, not self.session.busy_operation
        )
        link = self.session.link if connected and caps.firmware_info else None
        if link is not self._firmware_info_link:
            self._firmware_info_link = link
            if link is not None:
                # Match the notebook UI by reporting the running firmware as
                # soon as a capable transport connects.
                QtCore.QTimer.singleShot(0, self.firmware.load_versions)

    def operation_changed(self, running):
        """Gate editing and service actions while allowing acquisition recovery."""
        self.connection.setEnabled(not running)
        self.tabs.setTabEnabled(0, not running)
        connected = self.session.connected
        caps = self.session.capabilities
        self.acquisition.set_device_actions_available(
            connected and caps.reset_device, connected and caps.reset_msp
        )
        self.service.set_available(
            False
            if running
            else self.session.connected and self.session.capabilities.runtime_status
        )
        self.firmware.set_available(
            self.session.connected and self.session.capabilities.msp_update, not running
        )
        if not running and connected and caps.firmware_info:
            # The ESP32 learns the MSP430 version during the full-duplex
            # configuration exchange at acquisition start.
            self.firmware.load_versions()

    def closeEvent(self, event):
        """Shut down background resources before accepting a window close."""
        # Do not destroy widgets while worker callbacks can still target them.
        if self.pool.activeThreadCount() or self.session.busy_operation not in (
            None,
            "acquisition",
        ):
            self.statusBar().showMessage(
                "Waiting for the device operation to finish before closing", 5000
            )
            event.ignore()
            return
        if self.acquisition.worker:
            self.acquisition.worker.stop()
            if self.acquisition.thread and not self.acquisition.thread.wait(2000):
                event.ignore()
                return
        try:
            if self.session.connected and not self.session.busy_operation:
                self.session.disconnect()
        except Exception:
            logger.exception("Disconnect during shutdown failed")
        self.viewer.stop_replay()
        self.stop_debug_logging()
        event.accept()
