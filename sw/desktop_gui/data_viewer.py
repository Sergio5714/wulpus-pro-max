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


Data viewer components for the desktop application.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets
from scipy import signal

logger = logging.getLogger(__name__)


class NpzViewerTab(QtWidgets.QWidget):
    """Offline samples-by-frame viewer, independent of the connected device."""

    REQUIRED_ARRAYS = ("data_arr", "acq_num_arr", "tx_rx_id_arr")

    def __init__(self):
        """Initialize NPZ data state, playback controls, and visualization."""
        super().__init__()
        self.data_arr = np.empty((0, 0))
        self.acq_num_arr = np.empty(0)
        self.tx_rx_id_arr = np.empty(0)
        self.filtered_indices = np.empty(0, dtype=np.intp)
        self.replay_range = None
        self.path = QtWidgets.QLineEdit()
        self.path.setPlaceholderText("Select a notebook-compatible .npz acquisition")
        browse = QtWidgets.QPushButton("Browse…")
        load = QtWidgets.QPushButton("Load")
        browse.clicked.connect(self.browse)
        load.clicked.connect(lambda: self.load(self.path.text()))
        file_row = QtWidgets.QHBoxLayout()
        file_row.addWidget(self.path, 1)
        file_row.addWidget(browse)
        file_row.addWidget(load)
        self.info = QtWidgets.QLabel("No acquisition file loaded")
        self.config = QtWidgets.QComboBox()
        self.config.setEnabled(False)
        self.position = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.position.setEnabled(False)
        self.position.setRange(0, 0)
        self.position_label = QtWidgets.QLabel("Acquisition 0 of 0")
        self.sampling = QtWidgets.QDoubleSpinBox()
        self.sampling.setRange(0.5, 100)
        self.sampling.setValue(8)
        self.sampling.setSuffix(" MHz")
        self.low = QtWidgets.QDoubleSpinBox()
        self.low.setRange(0.01, 49.8)
        self.low.setValue(0.4)
        self.low.setSuffix(" MHz")
        self.high = QtWidgets.QDoubleSpinBox()
        self.high.setRange(0.02, 49.9)
        self.high.setValue(3.6)
        self.high.setSuffix(" MHz")
        self.raw = QtWidgets.QCheckBox("Raw")
        self.raw.setChecked(True)
        self.filtered = QtWidgets.QCheckBox("Filtered")
        self.envelope = QtWidgets.QCheckBox("Envelope")
        self.replay_fps = QtWidgets.QDoubleSpinBox()
        self.replay_fps.setRange(0.1, 500)
        self.replay_fps.setValue(20)
        self.replay_fps.setSuffix(" FPS")
        self.replay = QtWidgets.QPushButton("Replay")
        self.stop = QtWidgets.QPushButton("Stop")
        self.stop.setEnabled(False)
        selectors = QtWidgets.QHBoxLayout()
        selectors.addWidget(QtWidgets.QLabel("TX/RX config"))
        selectors.addWidget(self.config)
        selectors.addWidget(self.position_label)
        selectors.addWidget(self.position, 1)
        processing = QtWidgets.QHBoxLayout()
        for widget in (
            self.raw,
            self.filtered,
            self.envelope,
            QtWidgets.QLabel("Sampling"),
            self.sampling,
            QtWidgets.QLabel("Band-pass"),
            self.low,
            self.high,
        ):
            processing.addWidget(widget)
        processing.addStretch()
        processing.addWidget(self.replay_fps)
        processing.addWidget(self.replay)
        processing.addWidget(self.stop)
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Samples")
        self.plot.setLabel("left", "ADC digital code")
        self.raw_curve = self.plot.plot(pen=pg.mkPen("#4dabf7", width=2), name="Raw")
        self.filtered_curve = self.plot.plot(
            pen=pg.mkPen("#51cf66", width=3), name="Filtered"
        )
        self.envelope_curve = self.plot.plot(
            pen=pg.mkPen("#ff6b6b", width=3), name="Envelope"
        )
        self.plot.addLegend()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(file_row)
        layout.addWidget(self.info)
        layout.addLayout(selectors)
        layout.addLayout(processing)
        layout.addWidget(self.plot, 1)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.config.currentIndexChanged.connect(self.update_filter)
        self.position.valueChanged.connect(self.update_plot)
        for widget in (self.raw, self.filtered, self.envelope):
            widget.toggled.connect(self.update_plot)
        for widget in (self.sampling, self.low, self.high):
            widget.valueChanged.connect(self.signal_controls_changed)
        self.replay.clicked.connect(self.start_replay)
        self.stop.clicked.connect(self.stop_replay)

    @classmethod
    def read_npz(cls, path):
        """Read samples-by-frames data and matching metadata without pickle.

        Return ``(data_arr, acq_num_arr, tx_rx_id_arr)``. Reject missing keys,
        incompatible dimensions, and mismatched frame counts with ValueError.
        """
        with np.load(path, allow_pickle=False) as archive:
            missing = [name for name in cls.REQUIRED_ARRAYS if name not in archive]
            if missing:
                raise ValueError(f"Missing required NPZ arrays: {', '.join(missing)}")
            data = np.asarray(archive["data_arr"])
            numbers = np.asarray(archive["acq_num_arr"])
            configs = np.asarray(archive["tx_rx_id_arr"])
        if data.ndim != 2:
            raise ValueError(
                "data_arr must be a two-dimensional samples-by-frames array"
            )
        if numbers.ndim != 1 or configs.ndim != 1:
            raise ValueError("Metadata arrays must be one-dimensional")
        if data.shape[1] != len(numbers) or len(numbers) != len(configs):
            raise ValueError(
                "Metadata lengths must match the number of data_arr columns"
            )
        return data, numbers, configs

    def browse(self):
        """Choose a compatible acquisition archive and load it."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open acquisition", "", "NumPy (*.npz)"
        )
        if path:
            self.load(path)

    def load(self, path):
        """Replace the loaded dataset after validation and reset frame selection."""
        if not path:
            return
        try:
            data, numbers, configs = self.read_npz(path)
        except (OSError, ValueError) as error:
            QtWidgets.QMessageBox.critical(
                self, "Could not load acquisition", str(error)
            )
            return
        self.stop_replay()
        self.path.setText(str(path))
        self.data_arr = data
        self.acq_num_arr = numbers
        self.tx_rx_id_arr = configs
        unique, counts = np.unique(configs, return_counts=True)
        self.config.blockSignals(True)
        self.config.clear()
        self.config.addItem(f"All configurations ({len(configs)} frames)", None)
        for config_id, count in zip(unique, counts):
            self.config.addItem(
                f"Config {int(config_id)} ({int(count)} frames)", int(config_id)
            )
        self.config.blockSignals(False)
        self.config.setEnabled(bool(len(configs)))
        self.info.setText(
            f"{Path(path).name} — {data.shape[1]} frames, {data.shape[0]} samples/frame, {len(unique)} configurations"
        )
        logger.debug(
            "Loaded data file %s: %d frames, %d samples/frame, %d configurations",
            path,
            data.shape[1],
            data.shape[0],
            len(unique),
        )
        self.update_filter()

    def update_filter(self, *_):
        """Map the selected configuration to source frame indices in file order."""
        selected = self.config.currentData()
        self.filtered_indices = (
            np.arange(self.data_arr.shape[1], dtype=np.intp)
            if selected is None
            else np.flatnonzero(self.tx_rx_id_arr == selected)
        )
        count = len(self.filtered_indices)
        self.position.setEnabled(bool(count))
        self.position.setRange(0, max(0, count - 1))
        self.position.setValue(0)
        self.update_plot()

    def filter_data(self, samples):
        """Filter one frame using the user-supplied sampling rate and passband."""
        sampling_hz = self.sampling.value() * 1e6
        nyquist = sampling_hz / 2
        low = self.low.value() * 1e6
        high = min(self.high.value() * 1e6, nyquist * 0.999)
        if low >= high:
            raise ValueError("Band-pass low cutoff must be below the high cutoff")
        transition = max(1.0, min(0.2e6, low * 0.5, (nyquist - high) * 0.5))
        taps = signal.remez(
            31,
            [0, low - transition, low, high, high + transition, nyquist],
            [0, 1, 0],
            fs=sampling_hz,
            maxiter=2500,
        )
        return signal.filtfilt(taps, 1, samples)

    def update_plot(self, *_):
        """Update visible traces, preserving the captured view range during replay."""
        if not len(self.filtered_indices):
            for curve in (self.raw_curve, self.filtered_curve, self.envelope_curve):
                curve.clear()
            self.position_label.setText("Acquisition 0 of 0")
            return
        frame = int(self.filtered_indices[self.position.value()])
        samples = np.asarray(self.data_arr[:, frame], dtype=float)
        filtered = envelope = None
        if self.filtered.isChecked() or self.envelope.isChecked():
            try:
                filtered = self.filter_data(samples)
                envelope = np.abs(signal.hilbert(filtered))
            except ValueError as error:
                self.info.setText(f"Signal processing failed: {error}")
        self.raw_curve.setData(samples if self.raw.isChecked() else [])
        self.filtered_curve.setData(
            filtered if filtered is not None and self.filtered.isChecked() else []
        )
        self.envelope_curve.setData(
            envelope if envelope is not None and self.envelope.isChecked() else []
        )
        self.position_label.setText(
            f"Acquisition {self.position.value() + 1} of {len(self.filtered_indices)}"
        )
        self.plot.setTitle(
            f"Frame {frame} · acquisition {int(self.acq_num_arr[frame])} · TX/RX config {int(self.tx_rx_id_arr[frame])}"
        )
        if self.replay_range is None:
            self.plot.enableAutoRange()
        else:
            x_range, y_range = self.replay_range
            self.plot.setXRange(*x_range, padding=0)
            self.plot.setYRange(*y_range, padding=0)

    def signal_controls_changed(self, *_):
        """Keep passband controls within Nyquist bounds and redraw the frame."""
        maximum = max(0.02, self.sampling.value() / 2 - 0.01)
        self.low.setMaximum(maximum)
        self.high.setMaximum(maximum)
        if self.high.value() <= self.low.value():
            self.high.setValue(min(maximum, self.low.value() + 0.1))
        self.update_plot()

    def start_replay(self):
        """Advance through selected frames on a timer with fixed plot limits."""
        if not len(self.filtered_indices):
            return
        self.plot.getViewBox().autoRange()
        self.replay_range = [list(axis_range) for axis_range in self.plot.viewRange()]
        self.plot.disableAutoRange()
        self.timer.setInterval(max(1, round(1000 / self.replay_fps.value())))
        self.timer.start()
        self.replay.setEnabled(False)
        self.stop.setEnabled(True)

    def next_frame(self):
        """Advance replay once, stopping automatically at the last selected frame."""
        if self.position.value() >= self.position.maximum():
            self.stop_replay()
            return
        self.position.setValue(self.position.value() + 1)

    def stop_replay(self):
        """Stop the replay timer and return manual navigation to auto-ranging."""
        was_replaying = self.timer.isActive() or self.replay_range is not None
        self.timer.stop()
        self.replay_range = None
        self.replay.setEnabled(True)
        self.stop.setEnabled(False)
        if was_replaying:
            self.update_plot()
