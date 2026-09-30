"""Standalone WULPUS Pro Max desktop GUI.

Run from ``sw`` with ``python -m desktop_gui.main``.
"""

from __future__ import annotations

import argparse
from dataclasses import fields
import json
import logging
from pathlib import Path
import sys

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets
from scipy import signal
from serial.tools import list_ports

from wulpus.config_package_pro import configuration_package, us_to_ticks
from wulpus.esp32_update import Esp32ReleasePackage
from wulpus.msp430_update import MSP430Updater, load_image
from wulpus.wifi_link import WulpusProDeviceConfig, WulpusProWiFiPowerSave

from . import APP_NAME, APP_VERSION
from .controller import SessionController, default_links
from .debug_log import BatchedFileHandler
from .esp_flash import flash_package
from .models import (
    ERROR_NAMES, build_config, config_values, load_config, save_config, save_npz,
)
from .workers import AcquisitionWorker, Task


logger = logging.getLogger(__name__)


TX_RX_STYLESHEET = " QFrame#configCard{border:1px solid #69727d;border-radius:5px} QFrame#configCard[selected=true]{border:2px solid #228be6} QToolButton{min-width:28px;min-height:28px;border:1px solid #69727d;border-radius:3px} QToolButton:checked{background:#228be6;color:white;border-color:#74c0fc}"
DARK_STYLESHEET = "QMainWindow,QWidget{background:#15191f;color:#e7edf3} QLineEdit,QComboBox,QSpinBox,QPlainTextEdit,QTableWidget,QListWidget{background:#252b33;border:1px solid #46505c;padding:4px} QPushButton{background:#252b33;border:1px solid #46505c;border-radius:4px;padding:6px} QPushButton:hover{border-color:#4dabf7} QPushButton:disabled{color:#69727d} QGroupBox{border:1px solid #343b45;margin-top:8px;padding-top:8px}" + TX_RX_STYLESHEET
LIGHT_STYLESHEET = "QMainWindow,QWidget{background:#f4f6f8;color:#18202a} QLineEdit,QComboBox,QSpinBox,QPlainTextEdit,QTableWidget,QListWidget{background:#ffffff;border:1px solid #aeb7c2;padding:4px} QPushButton{background:#ffffff;border:1px solid #aeb7c2;border-radius:4px;padding:6px} QPushButton:hover{border-color:#1971c2} QPushButton:disabled{color:#8a939d} QGroupBox{border:1px solid #cbd1d8;margin-top:8px;padding-top:8px}" + TX_RX_STYLESHEET


def _compact_controls(root):
    """Apply one consistent sizing policy without constraining data views."""
    spin_boxes = root.findChildren(QtWidgets.QSpinBox) + root.findChildren(QtWidgets.QDoubleSpinBox)
    for widget in spin_boxes:
        widget.setMaximumWidth(140)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
    for widget in root.findChildren(QtWidgets.QComboBox):
        widget.setMaximumWidth(220)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
    for widget in root.findChildren(QtWidgets.QLineEdit):
        widget.setMaximumWidth(260)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
    for widget in root.findChildren(QtWidgets.QPushButton):
        widget.setMinimumWidth(90)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
    for widget in root.findChildren(QtWidgets.QProgressBar):
        widget.setMinimumWidth(250)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
    for layout in root.findChildren(QtWidgets.QFormLayout):
        layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldsStayAtSizeHint)


def _expanding_field(widget, minimum=280):
    widget.setMinimumWidth(minimum); widget.setMaximumWidth(16777215)
    widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)


def _style_plot(plot, theme):
    if theme == "dark":
        background, foreground = "#15191f", "#e7edf3"
    elif theme == "light":
        background, foreground = "#ffffff", "#18202a"
    else:
        palette = QtWidgets.QApplication.palette()
        background = palette.color(QtGui.QPalette.Base)
        foreground = palette.color(QtGui.QPalette.Text)
    plot.setBackground(background)
    plot_item = plot.getPlotItem()
    for name in ("left", "right", "top", "bottom"):
        axis = plot_item.getAxis(name)
        axis.setPen(foreground); axis.setTextPen(foreground)


def _error_text(traceback_text: str) -> str:
    lines = traceback_text.strip().splitlines()
    return lines[-1] if lines else traceback_text


class AsyncMixin:
    pool: QtCore.QThreadPool

    def run_task(self, function, done=None, *, busy=None):
        task = Task(function)
        # Keep the Python worker and its signal object alive until queued GUI
        # callbacks have been delivered. QThreadPool retains only the C++
        # QRunnable; without this reference fast tasks can lose their result.
        if not hasattr(self, "_active_tasks"):
            self._active_tasks = set()
        self._active_tasks.add(task)
        if done:
            task.signals.result.connect(done)
        def show_error(text):
            logger.error("Background operation failed\n%s", text.rstrip())
            QtWidgets.QMessageBox.critical(self, "Operation failed", _error_text(text))
        task.signals.error.connect(show_error)
        if busy:
            busy(False)
            task.signals.finished.connect(lambda: busy(True))
        task.signals.finished.connect(lambda worker=task: self._active_tasks.discard(worker))
        self.pool.start(task)
        return task


class TxRxConfigCard(QtWidgets.QFrame):
    selected = QtCore.Signal(int)
    edit_requested = QtCore.Signal(int)

    def __init__(self, index, tx_mask, rx_mask):
        super().__init__(); self.index = index; self.tx_mask = tx_mask; self.rx_mask = rx_mask
        self.setObjectName("configCard"); self.setCursor(QtCore.Qt.PointingHandCursor)
        self.title = QtWidgets.QLabel(); self.title.setStyleSheet("font-weight:600")
        self.tx_label = QtWidgets.QLabel(); self.rx_label = QtWidgets.QLabel()
        mono = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        self.tx_label.setFont(mono); self.rx_label.setFont(mono)
        layout = QtWidgets.QVBoxLayout(self); layout.setContentsMargins(10, 7, 10, 7); layout.setSpacing(2)
        layout.addWidget(self.title); layout.addWidget(self.tx_label); layout.addWidget(self.rx_label)
        self.refresh(tx_mask, rx_mask)

    @staticmethod
    def _channel_row(name, mask):
        blocks = " ".join("\u25a0" if mask & (1 << channel) else "\u25a1" for channel in range(16))
        return f"{name}  {blocks}"

    def refresh(self, tx_mask, rx_mask):
        self.tx_mask = tx_mask; self.rx_mask = rx_mask
        self.title.setText(f"Config {self.index}")
        self.tx_label.setText(self._channel_row("TX", tx_mask)); self.rx_label.setText(self._channel_row("RX", rx_mask))

    def set_selected(self, selected):
        self.setProperty("selected", selected); self.style().unpolish(self); self.style().polish(self)

    def mousePressEvent(self, event):
        self.selected.emit(self.index); super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.edit_requested.emit(self.index); super().mouseDoubleClickEvent(event)


