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


Service components for the desktop application.
"""

from __future__ import annotations

import logging
from dataclasses import fields
from pathlib import Path

from PySide6 import QtCore, QtWidgets
from wulpus.msp430_update import MSP430Updater

from .async_ui import AsyncMixin
from .models import (
    ERROR_NAMES,
)

logger = logging.getLogger(__name__)


class ServiceTab(QtWidgets.QWidget, AsyncMixin):
    """Inspect device diagnostics, clear selected errors, and export session events."""

    def __init__(self, session, pool):
        """Initialize device diagnostics, error, and event-log controls."""
        super().__init__()
        self.session, self.pool = session, pool
        self.summary = QtWidgets.QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.errors = QtWidgets.QListWidget()
        refresh = QtWidgets.QPushButton("Refresh")
        clear = QtWidgets.QPushButton("Clear selected errors")
        reset = QtWidgets.QPushButton("Clear errors + reset counters")
        export = QtWidgets.QPushButton("Export event log")
        self.action_controls = [refresh, clear, reset]
        refresh.clicked.connect(self.refresh)
        clear.clicked.connect(self.clear_selected)
        reset.clicked.connect(self.reset_all)
        export.clicked.connect(self.export_log)
        top = QtWidgets.QHBoxLayout()
        [top.addWidget(x) for x in (refresh, clear, reset, export)]
        top.addStretch()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(QtWidgets.QLabel("Sticky errors"))
        layout.addWidget(self.errors)
        layout.addWidget(QtWidgets.QLabel("Status and diagnostics"))
        layout.addWidget(self.summary, 1)

    def set_available(self, available):
        """Gate device commands while leaving local log export available."""
        for control in self.action_controls:
            control.setEnabled(available)

    def refresh(self):
        """Fetch supported status groups asynchronously and render them together."""
        link = self.session.require("runtime_status")

        def operation():
            """Collect supported diagnostic information from the device."""
            result = {"status": link.get_status(), "firmware": link.get_firmware_info()}
            if self.session.capabilities.wifi_status:
                result["wifi"] = link.get_wifi_status()
            if self.session.capabilities.msp_update:
                try:
                    result["msp_diagnostics"] = MSP430Updater(link).diagnostics()
                except Exception as error:
                    result["msp_diagnostics_error"] = str(error)
            return result

        self.run_task(operation, self._show_status)

    def _show_status(self, result):
        """Render device status and decoded errors in the service panel."""
        status = result["status"]
        self.errors.clear()
        for bit, name in ERROR_NAMES.items():
            if not status.error_flags & bit:
                continue
            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.UserRole, bit)
            item.setCheckState(QtCore.Qt.Checked)
            self.errors.addItem(item)
        if not status.error_flags:
            self.errors.addItem("None")
        lines = [
            f"{field.name}: {getattr(status, field.name)}" for field in fields(status)
        ]
        firmware = result["firmware"]
        lines += ["", "Firmware"] + [
            f"{field.name}: {getattr(firmware, field.name)}"
            for field in fields(firmware)
        ]
        for key in ("wifi", "msp_diagnostics"):
            if key in result:
                lines += ["", key.replace("_", " ").title()] + [
                    f"{field.name}: {getattr(result[key], field.name)}"
                    for field in fields(result[key])
                ]
        if "msp_diagnostics_error" in result:
            lines += [
                "",
                "MSP430 diagnostics unavailable: " + result["msp_diagnostics_error"],
            ]
        self.summary.setPlainText("\n".join(lines))
        self.session.log("Service status refreshed")

    def clear_selected(self):
        """Clear the checked sticky-error bits and refresh the displayed status."""
        mask = sum(
            self.errors.item(i).data(QtCore.Qt.UserRole) or 0
            for i in range(self.errors.count())
            if self.errors.item(i).checkState() == QtCore.Qt.Checked
        )
        if mask:
            self.run_task(
                lambda: self.session.require("runtime_status").clear_status(
                    error_mask=mask
                ),
                lambda _: self.refresh(),
            )

    def reset_all(self):
        """Confirm and clear all sticky errors and diagnostic counters."""
        if (
            QtWidgets.QMessageBox.question(
                self,
                "Reset counters",
                "Clear all sticky errors and diagnostic counters?",
            )
            == QtWidgets.QMessageBox.Yes
        ):
            self.run_task(
                lambda: self.session.require("runtime_status").clear_status(
                    clear_counters=True
                ),
                lambda _: self.refresh(),
            )

    def export_log(self):
        """Write the in-memory session event history to a chosen UTF-8 file."""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export event log", "wulpus-events.log", "Log (*.log);;All files (*)"
        )
        if path:
            Path(path).write_text(
                "\n".join(self.session.events) + "\n", encoding="utf-8"
            )
