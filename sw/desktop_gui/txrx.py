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


TX/RX components for the desktop application.
"""

from __future__ import annotations

import logging

from PySide6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)


class TxRxConfigCard(QtWidgets.QFrame):
    """Compact, selectable visualization of one pair of 16-channel masks."""

    selected = QtCore.Signal(int)
    edit_requested = QtCore.Signal(int)

    def __init__(self, index, tx_mask, rx_mask):
        """Initialize a draggable summary card for one TX/RX configuration."""
        super().__init__()
        self.index = index
        self.tx_mask = tx_mask
        self.rx_mask = rx_mask
        self.setObjectName("configCard")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.title = QtWidgets.QLabel()
        self.title.setStyleSheet("font-weight:600")
        self.tx_label = QtWidgets.QLabel()
        self.rx_label = QtWidgets.QLabel()
        mono = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        self.tx_label.setFont(mono)
        self.rx_label.setFont(mono)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)
        layout.addWidget(self.title)
        layout.addWidget(self.tx_label)
        layout.addWidget(self.rx_label)
        self.refresh(tx_mask, rx_mask)

    @staticmethod
    def _channel_row(name, mask):
        """Format one channel mask as a row of discrete channel markers."""
        blocks = " ".join(
            "\u25a0" if mask & (1 << channel) else "\u25a1" for channel in range(16)
        )
        return f"{name}  {blocks}"

    def refresh(self, tx_mask, rx_mask):
        """Update the schematic channel indicators from the stored masks."""
        self.tx_mask = tx_mask
        self.rx_mask = rx_mask
        self.title.setText(f"Config {self.index}")
        self.tx_label.setText(self._channel_row("TX", tx_mask))
        self.rx_label.setText(self._channel_row("RX", rx_mask))

    def set_selected(self, selected):
        """Apply the selection property and refresh stylesheet-dependent rendering."""
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        """Select this configuration on mouse press."""
        self.selected.emit(self.index)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Request channel editing when the card is double-clicked."""
        self.edit_requested.emit(self.index)
        super().mouseDoubleClickEvent(event)


class TxRxConfigDialog(QtWidgets.QDialog):
    """Edit channel selections locally; callers apply masks only after acceptance."""

    def __init__(self, index, tx_mask, rx_mask, parent=None):
        """Initialize a modal editor for one TX/RX configuration."""
        super().__init__(parent)
        self.setWindowTitle(f"Edit TX/RX configuration {index}")
        self.setMinimumWidth(560)
        self.tx_buttons = self._channel_buttons(tx_mask)
        self.rx_buttons = self._channel_buttons(rx_mask)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(QtWidgets.QLabel("Select the active transducer channels:"))
        self.tx_group = self._channel_group("TX channels", self.tx_buttons)
        self.rx_group = self._channel_group("RX channels", self.rx_buttons)
        layout.addWidget(self.tx_group)
        layout.addSpacing(20)
        layout.addWidget(self.rx_group)
        layout.addSpacing(8)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _channel_buttons(mask):
        """Create toggle buttons initialized from a 16-bit channel mask."""
        result = []
        for channel in range(16):
            button = QtWidgets.QToolButton()
            button.setText(str(channel))
            button.setCheckable(True)
            button.setChecked(bool(mask & (1 << channel)))
            button.setMinimumSize(42, 34)
            result.append(button)
        return result

    @staticmethod
    def _channel_group(title, buttons):
        """Arrange one channel bank as two clearly separated rows of eight."""
        group = QtWidgets.QGroupBox(title)
        grid = QtWidgets.QGridLayout(group)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.setContentsMargins(12, 14, 12, 12)
        for channel, button in enumerate(buttons):
            grid.addWidget(button, channel // 8, channel % 8)
        return group

    def masks(self):
        """Encode selected channels as a pair of unsigned 16-bit integer masks."""

        def mask(buttons):
            """Encode checked channel buttons into a 16-bit mask."""
            return sum(
                1 << channel
                for channel, button in enumerate(buttons)
                if button.isChecked()
            )

        return mask(self.tx_buttons), mask(self.rx_buttons)