class TxRxConfigDialog(QtWidgets.QDialog):
    def __init__(self, index, tx_mask, rx_mask, parent=None):
        super().__init__(parent); self.setWindowTitle(f"Edit TX/RX configuration {index}")
        self.tx_buttons = self._channel_buttons(tx_mask); self.rx_buttons = self._channel_buttons(rx_mask)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Select the active transducer channels:"))
        layout.addLayout(self._button_grid("TX", self.tx_buttons)); layout.addLayout(self._button_grid("RX", self.rx_buttons))
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    @staticmethod
    def _channel_buttons(mask):
        result = []
        for channel in range(16):
            button = QtWidgets.QToolButton(); button.setText(str(channel)); button.setCheckable(True)
            button.setChecked(bool(mask & (1 << channel))); result.append(button)
        return result

    @staticmethod
    def _button_grid(label, buttons):
        grid = QtWidgets.QGridLayout(); grid.addWidget(QtWidgets.QLabel(label), 0, 0, 2, 1)
        for channel, button in enumerate(buttons):
            grid.addWidget(button, channel // 8, channel % 8 + 1)
        return grid

    def masks(self):
        def mask(buttons):
            return sum(1 << channel for channel, button in enumerate(buttons) if button.isChecked())
        return mask(self.tx_buttons), mask(self.rx_buttons)


class ConnectionBar(QtWidgets.QWidget, AsyncMixin):
    state_changed = QtCore.Signal()

    def __init__(self, session, pool, parent=None):
        super().__init__(parent)
        self.session, self.pool, self.devices = session, pool, []
        self._scan_generation = 0
        self.transport = QtWidgets.QComboBox()
        self.transport.addItems(session.links)
        self.device = QtWidgets.QComboBox()
        self.scan = QtWidgets.QPushButton("Scan")
        self.connect = QtWidgets.QPushButton("Connect")
        self.disconnect = QtWidgets.QPushButton("Disconnect")
        self.disconnect.setEnabled(False)
        self.status = QtWidgets.QLabel("Disconnected")
        row = QtWidgets.QHBoxLayout(self)
        row.addWidget(QtWidgets.QLabel("Transport")); row.addWidget(self.transport)
        row.addWidget(QtWidgets.QLabel("Device")); row.addWidget(self.device, 1)
        row.addWidget(self.scan); row.addWidget(self.connect); row.addWidget(self.disconnect); row.addWidget(self.status)
        self.transport.currentTextChanged.connect(self.change_transport)
        self.scan.clicked.connect(self.scan_devices)
        self.connect.clicked.connect(self.connect_device)
        self.disconnect.clicked.connect(self.disconnect_device)
        self.scan_devices()

    def change_transport(self, name):
        if self.session.connected:
            self.transport.blockSignals(True)
            self.transport.setCurrentText(self.session.transport)
            self.transport.blockSignals(False)
            return
        self.session.select_transport(name)
        self.scan_devices()
        self.state_changed.emit()

    def scan_devices(self):
        if self.session.connected:
            return
        self._scan_generation += 1
        generation = self._scan_generation
        self.device.clear(); self.devices = []
        self.connect.setEnabled(False)
        self.run_task(self.session.scan, lambda devices: self._scanned(generation, devices))

    def _scanned(self, generation, devices):
        if generation != self._scan_generation or self.session.connected:
            return
        self.devices = list(devices)
        self.device.addItems([str(item) for item in self.devices])
        self.connect.setEnabled(bool(self.devices))

    def connect_device(self):
        if self.session.connected:
            return
        if self.device.currentIndex() < 0:
            return
        selected = self.devices[self.device.currentIndex()]
        self.run_task(lambda: self.session.connect(selected), self._connected, busy=self.connect.setEnabled)

    def disconnect_device(self):
        if not self.session.connected:
            self.reflect_session()
            return
        self.status.setText("Disconnecting…")
        self.disconnect.setEnabled(False)
        task = self.run_task(self.session.disconnect, self._disconnected)
        task.signals.error.connect(self._disconnect_failed)

    def _connected(self, _):
        self.status.setText(f"Connected via {self.session.transport}")
        self.connect.setEnabled(False)
        self.disconnect.setEnabled(True)
        self.transport.setEnabled(False); self.device.setEnabled(False); self.scan.setEnabled(False)
        self.state_changed.emit()

    def _disconnected(self, _):
        self.status.setText("Disconnected")
        self.connect.setEnabled(bool(self.devices))
        self.disconnect.setEnabled(False)
        self.transport.setEnabled(True)
        self.device.setEnabled(True)
        self.scan.setEnabled(True)
        self.state_changed.emit()

    def _disconnect_failed(self, _traceback_text):
        self.status.setText(f"Connected via {self.session.transport}")
        self.connect.setEnabled(False)
        self.disconnect.setEnabled(True)

    def reflect_session(self):
        """Synchronize controls after another tab deliberately closes a link."""
        if not self.session.connected:
            self.status.setText("Disconnected")
            self.connect.setEnabled(bool(self.devices))
            self.disconnect.setEnabled(False)
            self.transport.setEnabled(True)
            self.device.setEnabled(True)
            self.scan.setEnabled(True)
            self.state_changed.emit()


class ConfigEditor(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.inputs = {}
        defaults = config_values(build_config({}))
        root = QtWidgets.QVBoxLayout(self)
        buttons = QtWidgets.QHBoxLayout()
        load = QtWidgets.QPushButton("Load JSON"); save = QtWidgets.QPushButton("Save JSON")
        load.clicked.connect(self.load_json); save.clicked.connect(self.save_json)
        buttons.addWidget(load); buttons.addWidget(save); buttons.addStretch()
        root.addLayout(buttons)
        split = QtWidgets.QSplitter()
        root.addWidget(split, 1)
        parameters = QtWidgets.QWidget(); form = QtWidgets.QFormLayout(parameters)
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
                        minimum = int(param.min_val / us_to_ticks[param.config_name] + 1)
                        maximum = int(param.max_val / us_to_ticks[param.config_name] + 1)
                    except KeyError:
                        minimum, maximum = int(param.min_val), int(param.max_val)
                    widget.setRange(minimum, maximum); widget.setValue(int(value))
                self.inputs[param.config_name] = widget
                form.addRow(param.friendly_name, widget)
        self.tx_masks = [0xffff] + [0] * 15; self.rx_masks = [0xffff] + [0] * 15
        self.cards = {}; self.selected_config = 0
        self.inputs["num_txrx_configs"].valueChanged.connect(self._mask_count)
        mask_box = QtWidgets.QWidget(); mask_layout = QtWidgets.QVBoxLayout(mask_box)
        mask_layout.addWidget(QtWidgets.QLabel("TX/RX configurations (channels 0–15)"))
        scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget(); self.card_layout = QtWidgets.QVBoxLayout(content)
        self.card_layout.setContentsMargins(2, 2, 2, 2); self.card_layout.addStretch(); scroll.setWidget(content)
        mask_layout.addWidget(scroll, 1)
        card_buttons = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("+ Add"); edit = QtWidgets.QPushButton("Edit"); remove = QtWidgets.QPushButton("− Remove")
        add.clicked.connect(self.add_config); edit.clicked.connect(self.edit_config); remove.clicked.connect(self.remove_config)
        card_buttons.addWidget(add); card_buttons.addWidget(edit); card_buttons.addWidget(remove); card_buttons.addStretch(); mask_layout.addLayout(card_buttons)
        file_buttons = QtWidgets.QHBoxLayout()
        load_tx_rx = QtWidgets.QPushButton("Load TX/RX…"); save_tx_rx = QtWidgets.QPushButton("Save TX/RX…")
        load_tx_rx.clicked.connect(self.load_tx_rx); save_tx_rx.clicked.connect(self.save_tx_rx)
        file_buttons.addWidget(load_tx_rx); file_buttons.addWidget(save_tx_rx); file_buttons.addStretch(); mask_layout.addLayout(file_buttons)
        parameters.setMinimumWidth(420); mask_box.setMinimumWidth(520)
        split.addWidget(parameters); split.addWidget(mask_box); split.setCollapsible(0, False); split.setCollapsible(1, False)
        split.setStretchFactor(0, 4); split.setStretchFactor(1, 5); split.setSizes([520, 650])
        self._mask_count(defaults["num_txrx_configs"])

    def _mask_count(self, count):
        for card in self.cards.values():
            self.card_layout.removeWidget(card); card.deleteLater()
        self.cards = {}
        for index in range(count):
            card = TxRxConfigCard(index, self.tx_masks[index], self.rx_masks[index])
            card.selected.connect(self.select_config); card.edit_requested.connect(self.edit_config)
            self.cards[index] = card; self.card_layout.insertWidget(self.card_layout.count() - 1, card)
        self.select_config(min(self.selected_config, count - 1))

    def select_config(self, index):
        self.selected_config = index
        for card_index, card in self.cards.items(): card.set_selected(card_index == index)

    def edit_config(self, index=None):
        index = self.selected_config if index is None or isinstance(index, bool) else index
        dialog = TxRxConfigDialog(index, self.tx_masks[index], self.rx_masks[index], self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.tx_masks[index], self.rx_masks[index] = dialog.masks()
            self.cards[index].refresh(self.tx_masks[index], self.rx_masks[index])

    def add_config(self):
        count = self.inputs["num_txrx_configs"].value()
        if count < 16:
            self.inputs["num_txrx_configs"].setValue(count + 1); self.select_config(count)

    def remove_config(self):
        count = self.inputs["num_txrx_configs"].value()
        if count <= 1: return
        index = self.selected_config
        self.tx_masks[index:count - 1] = self.tx_masks[index + 1:count]
        self.rx_masks[index:count - 1] = self.rx_masks[index + 1:count]
        self.tx_masks[count - 1] = 0; self.rx_masks[count - 1] = 0
        self.inputs["num_txrx_configs"].setValue(count - 1)

    @staticmethod
    def _channels(mask):
        return [channel for channel in range(16) if mask & (1 << channel)]

    def save_tx_rx(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save TX/RX configurations", "tx_rx_configs.json", "JSON (*.json)"
        )
        if not path: return
        count = self.inputs["num_txrx_configs"].value()
        data = {"configs": [
            {"config_id": index, "tx_channels": self._channels(self.tx_masks[index]),
             "rx_channels": self._channels(self.rx_masks[index]), "optimized_switching": False}
            for index in range(count)
        ]}
        try:
            Path(path).write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        except OSError as error:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(error))

    def load_tx_rx(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load TX/RX configurations", "", "JSON (*.json)"
        )
        if not path: return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            entries = data.get("configs")
            if not isinstance(entries, list) or not 1 <= len(entries) <= 16:
                raise ValueError("The file must contain between 1 and 16 TX/RX configurations")
            masks = []
            for index, entry in enumerate(entries):
                if not isinstance(entry, dict): raise ValueError(f"Configuration {index} is invalid")
                config_id = int(entry.get("config_id", index))
                if config_id != index:
                    raise ValueError("Configuration IDs must be contiguous and start at 0")
                tx = {int(channel) for channel in entry["tx_channels"]}
                rx = {int(channel) for channel in entry["rx_channels"]}
                if not tx.issubset(range(16)) or not rx.issubset(range(16)):
                    raise ValueError(f"Configuration {index} contains a channel outside 0–15")
                masks.append((sum(1 << channel for channel in tx), sum(1 << channel for channel in rx)))
            for index, (tx_mask, rx_mask) in enumerate(masks):
                self.tx_masks[index] = tx_mask; self.rx_masks[index] = rx_mask
            self.inputs["num_txrx_configs"].setValue(len(masks)); self._mask_count(len(masks))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            QtWidgets.QMessageBox.critical(self, "Load failed", str(error))

    def values(self):
        data = {}
        for key, widget in self.inputs.items():
            data[key] = widget.currentData() if isinstance(widget, QtWidgets.QComboBox) else widget.value()
        count = data["num_txrx_configs"]
        data["tx_configs"] = self.tx_masks[:count]; data["rx_configs"] = self.rx_masks[:count]
        return data

    def config(self):
        return build_config(self.values())

    def set_config(self, config):
        values = config_values(config)
        for key, widget in self.inputs.items():
            if isinstance(widget, QtWidgets.QComboBox): widget.setCurrentIndex(widget.findData(values[key]))
            else: widget.setValue(values[key])
        for i, value in enumerate(values["tx_configs"]): self.tx_masks[i] = int(value)
        for i, value in enumerate(values["rx_configs"]): self.rx_masks[i] = int(value)
        self._mask_count(values["num_txrx_configs"])

    def load_json(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load configuration", "", "JSON (*.json)")
        if path:
            try: self.set_config(load_config(path))
            except Exception as error: QtWidgets.QMessageBox.critical(self, "Invalid configuration", str(error))

    def save_json(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save configuration", "uss_config.json", "JSON (*.json)")
        if path:
            try: save_config(path, self.config())
            except Exception as error: QtWidgets.QMessageBox.critical(self, "Invalid configuration", str(error))


class AcquisitionTab(QtWidgets.QWidget, AsyncMixin):
    running_changed = QtCore.Signal(bool)
    session_changed = QtCore.Signal()

    def __init__(self, session, config_editor):
        super().__init__(); self.session = session; self.pool = QtCore.QThreadPool.globalInstance(); self.thread = self.worker = None; self.result = None
        self.pending_device_action = None
        self.editor = config_editor
        self.mode = QtWidgets.QComboBox(); self.mode.addItems(["Off", "A-mode", "B-mode"])
        self.fps = QtWidgets.QSpinBox(); self.fps.setRange(1, 60); self.fps.setValue(20)
        self.raw = QtWidgets.QCheckBox("Raw"); self.raw.setChecked(True)
        self.filtered = QtWidgets.QCheckBox("Filtered")
        self.envelope = QtWidgets.QCheckBox("Envelope")
        self.gain = QtWidgets.QCheckBox("Gain curve"); self.gain.setChecked(True)
        self.config_choice = QtWidgets.QComboBox(); self.config_choice.addItem("0")
        self.low_cutoff = QtWidgets.QDoubleSpinBox(); self.low_cutoff.setRange(.01, 3.9); self.low_cutoff.setValue(.4); self.low_cutoff.setSuffix(" MHz")
        self.high_cutoff = QtWidgets.QDoubleSpinBox(); self.high_cutoff.setRange(.02, 3.99); self.high_cutoff.setValue(3.6); self.high_cutoff.setSuffix(" MHz")
        self.pause = QtWidgets.QPushButton("Pause display"); self.pause.setCheckable(True)
        self.autoscale = QtWidgets.QCheckBox("Autoscale"); self.autoscale.setChecked(False)
        self.output = QtWidgets.QLineEdit(); browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self.browse_output)
        self.start = QtWidgets.QPushButton("Start"); self.stop = QtWidgets.QPushButton("Stop"); self.stop.setEnabled(False)
        self.reboot = QtWidgets.QPushButton("Reboot device"); self.reboot.setEnabled(False)
        self.reset_msp = QtWidgets.QPushButton("Reset MSP430"); self.reset_msp.setEnabled(False)
        self.device_actions_group = QtWidgets.QGroupBox("Device controls")
        device_actions = QtWidgets.QHBoxLayout(self.device_actions_group)
        device_actions.setContentsMargins(8, 8, 8, 6)
        device_actions.addWidget(self.reboot); device_actions.addWidget(self.reset_msp)
        self.progress = QtWidgets.QProgressBar(); self.counters = QtWidgets.QLabel("Frames 0 · gaps 0")
        controls = QtWidgets.QHBoxLayout(); controls.addWidget(QtWidgets.QLabel("Display")); controls.addWidget(self.mode)
        controls.addWidget(QtWidgets.QLabel("Max FPS")); controls.addWidget(self.fps)
        controls.addWidget(QtWidgets.QLabel("Save NPZ")); controls.addWidget(self.output, 1); controls.addWidget(browse)
        controls.addWidget(self.start); controls.addWidget(self.stop); controls.addSpacing(12); controls.addWidget(self.device_actions_group)
        display_controls = QtWidgets.QHBoxLayout()
        for widget in (self.raw, self.filtered, self.envelope, self.gain): display_controls.addWidget(widget)
        display_controls.addWidget(QtWidgets.QLabel("TX/RX config")); display_controls.addWidget(self.config_choice)
        display_controls.addWidget(QtWidgets.QLabel("Band-pass")); display_controls.addWidget(self.low_cutoff); display_controls.addWidget(self.high_cutoff)
        display_controls.addStretch(); display_controls.addWidget(self.autoscale); display_controls.addWidget(self.pause)
        self.plot = pg.PlotWidget(); self.plot.showGrid(x=True, y=True, alpha=.25); self.plot.setTitle("A-mode data")
        self.plot.setLabel("bottom", "Samples"); self.plot.setLabel("left", "ADC digital code")
        self.plot_item = self.plot.getPlotItem(); self.plot_item.showAxis("right"); self.plot_item.setLabel("right", "Gain", units="dB")
        self.gain_view = pg.ViewBox(); self.plot_item.scene().addItem(self.gain_view); self.plot_item.getAxis("right").linkToView(self.gain_view); self.gain_view.setXLink(self.plot_item)
        def sync_gain_view(): self.gain_view.setGeometry(self.plot_item.vb.sceneBoundingRect())
        self.plot_item.vb.sigResized.connect(sync_gain_view); sync_gain_view()
        self.raw_curve = self.plot.plot(pen=pg.mkPen("#4dabf7", width=2), name="Raw data")
        self.filtered_curve = self.plot.plot(pen=pg.mkPen("#51cf66", width=3), name="Filtered data")
        self.envelope_curve = self.plot.plot(pen=pg.mkPen("#ff6b6b", width=3), name="Envelope")
        self.gain_curve = pg.PlotCurveItem(pen=pg.mkPen("#adb5bd", width=2, style=QtCore.Qt.DashLine), name="Gain curve"); self.gain_view.addItem(self.gain_curve)
        legend = self.plot.addLegend(); legend.addItem(self.gain_curve, "Gain curve"); self.image = pg.ImageItem(axisOrder="col-major", autoDownsample=False); self.plot.addItem(self.image); self.image.hide()
        self.bmode = None; self.bmode_separators = []; self.last_draw = QtCore.QElapsedTimer(); self.last_draw.start()
        layout = QtWidgets.QVBoxLayout(self); layout.addLayout(controls); layout.addLayout(display_controls); layout.addWidget(self.progress); layout.addWidget(self.counters); layout.addWidget(self.plot, 1)
        self.start.clicked.connect(self.start_acquisition); self.stop.clicked.connect(self.stop_acquisition)
        self.reboot.clicked.connect(self.reboot_device)
        self.reset_msp.clicked.connect(self.reset_msp_device)
        self.mode.currentTextChanged.connect(self.change_mode); self.pause.toggled.connect(lambda value: self.pause.setText("Resume display" if value else "Pause display"))
        self.gain.toggled.connect(self.gain_curve.setVisible)
        self.mode.currentTextChanged.connect(self.update_worker_display); self.fps.valueChanged.connect(self.update_worker_display)
        self.change_mode(self.mode.currentText())

    def set_device_actions_available(self, reboot, reset_msp):
        pending = self.pending_device_action is not None
        self.reboot.setEnabled(bool(reboot) and not pending)
        self.reset_msp.setEnabled(bool(reset_msp) and not pending)

    def reboot_device(self):
        if QtWidgets.QMessageBox.question(
            self, "Reboot device", "Reboot the connected device and disconnect?"
        ) != QtWidgets.QMessageBox.Yes:
            return
        self.run_or_queue_device_action("reboot")

    def reset_msp_device(self):
        if QtWidgets.QMessageBox.question(
            self, "Reset MSP430", "Reset the MSP430 now?"
        ) != QtWidgets.QMessageBox.Yes:
            return
        self.run_or_queue_device_action("reset_msp")

    def run_or_queue_device_action(self, action):
        if self.worker is not None:
            self.pending_device_action = action
            self.reboot.setEnabled(False); self.reset_msp.setEnabled(False)
            self.counters.setText("Stopping acquisition before device command…")
            self.worker.stop(); self.stop.setEnabled(False)
            return
        operation = self.session.reboot if action == "reboot" else self.session.reset_msp
        task = self.run_task(operation)
        if action == "reboot": task.signals.finished.connect(self.session_changed.emit)
        task.signals.finished.connect(
            lambda: self.set_device_actions_available(
                self.session.connected and self.session.capabilities.reset_device,
                self.session.connected and self.session.capabilities.reset_msp,
            )
        )

    def browse_output(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save acquisition", "acquisition.npz", "NumPy (*.npz)")
        if path: self.output.setText(path)

    def start_acquisition(self):
        try: config = self.editor.config(); self.session.require("acquisition")
        except Exception as error: QtWidgets.QMessageBox.critical(self, "Cannot start", str(error)); return
        self.progress.setRange(0, config.num_acqs); self.progress.setValue(0); self.bmode = np.zeros((config.num_txrx_configs, config.num_samples))
        # Reapply the selected mode after allocating the image. In particular,
        # never leak B-mode's categorical Y axis into an A-mode acquisition.
        self.change_mode(self.mode.currentText())
        current = self.config_choice.currentText(); self.config_choice.clear(); self.config_choice.addItems([str(i) for i in range(config.num_txrx_configs)]); self.config_choice.setCurrentText(current if current else "0")
        nyquist = config.sampling_freq / 2e6
        self.low_cutoff.setMaximum(max(.01, nyquist - .01)); self.high_cutoff.setMaximum(max(.02, nyquist - .001))
        if self.high_cutoff.value() <= self.low_cutoff.value(): self.high_cutoff.setValue(self.high_cutoff.maximum())
        try:
            config.calc_gain_curve(); self.gain_curve.setData(config.gain_curve_db); self.gain_view.setYRange(config.rx_gain - 20, config.rx_gain + 80, padding=0)
        except Exception:
            self.gain_curve.clear()
        self.gain_curve.setVisible(self.gain.isChecked())
        self.worker = AcquisitionWorker(
            self.session, config, self.mode.currentText(), self.fps.value()
        ); self.thread = QtCore.QThread(self)
        self.worker.moveToThread(self.thread); self.thread.started.connect(self.worker.run)
        self.worker.frame.connect(self.on_frame); self.worker.completed.connect(self.on_complete); self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.thread.quit); self.thread.finished.connect(self.finished)
        self.start.setEnabled(False); self.stop.setEnabled(True); self.running_changed.emit(True); self.thread.start()

    @QtCore.Slot(object, int, int, int, int)
    def on_frame(self, samples, number, config_id, gaps, count):
        self.progress.setValue(count); self.counters.setText(f"Frames {count} · gaps {gaps} · acquisition {number} · config {config_id}")
        mode = self.mode.currentText()
        if samples is None or mode == "Off" or self.pause.isChecked() or self.last_draw.elapsed() < 1000 / self.fps.value(): return
        self.last_draw.restart(); data = np.asarray(samples, dtype=float)
        if mode == "A-mode":
            if config_id != self.config_choice.currentIndex(): return
            filtered = self.filter_data(data)
            self.raw_curve.setData(data); self.raw_curve.setVisible(self.raw.isChecked())
            self.filtered_curve.setData(filtered); self.filtered_curve.setVisible(self.filtered.isChecked())
            self.envelope_curve.setData(np.abs(signal.hilbert(filtered))); self.envelope_curve.setVisible(self.envelope.isChecked())
            if self.autoscale.isChecked(): self.plot.enableAutoRange()
            else: self.plot.setYRange(-3000, 3000, padding=0)
        else:
            if 0 <= config_id < self.bmode.shape[0]: self.bmode[config_id] = np.abs(signal.hilbert(self.filter_data(data)))
            # ImageItem's col-major convention is x first and y second:
            # samples/depth belong on x, discrete TX/RX configurations on y.
            self.image.setImage(self.bmode.T, autoLevels=True)
            config = self.editor.config()
            depth_mm = config.num_samples / config.sampling_freq * 1540 * 1000 / 2
            self.image.setRect(QtCore.QRectF(0, -.5, depth_mm, config.num_txrx_configs))

    def filter_data(self, data):
        config = self.editor.config()
        low, high = self.low_cutoff.value() * 1e6, self.high_cutoff.value() * 1e6
        nyquist = config.sampling_freq / 2
        high = min(high, nyquist * .999)
        if low >= high: return data.copy()
        transition = max(1.0, min(.2e6, low * .5, (nyquist - high) * .5))
        taps = signal.remez(31, [0, low - transition, low, high, high + transition, nyquist], [0, 1, 0], fs=config.sampling_freq, maxiter=2500)
        return signal.filtfilt(taps, 1, data)

    def change_mode(self, mode):
        off, bmode = mode == "Off", mode == "B-mode"
        self.plot.setVisible(not off)
        self.image.setVisible(bmode and not off)
        for curve in (self.raw_curve, self.filtered_curve, self.envelope_curve): curve.setVisible(not off and not bmode)
        self.gain_curve.setVisible(not off and not bmode and self.gain.isChecked()); self.plot_item.getAxis("right").setVisible(not off and not bmode)
        self.plot.setTitle("B-mode data" if bmode else "A-mode data")
        self.plot.setLabel("bottom", "Depth (mm)" if bmode else "Samples")
        self.plot.setLabel("left", "TX/RX configuration" if bmode else "ADC digital code")
        if bmode:
            self.configure_bmode_axis(self.editor.inputs["num_txrx_configs"].value())
        else:
            for separator in self.bmode_separators: self.plot.removeItem(separator)
            self.bmode_separators = []
            self.plot.getAxis("left").setTicks(None)
            self.plot.getViewBox().setLimits(yMin=None, yMax=None)
            self.plot.getViewBox().setMouseEnabled(x=True, y=True)
            self.plot.enableAutoRange(axis="y")

    def configure_bmode_axis(self, count):
        for separator in self.bmode_separators: self.plot.removeItem(separator)
        self.bmode_separators = []
        ticks = [(index, f"Config {index}") for index in range(count)]
        self.plot.getAxis("left").setTicks([ticks])
        self.plot.getViewBox().setLimits(yMin=-.5, yMax=count - .5)
        self.plot.getViewBox().setMouseEnabled(x=True, y=False)
        self.plot.setYRange(-.5, count - .5, padding=0)
        for boundary in range(1, count):
            separator = pg.InfiniteLine(boundary - .5, angle=0, pen=pg.mkPen("#69727d", width=1))
            separator.setZValue(10); self.plot.addItem(separator); self.bmode_separators.append(separator)

    def update_worker_display(self, *_):
        if self.worker is not None:
            self.worker.set_display(self.mode.currentText(), self.fps.value())

    def on_complete(self, result):
        self.result = result
        self.progress.setValue(len(result.frames))
        self.counters.setText(f"Frames {len(result.frames)} · gaps {result.frame_gaps} · {'complete' if result.completed else 'stopped'}")
        if self.output.text().strip():
            try: save_npz(self.output.text().strip(), result)
            except Exception as error: QtWidgets.QMessageBox.critical(self, "Save failed", str(error))

    def on_error(self, text):
        QtWidgets.QMessageBox.critical(self, "Acquisition failed", _error_text(text))

    def stop_acquisition(self):
        if self.worker: self.worker.stop(); self.stop.setEnabled(False)

    def finished(self):
        self.start.setEnabled(True); self.stop.setEnabled(False); self.running_changed.emit(False)
        if self.worker: self.worker.deleteLater()
        if self.thread: self.thread.deleteLater()
        self.worker = self.thread = None
        pending, self.pending_device_action = self.pending_device_action, None
        if pending is not None:
            QtCore.QTimer.singleShot(0, lambda action=pending: self.run_or_queue_device_action(action))


class NpzViewerTab(QtWidgets.QWidget):
    REQUIRED_ARRAYS = ("data_arr", "acq_num_arr", "tx_rx_id_arr")

    def __init__(self):
        super().__init__()
        self.data_arr = np.empty((0, 0)); self.acq_num_arr = np.empty(0); self.tx_rx_id_arr = np.empty(0)
        self.filtered_indices = np.empty(0, dtype=np.intp)
        self.replay_range = None
        self.path = QtWidgets.QLineEdit(); self.path.setPlaceholderText("Select a notebook-compatible .npz acquisition")
        browse = QtWidgets.QPushButton("Browse…"); load = QtWidgets.QPushButton("Load")
        browse.clicked.connect(self.browse); load.clicked.connect(lambda: self.load(self.path.text()))
        file_row = QtWidgets.QHBoxLayout(); file_row.addWidget(self.path, 1); file_row.addWidget(browse); file_row.addWidget(load)
        self.info = QtWidgets.QLabel("No acquisition file loaded")
        self.config = QtWidgets.QComboBox(); self.config.setEnabled(False)
        self.position = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.position.setEnabled(False); self.position.setRange(0, 0)
        self.position_label = QtWidgets.QLabel("Acquisition 0 of 0")
        self.sampling = QtWidgets.QDoubleSpinBox(); self.sampling.setRange(.5, 100); self.sampling.setValue(8); self.sampling.setSuffix(" MHz")
        self.low = QtWidgets.QDoubleSpinBox(); self.low.setRange(.01, 49.8); self.low.setValue(.4); self.low.setSuffix(" MHz")
        self.high = QtWidgets.QDoubleSpinBox(); self.high.setRange(.02, 49.9); self.high.setValue(3.6); self.high.setSuffix(" MHz")
        self.raw = QtWidgets.QCheckBox("Raw"); self.raw.setChecked(True)
        self.filtered = QtWidgets.QCheckBox("Filtered"); self.envelope = QtWidgets.QCheckBox("Envelope")
        self.replay_fps = QtWidgets.QDoubleSpinBox(); self.replay_fps.setRange(.1, 500); self.replay_fps.setValue(20); self.replay_fps.setSuffix(" FPS")
        self.replay = QtWidgets.QPushButton("Replay"); self.stop = QtWidgets.QPushButton("Stop"); self.stop.setEnabled(False)
        selectors = QtWidgets.QHBoxLayout(); selectors.addWidget(QtWidgets.QLabel("TX/RX config")); selectors.addWidget(self.config)
        selectors.addWidget(self.position_label); selectors.addWidget(self.position, 1)
        processing = QtWidgets.QHBoxLayout()
        for widget in (self.raw, self.filtered, self.envelope, QtWidgets.QLabel("Sampling"), self.sampling,
                       QtWidgets.QLabel("Band-pass"), self.low, self.high): processing.addWidget(widget)
        processing.addStretch(); processing.addWidget(self.replay_fps); processing.addWidget(self.replay); processing.addWidget(self.stop)
        self.plot = pg.PlotWidget(); self.plot.showGrid(x=True, y=True, alpha=.25); self.plot.setLabel("bottom", "Samples"); self.plot.setLabel("left", "ADC digital code")
        self.raw_curve = self.plot.plot(pen=pg.mkPen("#4dabf7", width=2), name="Raw")
        self.filtered_curve = self.plot.plot(pen=pg.mkPen("#51cf66", width=3), name="Filtered")
        self.envelope_curve = self.plot.plot(pen=pg.mkPen("#ff6b6b", width=3), name="Envelope"); self.plot.addLegend()
        layout = QtWidgets.QVBoxLayout(self); layout.addLayout(file_row); layout.addWidget(self.info); layout.addLayout(selectors); layout.addLayout(processing); layout.addWidget(self.plot, 1)
        self.timer = QtCore.QTimer(self); self.timer.timeout.connect(self.next_frame)
        self.config.currentIndexChanged.connect(self.update_filter); self.position.valueChanged.connect(self.update_plot)
        for widget in (self.raw, self.filtered, self.envelope): widget.toggled.connect(self.update_plot)
        for widget in (self.sampling, self.low, self.high): widget.valueChanged.connect(self.signal_controls_changed)
        self.replay.clicked.connect(self.start_replay); self.stop.clicked.connect(self.stop_replay)

    @classmethod
    def read_npz(cls, path):
        with np.load(path, allow_pickle=False) as archive:
            missing = [name for name in cls.REQUIRED_ARRAYS if name not in archive]
            if missing: raise ValueError(f"Missing required NPZ arrays: {', '.join(missing)}")
            data = np.asarray(archive["data_arr"]); numbers = np.asarray(archive["acq_num_arr"]); configs = np.asarray(archive["tx_rx_id_arr"])
        if data.ndim != 2: raise ValueError("data_arr must be a two-dimensional samples-by-frames array")
        if numbers.ndim != 1 or configs.ndim != 1: raise ValueError("Metadata arrays must be one-dimensional")
        if data.shape[1] != len(numbers) or len(numbers) != len(configs):
            raise ValueError("Metadata lengths must match the number of data_arr columns")
        return data, numbers, configs

    def browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open acquisition", "", "NumPy (*.npz)")
        if path: self.load(path)

    def load(self, path):
        if not path: return
        try: data, numbers, configs = self.read_npz(path)
        except (OSError, ValueError) as error:
            QtWidgets.QMessageBox.critical(self, "Could not load acquisition", str(error)); return
        self.stop_replay(); self.path.setText(str(path)); self.data_arr = data; self.acq_num_arr = numbers; self.tx_rx_id_arr = configs
        unique, counts = np.unique(configs, return_counts=True)
        self.config.blockSignals(True); self.config.clear(); self.config.addItem(f"All configurations ({len(configs)} frames)", None)
        for config_id, count in zip(unique, counts): self.config.addItem(f"Config {int(config_id)} ({int(count)} frames)", int(config_id))
        self.config.blockSignals(False); self.config.setEnabled(bool(len(configs)))
        self.info.setText(f"{Path(path).name} — {data.shape[1]} frames, {data.shape[0]} samples/frame, {len(unique)} configurations")
        logger.debug("Loaded data file %s: %d frames, %d samples/frame, %d configurations", path, data.shape[1], data.shape[0], len(unique))
        self.update_filter()

    def update_filter(self, *_):
        selected = self.config.currentData()
        self.filtered_indices = np.arange(self.data_arr.shape[1], dtype=np.intp) if selected is None else np.flatnonzero(self.tx_rx_id_arr == selected)
        count = len(self.filtered_indices); self.position.setEnabled(bool(count)); self.position.setRange(0, max(0, count - 1)); self.position.setValue(0)
        self.update_plot()

    def filter_data(self, samples):
        sampling_hz = self.sampling.value() * 1e6; nyquist = sampling_hz / 2
        low = self.low.value() * 1e6; high = min(self.high.value() * 1e6, nyquist * .999)
        if low >= high: raise ValueError("Band-pass low cutoff must be below the high cutoff")
        transition = max(1.0, min(.2e6, low * .5, (nyquist - high) * .5))
        taps = signal.remez(31, [0, low - transition, low, high, high + transition, nyquist], [0, 1, 0], fs=sampling_hz, maxiter=2500)
        return signal.filtfilt(taps, 1, samples)

    def update_plot(self, *_):
        if not len(self.filtered_indices):
            for curve in (self.raw_curve, self.filtered_curve, self.envelope_curve): curve.clear()
            self.position_label.setText("Acquisition 0 of 0"); return
        frame = int(self.filtered_indices[self.position.value()]); samples = np.asarray(self.data_arr[:, frame], dtype=float)
        filtered = envelope = None
        if self.filtered.isChecked() or self.envelope.isChecked():
            try: filtered = self.filter_data(samples); envelope = np.abs(signal.hilbert(filtered))
            except ValueError as error: self.info.setText(f"Signal processing failed: {error}")
        self.raw_curve.setData(samples if self.raw.isChecked() else [])
        self.filtered_curve.setData(filtered if filtered is not None and self.filtered.isChecked() else [])
        self.envelope_curve.setData(envelope if envelope is not None and self.envelope.isChecked() else [])
        self.position_label.setText(f"Acquisition {self.position.value() + 1} of {len(self.filtered_indices)}")
        self.plot.setTitle(f"Frame {frame} · acquisition {int(self.acq_num_arr[frame])} · TX/RX config {int(self.tx_rx_id_arr[frame])}")
        if self.replay_range is None:
            self.plot.enableAutoRange()
        else:
            x_range, y_range = self.replay_range
            self.plot.setXRange(*x_range, padding=0); self.plot.setYRange(*y_range, padding=0)

    def signal_controls_changed(self, *_):
        maximum = max(.02, self.sampling.value() / 2 - .01)
        self.low.setMaximum(maximum); self.high.setMaximum(maximum)
        if self.high.value() <= self.low.value(): self.high.setValue(min(maximum, self.low.value() + .1))
        self.update_plot()

    def start_replay(self):
        if not len(self.filtered_indices): return
        self.plot.getViewBox().autoRange()
        self.replay_range = [list(axis_range) for axis_range in self.plot.viewRange()]
        self.plot.disableAutoRange()
        self.timer.setInterval(max(1, round(1000 / self.replay_fps.value()))); self.timer.start(); self.replay.setEnabled(False); self.stop.setEnabled(True)

    def next_frame(self):
        if self.position.value() >= self.position.maximum(): self.stop_replay(); return
        self.position.setValue(self.position.value() + 1)

    def stop_replay(self):
        was_replaying = self.timer.isActive() or self.replay_range is not None
        self.timer.stop(); self.replay_range = None; self.replay.setEnabled(True); self.stop.setEnabled(False)
        if was_replaying: self.update_plot()

class DeviceConfigTab(QtWidgets.QWidget, AsyncMixin):
    def __init__(self, session, pool):
        super().__init__(); self.session, self.pool = session, pool
        self.wifi_boot = QtWidgets.QCheckBox("Enable Wi-Fi at boot")
        self.auto = QtWidgets.QCheckBox("Automatic provisioning")
        self.power = QtWidgets.QComboBox()
        for item in WulpusProWiFiPowerSave: self.power.addItem(item.name, item)
        self.twt = QtWidgets.QCheckBox("Enable TWT")
        self.ssid = QtWidgets.QLineEdit(); self.password = QtWidgets.QLineEdit(); self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        load = QtWidgets.QPushButton("Load"); save = QtWidgets.QPushButton("Save settings")
        credentials = QtWidgets.QPushButton("Replace credentials"); clear = QtWidgets.QPushButton("Clear credentials"); reboot = QtWidgets.QPushButton("Reboot ESP32")
        self.controls = [load, save, credentials, clear, reboot, self.wifi_boot, self.auto, self.power, self.twt, self.ssid, self.password]
        load.clicked.connect(self.load); save.clicked.connect(self.save); credentials.clicked.connect(self.set_credentials); clear.clicked.connect(self.clear_credentials); reboot.clicked.connect(self.reboot)
        form = QtWidgets.QFormLayout(); form.addRow(self.wifi_boot); form.addRow(self.auto); form.addRow("Power save", self.power); form.addRow(self.twt); form.addRow("New SSID", self.ssid); form.addRow("New password", self.password)
        buttons = QtWidgets.QHBoxLayout(); [buttons.addWidget(x) for x in (load, save, credentials, clear, reboot)]; buttons.addStretch()
        layout = QtWidgets.QVBoxLayout(self); layout.addLayout(form); layout.addLayout(buttons); layout.addStretch()

    def set_available(self, available):
        for control in self.controls: control.setEnabled(available)
        self.setToolTip("" if available else "Persistent provisioning requires a connected USB CDC device")

    def load(self):
        link = self.session.require("device_config")
        def operation(): return link.get_device_config(), link.get_wifi_status()
        def done(value):
            config, status = value; self.wifi_boot.setChecked(config.wifi_enabled_at_boot); self.auto.setChecked(config.auto_provision)
            self.power.setCurrentIndex(self.power.findData(config.wifi_power_save_mode)); self.twt.setChecked(config.twt_enabled)
            QtWidgets.QMessageBox.information(self, "Configuration", f"Loaded. Credentials present: {status.credentials_present}")
        self.run_task(operation, done)

    def save(self):
        link = self.session.require("device_config")
        config = WulpusProDeviceConfig(self.wifi_boot.isChecked(), self.auto.isChecked(), self.power.currentData(), self.twt.isChecked())
        self.run_task(lambda: link.set_device_config(config), lambda _: QtWidgets.QMessageBox.information(self, "Saved", "Settings saved; reboot required."))

    def set_credentials(self):
        link = self.session.require("device_config"); ssid, password = self.ssid.text(), self.password.text(); self.password.clear()
        self.run_task(lambda: link.set_wifi_credentials(ssid, password), lambda _: self.ssid.clear())

    def clear_credentials(self):
        if QtWidgets.QMessageBox.question(self, "Remove credentials", "Remove stored Wi-Fi credentials?") == QtWidgets.QMessageBox.Yes:
            link = self.session.require("device_config"); self.run_task(link.clear_wifi_credentials)

    def reboot(self):
        if QtWidgets.QMessageBox.question(self, "Reboot", "Reboot the ESP32 and disconnect?") == QtWidgets.QMessageBox.Yes:
            link = self.session.require("device_config"); self.run_task(link.reset)


class ServiceTab(QtWidgets.QWidget, AsyncMixin):
    def __init__(self, session, pool):
        super().__init__(); self.session, self.pool = session, pool
        self.summary = QtWidgets.QPlainTextEdit(); self.summary.setReadOnly(True)
        self.errors = QtWidgets.QListWidget()
        refresh = QtWidgets.QPushButton("Refresh"); clear = QtWidgets.QPushButton("Clear selected errors"); reset = QtWidgets.QPushButton("Clear errors + reset counters"); export = QtWidgets.QPushButton("Export event log")
        self.action_controls = [refresh, clear, reset]; refresh.clicked.connect(self.refresh); clear.clicked.connect(self.clear_selected); reset.clicked.connect(self.reset_all); export.clicked.connect(self.export_log)
        top = QtWidgets.QHBoxLayout(); [top.addWidget(x) for x in (refresh, clear, reset, export)]; top.addStretch()
        layout = QtWidgets.QVBoxLayout(self); layout.addLayout(top); layout.addWidget(QtWidgets.QLabel("Sticky errors")); layout.addWidget(self.errors); layout.addWidget(QtWidgets.QLabel("Status and diagnostics")); layout.addWidget(self.summary, 1)

    def set_available(self, available):
        for control in self.action_controls: control.setEnabled(available)

    def refresh(self):
        link = self.session.require("runtime_status")
        def operation():
            result = {"status": link.get_status(), "firmware": link.get_firmware_info()}
            if self.session.capabilities.wifi_status: result["wifi"] = link.get_wifi_status()
            if self.session.capabilities.msp_update:
                try: result["msp_diagnostics"] = MSP430Updater(link).diagnostics()
                except Exception as error: result["msp_diagnostics_error"] = str(error)
            return result
        self.run_task(operation, self._show_status)

    def _show_status(self, result):
        status = result["status"]; self.errors.clear()
        for bit, name in ERROR_NAMES.items():
            if not status.error_flags & bit:
                continue
            item = QtWidgets.QListWidgetItem(name); item.setData(QtCore.Qt.UserRole, bit); item.setCheckState(QtCore.Qt.Checked); self.errors.addItem(item)
        if not status.error_flags: self.errors.addItem("None")
        lines = [f"{field.name}: {getattr(status, field.name)}" for field in fields(status)]
        firmware = result["firmware"]; lines += ["", "Firmware"] + [f"{field.name}: {getattr(firmware, field.name)}" for field in fields(firmware)]
        for key in ("wifi", "msp_diagnostics"):
            if key in result: lines += ["", key.replace('_', ' ').title()] + [f"{field.name}: {getattr(result[key], field.name)}" for field in fields(result[key])]
        if "msp_diagnostics_error" in result: lines += ["", "MSP430 diagnostics unavailable: " + result["msp_diagnostics_error"]]
        self.summary.setPlainText("\n".join(lines)); self.session.log("Service status refreshed")

    def clear_selected(self):
        mask = sum(self.errors.item(i).data(QtCore.Qt.UserRole) or 0 for i in range(self.errors.count()) if self.errors.item(i).checkState() == QtCore.Qt.Checked)
        if mask: self.run_task(lambda: self.session.require("runtime_status").clear_status(error_mask=mask), lambda _: self.refresh())

    def reset_all(self):
        if QtWidgets.QMessageBox.question(self, "Reset counters", "Clear all sticky errors and diagnostic counters?") == QtWidgets.QMessageBox.Yes:
            self.run_task(lambda: self.session.require("runtime_status").clear_status(clear_counters=True), lambda _: self.refresh())

    def export_log(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export event log", "wulpus-events.log", "Log (*.log);;All files (*)")
        if path: Path(path).write_text("\n".join(self.session.events) + "\n", encoding="utf-8")


class FirmwareTab(QtWidgets.QWidget, AsyncMixin):
    session_changed = QtCore.Signal()
    msp_progress_received = QtCore.Signal(object)

    def __init__(self, session, pool):
        super().__init__(); self.session, self.pool, self.esp_package = session, pool, None
        self.msp_image = None
        self.versions = QtWidgets.QLabel("Connect over USB CDC or Wi-Fi to read installed versions")
        self.versions.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.refresh_versions = QtWidgets.QPushButton("Refresh firmware versions")
        self.refresh_versions.clicked.connect(self.load_versions)
        self.esp_path = QtWidgets.QLineEdit(); esp_select = QtWidgets.QPushButton("Select ESP32 ZIP"); self.esp_port = QtWidgets.QComboBox(); esp_ports = QtWidgets.QPushButton("Refresh ports")
        self.esp_port.currentTextChanged.connect(self._flash_enabled)
        self.confirm = QtWidgets.QCheckBox("I will keep USB and board power connected")
        self.flash = QtWidgets.QPushButton("Flash ESP32"); self.flash.setEnabled(False)
        self.msp_path = QtWidgets.QLineEdit(); self.msp_path.setReadOnly(True)
        msp_select = QtWidgets.QPushButton("Select MSP430 ZIP/image"); self.program = QtWidgets.QPushButton("Program MSP430"); self.program.setEnabled(False)
        self.msp_ready = QtWidgets.QLabel("Select and validate an MSP430 firmware package")
        self.msp_progress = QtWidgets.QProgressBar(); self.msp_progress.setRange(0, 100); self.msp_progress.setValue(0)
        self.output = QtWidgets.QPlainTextEdit(); self.output.setReadOnly(True)
        esp_select.clicked.connect(self.select_esp); esp_ports.clicked.connect(self.refresh_ports); self.confirm.toggled.connect(self._flash_enabled); self.flash.clicked.connect(self.flash_esp)
        msp_select.clicked.connect(self.select_msp); self.program.clicked.connect(self.program_msp)
        self.msp_progress_received.connect(self.show_msp_progress)
        installed = QtWidgets.QGroupBox("Installed firmware")
        installed_layout = QtWidgets.QHBoxLayout(installed)
        installed_layout.addWidget(self.versions, 1)
        installed_layout.addWidget(self.refresh_versions)
        esp = QtWidgets.QGroupBox("ESP32-C6"); e = QtWidgets.QGridLayout(esp); e.addWidget(self.esp_path,0,0); e.addWidget(esp_select,0,1); e.addWidget(self.esp_port,1,0); e.addWidget(esp_ports,1,1); e.addWidget(self.confirm,2,0); e.addWidget(self.flash,2,1)
        msp = QtWidgets.QGroupBox("MSP430"); m = QtWidgets.QGridLayout(msp); m.addWidget(self.msp_path,0,0); m.addWidget(msp_select,0,1); m.addWidget(self.msp_ready,1,0); m.addWidget(self.program,1,1); m.addWidget(self.msp_progress,2,0,1,2)
        layout = QtWidgets.QVBoxLayout(self); layout.addWidget(installed); layout.addWidget(esp); layout.addWidget(msp); layout.addWidget(self.output,1); self.refresh_ports()

    def set_available(self, msp_available, idle):
        del msp_available  # Derived from the live session below.
        self.sync_esp_port()
        self._update_msp_enabled(idle)
        self.flash.setEnabled(idle and self.confirm.isChecked() and self.esp_package is not None and self.esp_port.currentIndex() >= 0)
        version_available = (
            self.session.connected
            and self.session.capabilities.firmware_info
            and idle
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
        try:
            link = self.session.require("firmware_info")
        except Exception as error:
            QtWidgets.QMessageBox.critical(self, "Versions unavailable", str(error))
            return
        self.refresh_versions.setEnabled(False)

        def done(info):
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
        def describe(version, git_hash, dirty):
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
        previous = self.esp_port.currentText()
        ports = [port.device for port in list_ports.comports()]
        self.esp_port.blockSignals(True)
        self.esp_port.clear(); self.esp_port.addItems(ports)
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
        if not self.session.connected or self.session.transport != "USB CDC":
            return ""
        device = self.session.device
        return str(getattr(device, "device", "") or "")

    def sync_esp_port(self):
        port = self.active_usb_port()
        if not port:
            return
        index = self.esp_port.findText(port, QtCore.Qt.MatchFixedString)
        if index < 0:
            self.esp_port.addItem(port)
            index = self.esp_port.count() - 1
        self.esp_port.setCurrentIndex(index)

    def select_esp(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "ESP32 release", "", "ZIP (*.zip)")
        if not path: return
        try: self.esp_package = Esp32ReleasePackage.load(path)
        except Exception as error: self.esp_package = None; QtWidgets.QMessageBox.critical(self, "Invalid release", str(error)); return
        self.esp_path.setText(path); self.output.appendPlainText(f"Validated ESP32 release {self.esp_package.version}"); self._flash_enabled()

    def _flash_enabled(self): self.flash.setEnabled(self.confirm.isChecked() and self.esp_package is not None and self.esp_port.currentIndex() >= 0 and not self.session.busy_operation)

    def flash_esp(self):
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
            self.output.appendPlainText("Closing the active USB CDC session before flashing…")
            task = self.run_task(self.session.disconnect, lambda _: self._usb_closed_for_flash(package, port))
            task.signals.error.connect(lambda _: self._flash_enabled())
            return
        self._start_esp_flash(package, port)

    def _usb_closed_for_flash(self, package, port):
        self.session_changed.emit()
        self._start_esp_flash(package, port)

    def _start_esp_flash(self, package, port):
        self.session.busy_operation = "ESP32 update"; self.flash.setEnabled(False)
        messages = []
        def done(_):
            self.output.appendPlainText("".join(messages).rstrip())
            self.output.appendPlainText("ESP32 update complete; reconnect after reboot.")
        task = self.run_task(lambda: flash_package(package, port, messages.append), done)
        task.signals.error.connect(
            lambda _: self.output.appendPlainText("".join(messages).rstrip())
        )
        task.signals.finished.connect(self._update_finished)

    def select_msp(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "MSP430 release", "", "Firmware (*.zip *.mspfw *.txt *.hex);;All files (*)")
        if path:
            try: self.msp_image = load_image(path)
            except Exception as error:
                self.msp_image = None; self.msp_path.clear(); self._update_msp_enabled()
                QtWidgets.QMessageBox.critical(self, "Invalid firmware", str(error)); return
            self.msp_path.setText(path); self.output.appendPlainText("Validated MSP430 firmware"); self._update_msp_enabled()

    def _update_msp_enabled(self, idle=None):
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
        try:
            link = self.session.require("msp_update")
            if self.msp_image is None:
                raise ValueError("Select and validate an MSP430 firmware package")
            image = self.msp_image
        except Exception as error: QtWidgets.QMessageBox.critical(self, "Cannot update", str(error)); return
        self.session.busy_operation = "MSP430 update"; self.program.setEnabled(False); self.msp_progress.setValue(0)
        self.output.appendPlainText(
            f"Starting MSP430 update over {self.session.transport}: "
            f"{len(image)} bytes"
        )
        def operation():
            status = MSP430Updater(link).program(
                image, progress=self.msp_progress_received.emit
            )
            # COMPLETE is reported only after the target has rebooted. Read the
            # ESP32's freshly detected MSP430 version in the same serialized
            # operation so the update tab cannot retain its pre-flash value.
            info = link.get_firmware_info(timeout=5.0)
            return status, info
        def done(value):
            status, info = value
            self.output.appendPlainText(f"MSP430 update: {status.state.name}")
            self.show_versions(info)
            self.session.log(f"MSP430 update {status.state.name}; firmware versions refreshed")
        task = self.run_task(operation, done)
        task.signals.error.connect(
            lambda text: self.output.appendPlainText(
                "MSP430 update failed: " + _error_text(text)
            )
        )
        task.signals.finished.connect(self._update_finished)

    @QtCore.Slot(object)
    def show_msp_progress(self, status):
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
        self.session.busy_operation = None; self._flash_enabled(); self._update_msp_enabled()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, include_simulator=False):
        super().__init__(); self.setWindowTitle(f"{APP_NAME} {APP_VERSION}"); self.resize(1350, 900)
        self.settings = QtCore.QSettings()
        self.debug_handler = None; self.previous_log_level = None
        self.pool = QtCore.QThreadPool.globalInstance(); self.session = SessionController(default_links(include_simulator))
        central = QtWidgets.QWidget(); layout = QtWidgets.QVBoxLayout(central)
        self.connection = ConnectionBar(self.session, self.pool); layout.addWidget(self.connection)
        self.tabs = QtWidgets.QTabWidget(); layout.addWidget(self.tabs, 1)
        self.configuration = ConfigEditor()
        self.acquisition = AcquisitionTab(self.session, self.configuration); self.viewer = NpzViewerTab(); self.device_config = DeviceConfigTab(self.session, self.pool); self.service = ServiceTab(self.session, self.pool); self.firmware = FirmwareTab(self.session, self.pool)
        self.tabs.addTab(self.configuration, "Acquisition Settings"); self.tabs.addTab(self.acquisition, "Acquisition"); self.tabs.addTab(self.viewer, "Data Viewer"); self.tabs.addTab(self.device_config, "Device Configuration"); self.tabs.addTab(self.service, "Service"); self.tabs.addTab(self.firmware, "Firmware Update")
        self.setCentralWidget(central); self.connection.state_changed.connect(self.update_capabilities); self.acquisition.running_changed.connect(self.operation_changed); self.update_capabilities()
        self.acquisition.session_changed.connect(self.connection.reflect_session)
        self.firmware.session_changed.connect(self.connection.reflect_session)
        _compact_controls(self)
        self.connection.transport.setMaximumWidth(170)
        self.connection.device.setMinimumWidth(240); self.connection.device.setMaximumWidth(360)
        for path_field in (self.acquisition.output, self.viewer.path, self.firmware.esp_path, self.firmware.msp_path):
            _expanding_field(path_field)
        self._create_theme_menu()
        self._create_debug_menu()
        self.set_theme(self.settings.value("appearance/theme", "light", type=str))

    def _create_theme_menu(self):
        theme_menu = self.menuBar().addMenu("Appearance").addMenu("Theme")
        self.theme_actions = {}
        group = QtGui.QActionGroup(self); group.setExclusive(True)
        for key, label in (("system", "System default"), ("light", "Light"), ("dark", "Dark")):
            action = theme_menu.addAction(label)
            action.setCheckable(True); action.setData(key); group.addAction(action)
            action.triggered.connect(lambda checked=False, name=key: self.set_theme(name))
            self.theme_actions[key] = action

    def set_theme(self, theme):
        if theme not in self.theme_actions:
            theme = "dark"
        self.setStyleSheet({"system": TX_RX_STYLESHEET, "light": LIGHT_STYLESHEET, "dark": DARK_STYLESHEET}[theme])
        _style_plot(self.acquisition.plot, theme); _style_plot(self.viewer.plot, theme)
        self.theme_actions[theme].setChecked(True)
        self.settings.setValue("appearance/theme", theme)

    def _create_debug_menu(self):
        debug_menu = self.menuBar().addMenu("Debug")
        self.debug_action = debug_menu.addAction("Enable debug logging…")
        self.debug_action.setCheckable(True); self.debug_action.toggled.connect(self.toggle_debug_logging)

    def toggle_debug_logging(self, enabled):
        if enabled:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Write debug log", "wulpus-debug.log", "Log (*.log);;All files (*)"
            )
            if not path:
                self.debug_action.blockSignals(True); self.debug_action.setChecked(False); self.debug_action.blockSignals(False)
                return
            try:
                handler = BatchedFileHandler(path)
            except OSError as error:
                self.debug_action.blockSignals(True); self.debug_action.setChecked(False); self.debug_action.blockSignals(False)
                QtWidgets.QMessageBox.critical(self, "Debug logging unavailable", str(error)); return
            root = logging.getLogger(); self.previous_log_level = root.level; root.setLevel(logging.DEBUG); root.addHandler(handler)
            self.debug_handler = handler; self.debug_action.setText("Disable debug logging")
            logger.info("Debug logging enabled: %s", path); self.statusBar().showMessage(f"Debug logging to {path}", 5000)
        else:
            self.stop_debug_logging()

    def stop_debug_logging(self):
        handler, self.debug_handler = self.debug_handler, None
        if handler is None: return
        logger.info("Debug logging disabled")
        root = logging.getLogger(); root.removeHandler(handler)
        if self.previous_log_level is not None: root.setLevel(self.previous_log_level)
        self.previous_log_level = None; handler.close(); self.debug_action.setText("Enable debug logging…")
        if handler.error is not None:
            QtWidgets.QMessageBox.warning(self, "Debug logging error", str(handler.error))

    def update_capabilities(self):
        connected = self.session.connected; caps = self.session.capabilities
        self.acquisition.set_device_actions_available(connected and caps.reset_device, connected and caps.reset_msp)
        self.device_config.set_available(connected and caps.device_config)
        self.service.set_available(connected and caps.runtime_status and not self.session.busy_operation)
        self.firmware.set_available(connected and caps.msp_update, not self.session.busy_operation)

    def operation_changed(self, running):
        self.connection.setEnabled(not running); self.tabs.setTabEnabled(0, not running)
        connected = self.session.connected; caps = self.session.capabilities
        self.acquisition.set_device_actions_available(connected and caps.reset_device, connected and caps.reset_msp)
        self.service.set_available(False if running else self.session.connected and self.session.capabilities.runtime_status); self.firmware.set_available(self.session.connected and self.session.capabilities.msp_update, not running)

    def closeEvent(self, event):
        if self.acquisition.worker:
            self.acquisition.worker.stop()
            if self.acquisition.thread and not self.acquisition.thread.wait(2000): event.ignore(); return
        try:
            if self.session.connected and not self.session.busy_operation: self.session.disconnect()
        except Exception: pass
        self.stop_debug_logging()
        event.accept()


def main(argv=None):
    parser = argparse.ArgumentParser(description="WULPUS Pro Max desktop GUI")
    parser.add_argument("--simulator", action="store_true", help="enable the development simulator")
    args = parser.parse_args(argv)
    app = QtWidgets.QApplication(sys.argv[:1]); app.setApplicationName(APP_NAME); app.setApplicationVersion(APP_VERSION); app.setStyle("Fusion")
    window = MainWindow(args.simulator); window.show(); return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
