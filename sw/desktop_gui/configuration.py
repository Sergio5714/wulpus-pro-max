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


Configuration components for the desktop application.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6 import QtWidgets
from wulpus.config_package_pro import configuration_package, us_to_ticks

from .models import (
    build_config,
    config_values,
    load_config,
    save_config,
)
from .txrx import TxRxConfigCard, TxRxConfigDialog

logger = logging.getLogger(__name__)


class ConfigEditor(QtWidgets.QWidget):
    """Edit acquisition parameters and ordered 16-bit TX/RX channel masks."""

    def __init__(self):
        """Initialize acquisition fields and the ordered TX/RX editor."""
        super().__init__()
        self.inputs = {}
        defaults = config_values(build_config({}))
        root = QtWidgets.QVBoxLayout(self)
        buttons = QtWidgets.QHBoxLayout()
        load = QtWidgets.QPushButton("Load JSON")
        save = QtWidgets.QPushButton("Save JSON")
        load.clicked.connect(self.load_json)
        save.clicked.connect(self.save_json)
        buttons.addWidget(load)
        buttons.addWidget(save)
        buttons.addStretch()
        root.addLayout(buttons)
        split = QtWidgets.QSplitter()
        root.addWidget(split, 1)
        parameters = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(parameters)
        for section in configuration_package:
            for param in section:
                value = defaults[param.config_name]
                if param.limit_type == "list":
                    widget = QtWidgets.QComboBox()
                    for option in param.max_val:
                        widget.addItem(str(option), option)
                    widget.setCurrentIndex(max(0, widget.findData(value)))
                else:
                    widget = QtWidgets.QSpinBox()
                    try:
                        minimum = int(
                            param.min_val / us_to_ticks[param.config_name] + 1
                        )
                        maximum = int(
                            param.max_val / us_to_ticks[param.config_name] + 1
                        )
                    except KeyError:
                        minimum, maximum = int(param.min_val), int(param.max_val)
                    widget.setRange(minimum, maximum)
                    widget.setValue(int(value))
                self.inputs[param.config_name] = widget
                form.addRow(param.friendly_name, widget)
        self.tx_masks = [0xFFFF] + [0] * 15
        self.rx_masks = [0xFFFF] + [0] * 15
        self.cards = {}
        self.selected_config = 0
        self.inputs["num_txrx_configs"].valueChanged.connect(self._mask_count)
        mask_box = QtWidgets.QWidget()
        mask_layout = QtWidgets.QVBoxLayout(mask_box)
        mask_layout.addWidget(QtWidgets.QLabel("TX/RX configurations (channels 0–15)"))
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        self.card_layout = QtWidgets.QVBoxLayout(content)
        self.card_layout.setContentsMargins(2, 2, 2, 2)
        self.card_layout.addStretch()
        scroll.setWidget(content)
        mask_layout.addWidget(scroll, 1)
        card_buttons = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("+ Add")
        edit = QtWidgets.QPushButton("Edit")
        remove = QtWidgets.QPushButton("− Remove")
        add.clicked.connect(self.add_config)
        edit.clicked.connect(self.edit_config)
        remove.clicked.connect(self.remove_config)
        card_buttons.addWidget(add)
        card_buttons.addWidget(edit)
        card_buttons.addWidget(remove)
        card_buttons.addStretch()
        mask_layout.addLayout(card_buttons)
        file_buttons = QtWidgets.QHBoxLayout()
        load_tx_rx = QtWidgets.QPushButton("Load TX/RX…")
        save_tx_rx = QtWidgets.QPushButton("Save TX/RX…")
        load_tx_rx.clicked.connect(self.load_tx_rx)
        save_tx_rx.clicked.connect(self.save_tx_rx)
        file_buttons.addWidget(load_tx_rx)
        file_buttons.addWidget(save_tx_rx)
        file_buttons.addStretch()
        mask_layout.addLayout(file_buttons)
        parameters.setMinimumWidth(420)
        mask_box.setMinimumWidth(520)
        split.addWidget(parameters)
        split.addWidget(mask_box)
        split.setCollapsible(0, False)
        split.setCollapsible(1, False)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 5)
        split.setSizes([520, 650])
        self._mask_count(defaults["num_txrx_configs"])

    def _mask_count(self, count):
        """Rebuild visible cards while retaining masks for temporarily hidden rows."""
        for card in self.cards.values():
            self.card_layout.removeWidget(card)
            card.deleteLater()
        self.cards = {}
        for index in range(count):
            card = TxRxConfigCard(index, self.tx_masks[index], self.rx_masks[index])
            card.selected.connect(self.select_config)
            card.edit_requested.connect(self.edit_config)
            self.cards[index] = card
            self.card_layout.insertWidget(self.card_layout.count() - 1, card)
        self.select_config(min(self.selected_config, count - 1))

    def select_config(self, index):
        """Highlight the card targeted by edit/remove commands."""
        self.selected_config = index
        for card_index, card in self.cards.items():
            card.set_selected(card_index == index)

    def edit_config(self, index=None):
        """Open a transactional editor for the selected or specified mask pair."""
        index = (
            self.selected_config if index is None or isinstance(index, bool) else index
        )
        dialog = TxRxConfigDialog(
            index, self.tx_masks[index], self.rx_masks[index], self
        )
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.tx_masks[index], self.rx_masks[index] = dialog.masks()
            self.cards[index].refresh(self.tx_masks[index], self.rx_masks[index])

    def add_config(self):
        """Expose the next configuration slot, up to the firmware limit of 16."""
        count = self.inputs["num_txrx_configs"].value()
        if count < 16:
            self.inputs["num_txrx_configs"].setValue(count + 1)
            self.select_config(count)

    def remove_config(self):
        """Remove the selected pair and compact firmware configuration IDs."""
        count = self.inputs["num_txrx_configs"].value()
        if count <= 1:
            return
        index = self.selected_config
        self.tx_masks[index : count - 1] = self.tx_masks[index + 1 : count]
        self.rx_masks[index : count - 1] = self.rx_masks[index + 1 : count]
        self.tx_masks[count - 1] = 0
        self.rx_masks[count - 1] = 0
        self.inputs["num_txrx_configs"].setValue(count - 1)

    @staticmethod
    def _channels(mask):
        """Return channel indices selected by a 16-bit mask."""
        return [channel for channel in range(16) if mask & (1 << channel)]

    def save_tx_rx(self):
        """Export active channel lists in the legacy configs JSON schema."""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save TX/RX configurations", "tx_rx_configs.json", "JSON (*.json)"
        )
        if not path:
            return
        count = self.inputs["num_txrx_configs"].value()
        data = {
            "configs": [
                {
                    "config_id": index,
                    "tx_channels": self._channels(self.tx_masks[index]),
                    "rx_channels": self._channels(self.rx_masks[index]),
                    "optimized_switching": False,
                }
                for index in range(count)
            ]
        }
        try:
            Path(path).write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        except OSError as error:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(error))

    def load_tx_rx(self):
        """Validate a legacy file fully before applying its channel masks."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load TX/RX configurations", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            entries = data.get("configs")
            if not isinstance(entries, list) or not 1 <= len(entries) <= 16:
                raise ValueError(
                    "The file must contain between 1 and 16 TX/RX configurations"
                )
            masks = []
            for index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    raise ValueError(f"Configuration {index} is invalid")
                config_id = int(entry.get("config_id", index))
                if config_id != index:
                    raise ValueError(
                        "Configuration IDs must be contiguous and start at 0"
                    )
                tx = {int(channel) for channel in entry["tx_channels"]}
                rx = {int(channel) for channel in entry["rx_channels"]}
                if not tx.issubset(range(16)) or not rx.issubset(range(16)):
                    raise ValueError(
                        f"Configuration {index} contains a channel outside 0–15"
                    )
                masks.append(
                    (
                        sum(1 << channel for channel in tx),
                        sum(1 << channel for channel in rx),
                    )
                )
            for index, (tx_mask, rx_mask) in enumerate(masks):
                self.tx_masks[index] = tx_mask
                self.rx_masks[index] = rx_mask
            self.inputs["num_txrx_configs"].setValue(len(masks))
            self._mask_count(len(masks))
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as error:
            QtWidgets.QMessageBox.critical(self, "Load failed", str(error))

    def values(self):
        """Return current parameter values and ordered TX/RX masks."""
        data = {}
        for key, widget in self.inputs.items():
            data[key] = (
                widget.currentData()
                if isinstance(widget, QtWidgets.QComboBox)
                else widget.value()
            )
        count = data["num_txrx_configs"]
        data["tx_configs"] = self.tx_masks[:count]
        data["rx_configs"] = self.rx_masks[:count]
        return data

    def config(self):
        """Build the validated hardware configuration used by acquisition."""
        return build_config(self.values())

    def set_config(self, config):
        """Populate fields and channel cards from a hardware configuration."""
        values = config_values(config)
        for key, widget in self.inputs.items():
            if isinstance(widget, QtWidgets.QComboBox):
                widget.setCurrentIndex(widget.findData(values[key]))
            else:
                widget.setValue(values[key])
        for i, value in enumerate(values["tx_configs"]):
            self.tx_masks[i] = int(value)
        for i, value in enumerate(values["rx_configs"]):
            self.rx_masks[i] = int(value)
        self._mask_count(values["num_txrx_configs"])

    def load_json(self):
        """Load a complete acquisition configuration from a user-selected file."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load configuration", "", "JSON (*.json)"
        )
        if path:
            try:
                self.set_config(load_config(path))
            except Exception as error:
                QtWidgets.QMessageBox.critical(
                    self, "Invalid configuration", str(error)
                )

    def save_json(self):
        """Validate and save the complete acquisition configuration."""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save configuration", "uss_config.json", "JSON (*.json)"
        )
        if path:
            try:
                save_config(path, self.config())
            except Exception as error:
                QtWidgets.QMessageBox.critical(
                    self, "Invalid configuration", str(error)
                )
