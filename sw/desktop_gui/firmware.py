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


Firmware components for the desktop application.
"""

from __future__ import annotations

import logging

from PySide6 import QtCore, QtWidgets
from serial.tools import list_ports
from wulpus.esp32_update import Esp32ReleasePackage
from wulpus.msp430_update import MSP430Updater, load_image

from .async_ui import AsyncMixin, _error_text
from .esp_flash import flash_package

logger = logging.getLogger(__name__)


class FirmwareTab(QtWidgets.QWidget, AsyncMixin):
    """Validate release packages and coordinate asynchronous firmware updates.

    ESP32 flashing takes exclusive ownership of the serial port. MSP430
    updates use the connected host's programming commands and emit progress
    through Qt signals so worker threads never update widgets directly.
    """

    session_changed = QtCore.Signal()
    msp_progress_received = QtCore.Signal(object)

    def __init__(self, session, pool):
        """Initialize firmware inspection, selection, and update controls."""
        super().__init__()
        self.session, self.pool, self.esp_package = session, pool, None
        self.msp_image = None
        self.versions = QtWidgets.QLabel(
            "Connect over USB CDC or Wi-Fi to read installed versions"
        )
        self.versions.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.refresh_versions = QtWidgets.QPushButton("Refresh firmware versions")
        self.refresh_versions.clicked.connect(self.load_versions)
        self.esp_path = QtWidgets.QLineEdit()
        esp_select = QtWidgets.QPushButton("Select ESP32 ZIP")
        self.esp_port = QtWidgets.QComboBox()
        esp_ports = QtWidgets.QPushButton("Refresh ports")
        self.esp_port.currentTextChanged.connect(self._flash_enabled)
        self.confirm = QtWidgets.QCheckBox("I will keep USB and board power connected")
        self.flash = QtWidgets.QPushButton("Flash ESP32")
        self.flash.setEnabled(False)
        self.msp_path = QtWidgets.QLineEdit()
        self.msp_path.setReadOnly(True)
        msp_select = QtWidgets.QPushButton("Select MSP430 ZIP/image")
        self.program = QtWidgets.QPushButton("Program MSP430")
        self.program.setEnabled(False)
        self.msp_ready = QtWidgets.QLabel(
            "Select and validate an MSP430 firmware package"
        )
        self.msp_progress = QtWidgets.QProgressBar()
        self.msp_progress.setRange(0, 100)
        self.msp_progress.setValue(0)
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        esp_select.clicked.connect(self.select_esp)
        esp_ports.clicked.connect(self.refresh_ports)
        self.confirm.toggled.connect(self._flash_enabled)
        self.flash.clicked.connect(self.flash_esp)
        msp_select.clicked.connect(self.select_msp)
        self.program.clicked.connect(self.program_msp)
        self.msp_progress_received.connect(self.show_msp_progress)
        installed = QtWidgets.QGroupBox("Installed firmware")
        installed_layout = QtWidgets.QHBoxLayout(installed)
        installed_layout.addWidget(self.versions, 1)
        installed_layout.addWidget(self.refresh_versions)
        esp = QtWidgets.QGroupBox("ESP32-C6")
        e = QtWidgets.QGridLayout(esp)
        e.addWidget(self.esp_path, 0, 0)
        e.addWidget(esp_select, 0, 1)
        e.addWidget(self.esp_port, 1, 0)
        e.addWidget(esp_ports, 1, 1)
        e.addWidget(self.confirm, 2, 0)
        e.addWidget(self.flash, 2, 1)
        msp = QtWidgets.QGroupBox("MSP430")
        m = QtWidgets.QGridLayout(msp)
        m.addWidget(self.msp_path, 0, 0)
        m.addWidget(msp_select, 0, 1)
        m.addWidget(self.msp_ready, 1, 0)
        m.addWidget(self.program, 1, 1)
        m.addWidget(self.msp_progress, 2, 0, 1, 2)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(installed)
        layout.addWidget(esp)
        layout.addWidget(msp)
        layout.addWidget(self.output, 1)
        self.refresh_ports()

    def set_available(self, msp_available, idle):
        """Refresh update controls from capabilities, session state, and packages."""
        del msp_available  # Derived from the live session below.
        self.sync_esp_port()
        self._update_msp_enabled(idle)
        self.flash.setEnabled(
            idle
            and self.confirm.isChecked()
            and self.esp_package is not None
            and self.esp_port.currentIndex() >= 0
        )
        version_available = (
            self.session.connected and self.session.capabilities.firmware_info and idle
        )
        self.refresh_versions.setEnabled(version_available)
        if not self.session.connected:
            self.versions.setText(
                "Connect over USB CDC or Wi-Fi to read installed versions"
            )
        elif not self.session.capabilities.firmware_info:
            self.versions.setText(
                f"Installed versions are unavailable over {self.session.transport}"
            )

    def load_versions(self):
        """Read installed host/MSP firmware versions on a background task."""
        try:
            link = self.session.require("firmware_info")
        except Exception as error:
            QtWidgets.QMessageBox.critical(self, "Versions unavailable", str(error))
            return
        self.refresh_versions.setEnabled(False)

        def done(info):
            """Display firmware information returned by the device."""
            self.show_versions(info)
            self.session.log("Installed firmware versions refreshed")

        task = self.run_task(lambda: link.get_firmware_info(), done)
        task.signals.finished.connect(
            lambda: self.refresh_versions.setEnabled(
                self.session.connected
                and self.session.capabilities.firmware_info
                and not self.session.busy_operation
            )
        )

    def show_versions(self, info):
        """Render installed firmware identifiers and update capability hints."""

        def describe(version, git_hash, dirty):
            """Format a version and optional repository metadata for display."""
            text = version or "unknown"
            if git_hash:
                text += f" · {git_hash}"
            if dirty:
                text += " · dirty build"
            return text

        self.versions.setText(
            "ESP32: "
            + describe(info.esp_version, info.esp_git_hash, info.esp_dirty)
            + "\nMSP430: "
            + describe(info.msp_version, info.msp_git_hash, info.msp_dirty)
        )

    def refresh_ports(self):
        """Enumerate serial flash targets and reconcile the active USB port."""
        previous = self.esp_port.currentText()
        ports = [port.device for port in list_ports.comports()]
        self.esp_port.blockSignals(True)
        self.esp_port.clear()
        self.esp_port.addItems(ports)
        preferred = self.active_usb_port() or previous
        if preferred:
            index = self.esp_port.findText(preferred, QtCore.Qt.MatchFixedString)
            if index < 0 and self.active_usb_port():
                self.esp_port.addItem(preferred)
                index = self.esp_port.count() - 1
            if index >= 0:
                self.esp_port.setCurrentIndex(index)
        self.esp_port.blockSignals(False)
        self._flash_enabled()

    def active_usb_port(self):
        """Return the connected USB endpoint name, or None for other transports."""
        if not self.session.connected or self.session.transport != "USB CDC":
            return ""
        device = self.session.device
        return str(getattr(device, "device", "") or "")

    def sync_esp_port(self):
        """Prefer the connected device's port when presenting ESP32 flash targets."""
        port = self.active_usb_port()
        if not port:
            return
        index = self.esp_port.findText(port, QtCore.Qt.MatchFixedString)
        if index < 0:
            self.esp_port.addItem(port)
            index = self.esp_port.count() - 1
        self.esp_port.setCurrentIndex(index)

    def select_esp(self):
        """Choose and validate an ESP32 release ZIP before enabling flash."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "ESP32 release", "", "ZIP (*.zip)"
        )
        if not path:
            return
        try:
            self.esp_package = Esp32ReleasePackage.load(path)
        except Exception as error:
            self.esp_package = None
            QtWidgets.QMessageBox.critical(self, "Invalid release", str(error))
            return
        self.esp_path.setText(path)
        self.output.appendPlainText(
            f"Validated ESP32 release {self.esp_package.version}"
        )
        self._flash_enabled()

    def _flash_enabled(self):
        """Enable ESP32 flashing only when all safety conditions are met."""
        self.flash.setEnabled(
            self.confirm.isChecked()
            and self.esp_package is not None
            and self.esp_port.currentIndex() >= 0
            and not self.session.busy_operation
        )

    def flash_esp(self):
        """Release an active USB session before handing its port to esptool."""
        package, port = self.esp_package, self.esp_port.currentText()
        active_port = self.active_usb_port()
        if active_port:
            # The device connected in the global connection bar is the source
            # of truth. Capture it before closing that session for esptool.
            port = active_port
            self.esp_port.setCurrentText(active_port)
        self.output.appendPlainText(f"ESP32 flash port: {port}")
        if self.session.connected and self.session.transport == "USB CDC":
            self.flash.setEnabled(False)
            self.output.appendPlainText(
                "Closing the active USB CDC session before flashing…"
            )
            task = self.run_task(
                self.session.disconnect,
                lambda _: self._usb_closed_for_flash(package, port),
            )
            task.signals.error.connect(lambda _: self._flash_enabled())
            return
        self._start_esp_flash(package, port)

    def _usb_closed_for_flash(self, package, port):
        """Continue flashing after the active USB link has closed."""
        self.session_changed.emit()
        self._start_esp_flash(package, port)

    def _start_esp_flash(self, package, port):
        """Run an ESP32 flash operation and stream its progress to the panel."""
        self.session.busy_operation = "ESP32 update"
        self.flash.setEnabled(False)
        messages = []

        def done(_):
            """Report successful ESP32 flashing and refresh panel state."""
            self.output.appendPlainText("".join(messages).rstrip())
            self.output.appendPlainText(
                "ESP32 update complete; reconnect after reboot."
            )

        task = self.run_task(
            lambda: flash_package(package, port, messages.append), done
        )
        task.signals.error.connect(
            lambda _: self.output.appendPlainText("".join(messages).rstrip())
        )
        task.signals.finished.connect(self._update_finished)

    def select_msp(self):
        """Choose and validate an MSP430 image or packaged release."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "MSP430 release",
            "",
            "Firmware (*.zip *.mspfw *.txt *.hex);;All files (*)",
        )
        if path:
            try:
                self.msp_image = load_image(path)
            except Exception as error:
                self.msp_image = None
                self.msp_path.clear()
                self._update_msp_enabled()
                QtWidgets.QMessageBox.critical(self, "Invalid firmware", str(error))
                return
            self.msp_path.setText(path)
            self.output.appendPlainText("Validated MSP430 firmware")
            self._update_msp_enabled()

    def _update_msp_enabled(self, idle=None):
        """Update MSP430 controls from session state and image availability."""
        if idle is None:
            idle = not self.session.busy_operation
        connected = self.session.connected
        compatible = connected and self.session.capabilities.msp_update
        ready = self.msp_image is not None
        self.program.setEnabled(bool(ready and compatible and idle))
        if not ready:
            message = "Select and validate an MSP430 firmware package"
        elif not connected:
            message = "Connect using USB CDC or Wi-Fi in the connection bar above"
        elif not self.session.capabilities.msp_update:
            message = f"MSP430 update is unavailable over {self.session.transport}"
        elif not idle:
            message = f"Waiting for {self.session.busy_operation} to finish"
        else:
            message = f"Ready to program over {self.session.transport}"
        self.msp_ready.setText(message)

    def program_msp(self):
        """Program the validated MSP430 image while reserving the session."""
        try:
            link = self.session.require("msp_update")
            if self.msp_image is None:
                raise ValueError("Select and validate an MSP430 firmware package")
            image = self.msp_image
        except Exception as error:
            QtWidgets.QMessageBox.critical(self, "Cannot update", str(error))
            return
        self.session.busy_operation = "MSP430 update"
        self.program.setEnabled(False)
        self.msp_progress.setValue(0)
        self.output.appendPlainText(
            f"Starting MSP430 update over {self.session.transport}: {len(image)} bytes"
        )

        def operation():
            """Program the MSP430 and read firmware information afterward."""
            status = MSP430Updater(link).program(
                image, progress=self.msp_progress_received.emit
            )
            # COMPLETE is reported only after the target has rebooted. Read the
            # ESP32's freshly detected MSP430 version in the same serialized
            # operation so the update tab cannot retain its pre-flash value.
            info = link.get_firmware_info(timeout=5.0)
            return status, info

        def done(value):
            """Present the completed MSP430 update and installed versions."""
            status, info = value
            self.output.appendPlainText(f"MSP430 update: {status.state.name}")
            self.show_versions(info)
            self.session.log(
                f"MSP430 update {status.state.name}; firmware versions refreshed"
            )

        task = self.run_task(operation, done)
        task.signals.error.connect(
            lambda text: self.output.appendPlainText(
                "MSP430 update failed: " + _error_text(text)
            )
        )
        task.signals.finished.connect(self._update_finished)

    @QtCore.Slot(object)
    def show_msp_progress(self, status):
        """Render a programmer progress snapshot received on the GUI thread."""
        completed = status.processed_bytes or status.received_bytes
        percent = int(100 * completed / max(1, status.total_bytes))
        if status.state.name == "COMPLETE":
            percent = 100
        self.msp_progress.setValue(max(0, min(100, percent)))
        details = (
            f"MSP430 {status.state.name}: received={status.received_bytes}/"
            f"{status.total_bytes}, processed={status.processed_bytes}, "
            f"address=0x{status.current_address:08x}, "
            f"device=0x{status.target_device_id:04x}, error={status.error}"
        )
        self.output.appendPlainText(details)

    def _update_finished(self):
        """Clear update state and restore firmware action availability."""
        self.session.busy_operation = None
        self._flash_enabled()
        self._update_msp_enabled()
