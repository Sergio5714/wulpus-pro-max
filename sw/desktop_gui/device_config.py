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


Device configuration components for the desktop application.
"""

from __future__ import annotations

import logging

from PySide6 import QtWidgets
from wulpus.wifi_link import WulpusProDeviceConfig, WulpusProWiFiPowerSave

from .async_ui import AsyncMixin, busy_button

logger = logging.getLogger(__name__)


class DeviceConfigTab(QtWidgets.QWidget, AsyncMixin):
    """Edit persistent host settings and Wi-Fi provisioning over USB CDC."""

    def __init__(self, session, pool):
        """Initialize persistent device and Wi-Fi configuration controls."""
        super().__init__()
        self.session, self.pool = session, pool
        self.wifi_boot = QtWidgets.QCheckBox("Enable Wi-Fi at boot")
        self.auto = QtWidgets.QCheckBox("Automatic provisioning")
        self.power = QtWidgets.QComboBox()
        for item in WulpusProWiFiPowerSave:
            self.power.addItem(item.name, item)
        self.twt = QtWidgets.QCheckBox("Enable TWT")
        self.ssid = QtWidgets.QLineEdit()
        self.password = QtWidgets.QLineEdit()
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.load_button = QtWidgets.QPushButton("Load")
        self.save_button = QtWidgets.QPushButton("Save settings")
        self.credentials_button = QtWidgets.QPushButton("Replace credentials")
        self.clear_button = QtWidgets.QPushButton("Clear credentials")
        self.reboot_button = QtWidgets.QPushButton("Reboot ESP32")
        buttons = (
            self.load_button,
            self.save_button,
            self.credentials_button,
            self.clear_button,
            self.reboot_button,
        )
        self.controls = [
            *buttons,
            self.wifi_boot,
            self.auto,
            self.power,
            self.twt,
            self.ssid,
            self.password,
        ]
        self.load_button.clicked.connect(self.load)
        self.save_button.clicked.connect(self.save)
        self.credentials_button.clicked.connect(self.set_credentials)
        self.clear_button.clicked.connect(self.clear_credentials)
        self.reboot_button.clicked.connect(self.reboot)
        form = QtWidgets.QFormLayout()
        form.addRow(self.wifi_boot)
        form.addRow(self.auto)
        form.addRow("Power save", self.power)
        form.addRow(self.twt)
        form.addRow("New SSID", self.ssid)
        form.addRow("New password", self.password)
        button_layout = QtWidgets.QHBoxLayout()
        [button_layout.addWidget(x) for x in buttons]
        button_layout.addStretch()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(button_layout)
        layout.addStretch()

    def set_available(self, available):
        """Enable provisioning fields only for an available USB session."""
        for control in self.controls:
            control.setEnabled(available)
        self.setToolTip(
            ""
            if available
            else "Persistent provisioning requires a connected USB CDC device"
        )

    def load(self):
        """Fetch persistent device settings and Wi-Fi status asynchronously."""
        link = self.session.require("device_config")

        def operation():
            """Read device configuration and Wi-Fi status off the UI thread."""
            return link.get_device_config(), link.get_wifi_status()

        def done(value):
            """Populate configuration controls from a completed read."""
            config, status = value
            self.wifi_boot.setChecked(config.wifi_enabled_at_boot)
            self.auto.setChecked(config.auto_provision)
            self.power.setCurrentIndex(self.power.findData(config.wifi_power_save_mode))
            self.twt.setChecked(config.twt_enabled)
            QtWidgets.QMessageBox.information(
                self,
                "Configuration",
                f"Loaded. Credentials present: {status.credentials_present}",
            )

        self.run_task(operation, done, busy=busy_button(self.load_button, "Loading…"))

    def save(self):
        """Persist edited host settings; changes take effect after reboot."""
        link = self.session.require("device_config")
        config = WulpusProDeviceConfig(
            self.wifi_boot.isChecked(),
            self.auto.isChecked(),
            self.power.currentData(),
            self.twt.isChecked(),
        )
        self.run_task(
            lambda: link.set_device_config(config),
            lambda _: QtWidgets.QMessageBox.information(
                self, "Saved", "Settings saved; reboot required."
            ),
            busy=busy_button(self.save_button, "Saving…"),
        )

    def set_credentials(self):
        """Send replacement credentials and immediately clear the password field."""
        link = self.session.require("device_config")
        ssid, password = self.ssid.text(), self.password.text()
        self.password.clear()
        self.run_task(
            lambda: link.set_wifi_credentials(ssid, password),
            lambda _: self.ssid.clear(),
            busy=busy_button(self.credentials_button, "Replacing…"),
        )

    def clear_credentials(self):
        """Confirm removal of stored Wi-Fi credentials before sending the command."""
        if (
            QtWidgets.QMessageBox.question(
                self, "Remove credentials", "Remove stored Wi-Fi credentials?"
            )
            == QtWidgets.QMessageBox.Yes
        ):
            link = self.session.require("device_config")
            self.run_task(
                link.clear_wifi_credentials,
                busy=busy_button(self.clear_button, "Clearing…"),
            )

    def reboot(self):
        """Confirm and request host reboot for changed persistent settings."""
        if (
            QtWidgets.QMessageBox.question(
                self, "Reboot", "Reboot the ESP32 and disconnect?"
            )
            == QtWidgets.QMessageBox.Yes
        ):
            link = self.session.require("device_config")
            self.run_task(
                link.reset, busy=busy_button(self.reboot_button, "Rebooting…")
            )
