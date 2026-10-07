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


Acquisition components for the desktop application.
"""

from __future__ import annotations

import logging

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets
from scipy import signal

from .async_ui import AsyncMixin, _error_text
from .models import (
    save_npz,
)
from .workers import AcquisitionWorker

logger = logging.getLogger(__name__)


class BandPassRangeSlider(QtWidgets.QWidget):
    """Compact dual-handle slider for selecting a frequency interval in kHz."""

    range_changed = QtCore.Signal(int, int)

    def __init__(self):
        """Initialize a 10 kHz to 3.99 MHz band-pass range."""
        super().__init__()
        self.minimum = 10
        self.maximum = 3990
        self.low = 400
        self.high = 3600
        self._dragging = None
        self.setMinimumSize(220, 48)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.setToolTip("Drag either handle to set the lower or upper cutoff")

    def set_limits(self, minimum, maximum):
        """Set the available slider interval and clamp the selected band."""
        self.minimum = int(minimum)
        self.maximum = max(self.minimum + 1, int(maximum))
        self.set_values(self.low, self.high)

    def set_values(self, low, high):
        """Update both handles while preserving their ordering."""
        low = min(max(int(low), self.minimum), self.maximum - 1)
        high = min(max(int(high), low + 1), self.maximum)
        changed = (low, high) != (self.low, self.high)
        self.low, self.high = low, high
        self.update()
        if changed:
            self.range_changed.emit(low, high)

    def _x_for_value(self, value):
        left, right = 12, max(13, self.width() - 12)
        ratio = (value - self.minimum) / (self.maximum - self.minimum)
        return left + ratio * (right - left)

    def _value_for_x(self, position):
        left, right = 12, max(13, self.width() - 12)
        ratio = min(1.0, max(0.0, (position - left) / (right - left)))
        return round(self.minimum + ratio * (self.maximum - self.minimum))

    def paintEvent(self, event):
        """Draw the full range, selected pass band, handles, and endpoint labels."""
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        y = 17
        left, right = 12, self.width() - 12
        palette = self.palette()
        painter.setPen(QtGui.QPen(palette.mid().color(), 5, QtCore.Qt.SolidLine))
        painter.drawLine(left, y, right, y)
        low_x, high_x = self._x_for_value(self.low), self._x_for_value(self.high)
        painter.setPen(QtGui.QPen(palette.highlight().color(), 6, QtCore.Qt.SolidLine))
        painter.drawLine(round(low_x), y, round(high_x), y)
        painter.setPen(QtGui.QPen(palette.highlight().color(), 2))
        painter.setBrush(palette.base())
        painter.drawEllipse(QtCore.QPointF(low_x, y), 7, 7)
        painter.drawEllipse(QtCore.QPointF(high_x, y), 7, 7)
        painter.setPen(palette.text().color())
        label_y = 43
        painter.drawText(0, label_y, f"{self.low / 1000:g} MHz")
        high_label = f"{self.high / 1000:g} MHz"
        width = painter.fontMetrics().horizontalAdvance(high_label)
        painter.drawText(self.width() - width, label_y, high_label)

    def mousePressEvent(self, event):
        """Select the closest handle and begin adjusting it."""
        position = event.position().x()
        self._dragging = (
            "low"
            if abs(position - self._x_for_value(self.low))
            <= abs(position - self._x_for_value(self.high))
            else "high"
        )
        self._move_handle(position)

    def mouseMoveEvent(self, event):
        """Move the active handle while dragging."""
        if self._dragging:
            self._move_handle(event.position().x())

    def mouseReleaseEvent(self, event):
        """Finish a handle drag."""
        del event
        self._dragging = None

    def _move_handle(self, position):
        value = self._value_for_x(position)
        if self._dragging == "low":
            self.set_values(min(value, self.high - 1), self.high)
        else:
            self.set_values(self.low, max(value, self.low + 1))


class AcquisitionTab(QtWidgets.QWidget, AsyncMixin):
    """Live acquisition view; protocol I/O belongs to the acquisition worker.

    Qt callbacks update widgets on the GUI thread. Recovery commands are queued
    until the worker releases the transport, so two readers never share it.
    """

    running_changed = QtCore.Signal(bool)
    session_changed = QtCore.Signal()

    def __init__(self, session, config_editor):
        """Initialize acquisition controls, plots, and shared session state."""
        super().__init__()
        self.session = session
        self.pool = QtCore.QThreadPool.globalInstance()
        self.thread = self.worker = None
        self.result = None
        self.pending_device_action = None
        self.editor = config_editor
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(["Off", "A-mode", "B-mode"])
        self.fps = QtWidgets.QSpinBox()
        self.fps.setRange(1, 60)
        self.fps.setValue(20)
        self.raw = QtWidgets.QCheckBox("Raw")
        self.raw.setChecked(True)
        self.filtered = QtWidgets.QCheckBox("Filtered")
        self.envelope = QtWidgets.QCheckBox("Envelope")
        self.gain = QtWidgets.QCheckBox("Gain curve")
        self.gain.setChecked(True)
        self.config_choice = QtWidgets.QComboBox()
        self.config_choice.addItem("0")
        self.low_cutoff = QtWidgets.QDoubleSpinBox()
        self.low_cutoff.setRange(0.01, 3.9)
        self.low_cutoff.setValue(0.4)
        self.low_cutoff.setSuffix(" MHz")
        self.high_cutoff = QtWidgets.QDoubleSpinBox()
        self.high_cutoff.setRange(0.02, 3.99)
        self.high_cutoff.setValue(3.6)
        self.high_cutoff.setSuffix(" MHz")
        self.band_pass_range = BandPassRangeSlider()
        self.low_cutoff.valueChanged.connect(self._cutoffs_changed)
        self.high_cutoff.valueChanged.connect(self._cutoffs_changed)
        self.band_pass_range.range_changed.connect(self._slider_range_changed)
        self.pause = QtWidgets.QPushButton("Pause display")
        self.pause.setCheckable(True)
        self.autoscale = QtWidgets.QCheckBox("Autoscale")
        self.autoscale.setChecked(False)
        self.output = QtWidgets.QLineEdit()
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self.browse_output)
        self.start = QtWidgets.QPushButton("Start")
        self.stop = QtWidgets.QPushButton("Stop")
        self.stop.setEnabled(False)
        self.reboot = QtWidgets.QPushButton("Reboot device")
        self.reboot.setEnabled(False)
        self.reset_msp = QtWidgets.QPushButton("Reset MSP430")
        self.reset_msp.setEnabled(False)
        self.device_actions_group = QtWidgets.QGroupBox("Device controls")
        device_actions = QtWidgets.QHBoxLayout(self.device_actions_group)
        device_actions.setContentsMargins(8, 8, 8, 6)
        device_actions.addWidget(self.reboot)
        device_actions.addWidget(self.reset_msp)
        self.progress = QtWidgets.QProgressBar()
        self.counters = QtWidgets.QLabel("Frames 0 · gaps 0")
        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("Display"))
        controls.addWidget(self.mode)
        controls.addWidget(QtWidgets.QLabel("Max FPS"))
        controls.addWidget(self.fps)
        controls.addWidget(QtWidgets.QLabel("Save NPZ"))
        controls.addWidget(self.output, 1)
        controls.addWidget(browse)
        controls.addWidget(self.start)
        controls.addWidget(self.stop)
        controls.addSpacing(12)
        controls.addWidget(self.device_actions_group)
        display_controls = QtWidgets.QHBoxLayout()
        for widget in (self.raw, self.filtered, self.envelope, self.gain):
            display_controls.addWidget(widget)
        display_controls.addWidget(QtWidgets.QLabel("TX/RX config"))
        display_controls.addWidget(self.config_choice)
        display_controls.addWidget(QtWidgets.QLabel("Band-pass"))
        display_controls.addWidget(QtWidgets.QLabel("Low"))
        display_controls.addWidget(self.low_cutoff)
        display_controls.addWidget(self.band_pass_range, 1)
        display_controls.addWidget(QtWidgets.QLabel("High"))
        display_controls.addWidget(self.high_cutoff)
        display_controls.addStretch()
        display_controls.addWidget(self.autoscale)
        display_controls.addWidget(self.pause)
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setTitle("A-mode data")
        self.plot.setLabel("bottom", "Samples")
        self.plot.setLabel("left", "ADC digital code")
        self.plot_item = self.plot.getPlotItem()
        self.plot_item.showAxis("right")
        self.plot_item.setLabel("right", "Gain", units="dB")
        self.plot_item.getAxis("right").setWidth(58)
        self.plot_item.getAxis("right").setTicks(
            [[(value, str(value)) for value in (*range(-10, 111, 20), 120)]]
        )
        self.gain_view = pg.ViewBox()
        self.plot_item.scene().addItem(self.gain_view)
        self.plot_item.getAxis("right").linkToView(self.gain_view)
        self.gain_view.setXLink(self.plot_item)

        def sync_gain_view():
            """Keep the secondary gain axis aligned with the primary plot."""
            self.gain_view.setGeometry(self.plot_item.vb.sceneBoundingRect())

        self.plot_item.vb.sigResized.connect(sync_gain_view)
        sync_gain_view()
        self.raw_curve = self.plot.plot(
            pen=pg.mkPen("#4dabf7", width=2), name="Raw data"
        )
        self.filtered_curve = self.plot.plot(
            pen=pg.mkPen("#51cf66", width=3), name="Filtered data"
        )
        self.envelope_curve = self.plot.plot(
            pen=pg.mkPen("#ff6b6b", width=3), name="Envelope"
        )
        self.gain_curve = pg.PlotCurveItem(
            pen=pg.mkPen("#adb5bd", width=2, style=QtCore.Qt.DashLine),
            name="Gain curve",
        )
        self.gain_view.addItem(self.gain_curve)
        legend = self.plot.addLegend()
        legend.addItem(self.gain_curve, "Gain curve")
        self.image = pg.ImageItem(axisOrder="col-major", autoDownsample=False)
        self.plot.addItem(self.image)
        self.image.hide()
        self.bmode = None
        self.bmode_separators = []
        self.last_draw = QtCore.QElapsedTimer()
        self.last_draw.start()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addLayout(display_controls)
        layout.addWidget(self.progress)
        layout.addWidget(self.counters)
        layout.addWidget(self.plot, 1)
        self.start.clicked.connect(self.start_acquisition)
        self.stop.clicked.connect(self.stop_acquisition)
        self.reboot.clicked.connect(self.reboot_device)
        self.reset_msp.clicked.connect(self.reset_msp_device)
        self.mode.currentTextChanged.connect(self.change_mode)
        self.pause.toggled.connect(
            lambda value: self.pause.setText(
                "Resume display" if value else "Pause display"
            )
        )
        self.gain.toggled.connect(self.gain_curve.setVisible)
        self.mode.currentTextChanged.connect(self.update_worker_display)
        self.fps.valueChanged.connect(self.update_worker_display)
        self.change_mode(self.mode.currentText())

    def _cutoffs_changed(self):
        """Synchronize numeric cutoff fields to the range slider."""
        low = round(self.low_cutoff.value() * 1000)
        high = round(self.high_cutoff.value() * 1000)
        if low >= high:
            sender = self.sender()
            if sender is self.low_cutoff:
                low = max(10, high - 10)
                self.low_cutoff.setValue(low / 1000)
            else:
                high = min(round(self.high_cutoff.maximum() * 1000), low + 10)
                self.high_cutoff.setValue(high / 1000)
        self.band_pass_range.set_values(low, high)

    def _slider_range_changed(self, low, high):
        """Synchronize slider handles to the precise numeric cutoff fields."""
        self.low_cutoff.setValue(low / 1000)
        self.high_cutoff.setValue(high / 1000)

    def set_device_actions_available(self, reboot, reset_msp):
        """Enable supported recovery commands unless a recovery is already queued."""
        pending = self.pending_device_action is not None
        self.reboot.setEnabled(bool(reboot) and not pending)
        self.reset_msp.setEnabled(bool(reset_msp) and not pending)

    def reboot_device(self):
        """Confirm a host reboot and route it through cooperative recovery."""
        if (
            QtWidgets.QMessageBox.question(
                self, "Reboot device", "Reboot the connected device and disconnect?"
            )
            != QtWidgets.QMessageBox.Yes
        ):
            return
        self.run_or_queue_device_action("reboot")

    def reset_msp_device(self):
        """Confirm an MSP430 reset that preserves the host connection."""
        if (
            QtWidgets.QMessageBox.question(
                self, "Reset MSP430", "Reset the MSP430 now?"
            )
            != QtWidgets.QMessageBox.Yes
        ):
            return
        self.run_or_queue_device_action("reset_msp")

    def run_or_queue_device_action(self, action):
        """Stop capture before issuing reset/reboot on the same protocol stream."""
        if self.worker is not None:
            self.pending_device_action = action
            self.reboot.setEnabled(False)
            self.reset_msp.setEnabled(False)
            self.counters.setText("Stopping acquisition before device command…")
            self.worker.stop()
            self.stop.setEnabled(False)
            return
        operation = (
            self.session.reboot if action == "reboot" else self.session.reset_msp
        )
        task = self.run_task(operation)
        if action == "reboot":
            task.signals.finished.connect(self.session_changed.emit)
        task.signals.finished.connect(
            lambda: self.set_device_actions_available(
                self.session.connected and self.session.capabilities.reset_device,
                self.session.connected and self.session.capabilities.reset_msp,
            )
        )

    def browse_output(self):
        """Select the optional destination for raw acquisition data."""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save acquisition", "acquisition.npz", "NumPy (*.npz)"
        )
        if path:
            self.output.setText(path)

    def start_acquisition(self):
        """Validate settings and start a worker with mode-specific plot geometry."""
        try:
            config = self.editor.config()
            self.session.require("acquisition")
        except Exception as error:
            QtWidgets.QMessageBox.critical(self, "Cannot start", str(error))
            return
        self.progress.setRange(0, config.num_acqs)
        self.progress.setValue(0)
        self.bmode = np.zeros((config.num_txrx_configs, config.num_samples))
        # Reapply the selected mode after allocating the image. In particular,
        # never leak B-mode's categorical Y axis into an A-mode acquisition.
        self.change_mode(self.mode.currentText())
        current = self.config_choice.currentText()
        self.config_choice.clear()
        self.config_choice.addItems([str(i) for i in range(config.num_txrx_configs)])
        self.config_choice.setCurrentText(current if current else "0")
        nyquist = config.sampling_freq / 2e6
        self.low_cutoff.setMaximum(max(0.01, nyquist - 0.01))
        self.high_cutoff.setMaximum(max(0.02, nyquist - 0.001))
        self.band_pass_range.set_limits(10, round(self.high_cutoff.maximum() * 1000))
        if self.high_cutoff.value() <= self.low_cutoff.value():
            self.high_cutoff.setValue(self.high_cutoff.maximum())
        try:
            config.calc_gain_curve()
            self.gain_curve.setData(config.gain_curve_db)
            self.gain_view.setYRange(-10, 120, padding=0)
        except Exception:
            self.gain_curve.clear()
        self.gain_curve.setVisible(self.gain.isChecked())
        self.worker = AcquisitionWorker(
            self.session, config, self.mode.currentText(), self.fps.value()
        )
        self.thread = QtCore.QThread(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.frame.connect(self.on_frame)
        self.worker.completed.connect(self.on_complete)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.finished)
        self.start.setEnabled(False)
        self.stop.setEnabled(True)
        self.running_changed.emit(True)
        self.thread.start()

    @QtCore.Slot(object, int, int, int, int)
    def on_frame(self, samples, number, config_id, gaps, count):
        """Render a throttled preview; this callback never owns recorded data."""
        self.progress.setValue(count)
        self.counters.setText(
            f"Frames {count} · gaps {gaps} · acquisition {number} · config {config_id}"
        )
        mode = self.mode.currentText()
        if (
            samples is None
            or mode == "Off"
            or self.pause.isChecked()
            or self.last_draw.elapsed() < 1000 / self.fps.value()
        ):
            return
        self.last_draw.restart()
        data = np.asarray(samples, dtype=float)
        if mode == "A-mode":
            if config_id != self.config_choice.currentIndex():
                return
            filtered = self.filter_data(data)
            self.raw_curve.setData(data)
            self.raw_curve.setVisible(self.raw.isChecked())
            self.filtered_curve.setData(filtered)
            self.filtered_curve.setVisible(self.filtered.isChecked())
            self.envelope_curve.setData(np.abs(signal.hilbert(filtered)))
            self.envelope_curve.setVisible(self.envelope.isChecked())
            if self.autoscale.isChecked():
                self.plot.enableAutoRange()
            else:
                self.plot.setYRange(-3000, 3000, padding=0)
        else:
            if 0 <= config_id < self.bmode.shape[0]:
                self.bmode[config_id] = np.abs(signal.hilbert(self.filter_data(data)))
            # ImageItem's col-major convention is x first and y second:
            # samples/depth belong on x, discrete TX/RX configurations on y.
            self.image.setImage(self.bmode.T, autoLevels=True)
            config = self.editor.config()
            depth_mm = config.num_samples / config.sampling_freq * 1540 * 1000 / 2
            self.image.setRect(
                QtCore.QRectF(0, -0.5, depth_mm, config.num_txrx_configs)
            )

    def filter_data(self, data):
        """Apply a zero-phase FIR band-pass using the acquisition sampling rate."""
        config = self.editor.config()
        low, high = self.low_cutoff.value() * 1e6, self.high_cutoff.value() * 1e6
        nyquist = config.sampling_freq / 2
        high = min(high, nyquist * 0.999)
        if low >= high:
            return data.copy()
        transition = max(1.0, min(0.2e6, low * 0.5, (nyquist - high) * 0.5))
        taps = signal.remez(
            31,
            [0, low - transition, low, high, high + transition, nyquist],
            [0, 1, 0],
            fs=config.sampling_freq,
            maxiter=2500,
        )
        return signal.filtfilt(taps, 1, data)

    def change_mode(self, mode):
        """Switch between hidden display, continuous amplitude, and discrete rows."""
        off, bmode = mode == "Off", mode == "B-mode"
        self.plot.setVisible(not off)
        self.image.setVisible(bmode and not off)
        for curve in (self.raw_curve, self.filtered_curve, self.envelope_curve):
            curve.setVisible(not off and not bmode)
        self.gain_curve.setVisible(not off and not bmode and self.gain.isChecked())
        self.plot_item.getAxis("right").setVisible(not off and not bmode)
        self.plot.setTitle("B-mode data" if bmode else "A-mode data")
        self.plot.setLabel("bottom", "Depth (mm)" if bmode else "Samples")
        self.plot.setLabel(
            "left", "TX/RX configuration" if bmode else "ADC digital code"
        )
        if bmode:
            self.configure_bmode_axis(self.editor.inputs["num_txrx_configs"].value())
        else:
            for separator in self.bmode_separators:
                self.plot.removeItem(separator)
            self.bmode_separators = []
            self.plot.getAxis("left").setTicks(None)
            self.plot.getViewBox().setLimits(yMin=None, yMax=None)
            self.plot.getViewBox().setMouseEnabled(x=True, y=True)
            self.plot.enableAutoRange(axis="y")

    def configure_bmode_axis(self, count):
        """Center each configuration row on its integer ID and lock Y navigation."""
        for separator in self.bmode_separators:
            self.plot.removeItem(separator)
        self.bmode_separators = []
        ticks = [(index, f"Config {index}") for index in range(count)]
        self.plot.getAxis("left").setTicks([ticks])
        self.plot.getViewBox().setLimits(yMin=-0.5, yMax=count - 0.5)
        self.plot.getViewBox().setMouseEnabled(x=True, y=False)
        self.plot.setYRange(-0.5, count - 0.5, padding=0)
        for boundary in range(1, count):
            separator = pg.InfiniteLine(
                boundary - 0.5, angle=0, pen=pg.mkPen("#69727d", width=1)
            )
            separator.setZValue(10)
            self.plot.addItem(separator)
            self.bmode_separators.append(separator)

    def update_worker_display(self, *_):
        """Propagate preview mode/rate changes to a running worker."""
        if self.worker is not None:
            self.worker.set_display(self.mode.currentText(), self.fps.value())

    def on_complete(self, result):
        """Report capture completion and save the optional notebook-compatible NPZ."""
        self.result = result
        self.progress.setValue(len(result.frames))
        self.counters.setText(
            f"Frames {len(result.frames)} · gaps {result.frame_gaps} · {'complete' if result.completed else 'stopped'}"
        )
        if self.output.text().strip():
            try:
                save_npz(self.output.text().strip(), result)
            except Exception as error:
                QtWidgets.QMessageBox.critical(self, "Save failed", str(error))

    def on_error(self, text):
        """Display the worker's final error message without its full traceback."""
        QtWidgets.QMessageBox.critical(self, "Acquisition failed", _error_text(text))

    def stop_acquisition(self):
        """Request cooperative stop and disable duplicate stop requests."""
        if self.worker:
            self.worker.stop()
            self.stop.setEnabled(False)

    def finished(self):
        """Release worker ownership before dispatching a queued recovery command."""
        self.start.setEnabled(True)
        self.stop.setEnabled(False)
        self.running_changed.emit(False)
        if self.worker:
            self.worker.deleteLater()
        if self.thread:
            self.thread.deleteLater()
        self.worker = self.thread = None
        pending, self.pending_device_action = self.pending_device_action, None
        if pending is not None:
            QtCore.QTimer.singleShot(
                0, lambda action=pending: self.run_or_queue_device_action(action)
            )
