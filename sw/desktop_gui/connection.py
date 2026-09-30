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


Connection components for the desktop application.
"""

from __future__ import annotations

import logging

from PySide6 import QtCore, QtWidgets

from .async_ui import AsyncMixin

logger = logging.getLogger(__name__)


class ConnectionBar(QtWidgets.QWidget, AsyncMixin):
    """Discovery and connection controls; discard results from superseded scans."""

    state_changed = QtCore.Signal()

    def __init__(self, session, pool, parent=None):
        """Initialize transport selection and asynchronous connection controls."""
        super().__init__(parent)
        self.session, self.pool, self.devices = session, pool, []
        self._scan_generation = 0
        self.transport = QtWidgets.QComboBox()
        self.transport.addItems(session.links)
        self.device = QtWidgets.QComboBox()
        self.scan = QtWidgets.QPushButton("Scan")
        self.connect = QtWidgets.QPushButton("Connect")
        self.connect.setObjectName("connectButton")
        self._set_connected_visual(False)
        self.disconnect = QtWidgets.QPushButton("Disconnect")
        self.disconnect.setEnabled(False)
        self.status = QtWidgets.QLabel("Disconnected")
        row = QtWidgets.QHBoxLayout(self)
        row.addWidget(QtWidgets.QLabel("Transport"))
        row.addWidget(self.transport)
        row.addWidget(QtWidgets.QLabel("Device"))
        row.addWidget(self.device, 1)
        row.addWidget(self.scan)
        row.addWidget(self.connect)
        row.addWidget(self.disconnect)
        row.addWidget(self.status)
        self.transport.currentTextChanged.connect(self.change_transport)
        self.scan.clicked.connect(self.scan_devices)
        self.connect.clicked.connect(self.connect_device)
        self.disconnect.clicked.connect(self.disconnect_device)
        self.scan_devices()

    def change_transport(self, name):
        """Select and rescan a transport only while disconnected."""
        if self.session.connected:
            self.transport.blockSignals(True)
            self.transport.setCurrentText(self.session.transport)
            self.transport.blockSignals(False)
            return
        self.session.select_transport(name)
        self.scan_devices()
        self.state_changed.emit()

    def scan_devices(self):
        """Start discovery and invalidate any result from an older scan."""
        if self.session.connected:
            return
        self._scan_generation += 1
        generation = self._scan_generation
        self.device.clear()
        self.devices = []
        self.connect.setEnabled(False)
        self.run_task(
            self.session.scan, lambda devices: self._scanned(generation, devices)
        )

    def _scanned(self, generation, devices):
        """Apply scan results when they belong to the latest scan request."""
        if generation != self._scan_generation or self.session.connected:
            return
        self.devices = list(devices)
        self.device.addItems([str(item) for item in self.devices])
        self.connect.setEnabled(bool(self.devices))

    def connect_device(self):
        """Open the currently selected discovered endpoint asynchronously."""
        if self.session.connected:
            return
        if self.device.currentIndex() < 0:
            return
        selected = self.devices[self.device.currentIndex()]
        self.run_task(
            lambda: self.session.connect(selected),
            self._connected,
            busy=self.connect.setEnabled,
        )

    def disconnect_device(self):
        """Close the session asynchronously and refresh connection controls."""
        if not self.session.connected:
            self.reflect_session()
            return
        self.status.setText("Disconnecting…")
        self.disconnect.setEnabled(False)
        task = self.run_task(self.session.disconnect, self._disconnected)
        task.signals.error.connect(self._disconnect_failed)

    def _connected(self, _):
        """Update controls after a connection succeeds."""
        self.status.setText(f"Connected via {self.session.transport}")
        self._set_connected_visual(True)
        self.connect.setEnabled(False)
        self.disconnect.setEnabled(True)
        self.transport.setEnabled(False)
        self.device.setEnabled(False)
        self.scan.setEnabled(False)
        self.state_changed.emit()

    def _disconnected(self, _):
        """Update controls after a disconnection succeeds."""
        self.status.setText("Disconnected")
        self._set_connected_visual(False)
        self.connect.setEnabled(bool(self.devices))
        self.disconnect.setEnabled(False)
        self.transport.setEnabled(True)
        self.device.setEnabled(True)
        self.scan.setEnabled(True)
        self.state_changed.emit()

    def _disconnect_failed(self, _traceback_text):
        """Restore the connected state after a failed disconnection."""
        self.status.setText(f"Connected via {self.session.transport}")
        self._set_connected_visual(True)
        self.connect.setEnabled(False)
        self.disconnect.setEnabled(True)

    def reflect_session(self):
        """Synchronize controls after another tab deliberately closes a link."""
        if not self.session.connected:
            self.status.setText("Disconnected")
            self._set_connected_visual(False)
            self.connect.setEnabled(bool(self.devices))
            self.disconnect.setEnabled(False)
            self.transport.setEnabled(True)
            self.device.setEnabled(True)
            self.scan.setEnabled(True)
            self.state_changed.emit()

    def _set_connected_visual(self, connected):
        """Expose connection state to the theme and refresh button styling."""
        self.connect.setProperty("connected", connected)
        self.connect.style().unpolish(self.connect)
        self.connect.style().polish(self.connect)
        self.connect.update()
