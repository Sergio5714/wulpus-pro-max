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

from PySide6 import QtCore, QtGui, QtWidgets
from wulpus.config_package_pro import configuration_package, us_to_ticks
from wulpus.uss_conf_pro import (
    VGA_MAX_GAIN_DB,
    VGA_RC_CAP_VAL,
    VGA_RC_EN_DELAY_US,
    VGA_RC_SER_RES,
    VGA_SLOPE_CODE_FIXED_GAIN_MODE,
    digipot_code_to_res,
    vga_precharge_voltage,
    vga_volts_to_gain_db,
)

from .models import (
    build_config,
    config_values,
    load_config,
    save_config,
)
from .txrx import TxRxConfigCard, TxRxConfigDialog

logger = logging.getLogger(__name__)


ACQUISITION_PARAMETERS = (
    "num_acqs",
    "meas_period",
    "dcdc_turnon",
    "sampling_freq",
    "num_samples",
    "enable_env_det",
)
GAIN_PARAMETERS = ("rx_gain", "vga_rc_prech_cyc", "vga_slope_code")
EXCITATION_PARAMETERS = ("trans_freq", "pulse_freq", "num_pulses")
ADVANCED_PARAMETERS = (
    "start_hvmuxrx",
    "start_ppg",
    "turnon_adc",
    "start_pgainbias",
    "start_adcsampl",
    "capt_timeout",
)
HIDDEN_PARAMETERS = ("restart_capt",)
LABEL_OVERRIDES = {
    "dcdc_turnon": "HV supply ON time [µs]",
    "num_samples": "Number of samples (fixed)",
}


class AcquisitionCyclePreview(QtWidgets.QWidget):
    """Visualize the slow-timer period and HV supply switch command."""

    def __init__(self, parent=None):
        """Initialize the live acquisition-cycle preview."""
        super().__init__(parent)
        self._values = {}
        self.setMinimumHeight(215)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def set_values(self, values):
        """Replace cycle values and schedule a repaint."""
        self._values = dict(values)
        self.update()

    def cycle_snapshot(self):
        """Return timer events matching the MSP430 slow/fast timer callbacks."""
        period = float(self._values.get("meas_period", 0))
        switch_enable = float(self._values.get("dcdc_turnon", 0))
        sample_start = float(self._values.get("start_adcsampl", 0))
        sample_count = float(self._values.get("num_samples", 0))
        sample_frequency = max(1.0, float(self._values.get("sampling_freq", 1)))
        acquisition_end = sample_start + sample_count * 1e6 / sample_frequency
        switch_enabled = 0 <= switch_enable < period
        switch_disable = period + acquisition_end if switch_enabled else None
        duty_cycle = (
            min(100, 100 * (switch_disable - switch_enable) / period)
            if switch_enabled and period > 0
            else 0
        )
        return {
            "period": period,
            "switch_enable": switch_enable if switch_enabled else None,
            "next_acquisition": period,
            "switch_disable": switch_disable,
            "acquisition_end": acquisition_end,
            "lead_time": period - switch_enable if switch_enabled else 0,
            "duty_cycle": duty_cycle,
            "switch_enabled": switch_enabled,
        }

    def paintEvent(self, event):
        """Paint one acquisition interval and the following MUX-to-RX event."""
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().color(QtGui.QPalette.Base))
        if not self._values:
            return
        cycle = self.cycle_snapshot()
        text = self.palette().color(QtGui.QPalette.Text)
        muted = self.palette().color(QtGui.QPalette.Mid)
        green = QtGui.QColor("#2f9e44")
        red = QtGui.QColor("#e03131")
        blue = QtGui.QColor("#228be6")
        left, right = 95, max(130, self.width() - 24)
        end = max(cycle["period"] * 1.06, (cycle["switch_disable"] or 0), 1)

        def to_x(value):
            return int(left + value / end * (right - left))

        painter.setPen(text)
        painter.setFont(QtGui.QFont(painter.font().family(), -1, QtGui.QFont.Bold))
        painter.drawText(
            QtCore.QRect(0, 6, self.width(), 24),
            QtCore.Qt.AlignCenter,
            "High Voltage DC-DC Duty Cycle",
        )
        painter.setFont(QtGui.QFont(painter.font().family(), -1, QtGui.QFont.Normal))
        legend_x, legend_y = max(12, self.width() // 2 - 75), 43
        painter.setPen(QtGui.QPen(green, 7))
        painter.drawLine(legend_x, legend_y, legend_x + 24, legend_y)
        painter.setPen(text)
        painter.drawText(legend_x + 34, legend_y + 5, "HV DC-DC is ON")
        axis_y, bar_y = 132, 92
        painter.setPen(QtGui.QPen(muted, 1))
        painter.drawLine(left, axis_y, right, axis_y)
        painter.setPen(QtGui.QPen(blue, 2))
        for value in (0, cycle["next_acquisition"]):
            x = to_x(value)
            painter.drawLine(x, 65, x, axis_y + 5)
        painter.setPen(text)
        painter.drawText(left, 62, "Current ACQ sequencer trigger")
        next_x = to_x(cycle["next_acquisition"])
        painter.drawText(max(left, next_x - 130), 62, "Next ACQ sequencer trigger")

        if cycle["switch_enabled"]:
            on_x = to_x(cycle["switch_enable"])
            off_x = to_x(cycle["switch_disable"])
            painter.setPen(QtGui.QPen(green, 8))
            painter.drawLine(on_x, bar_y, off_x, bar_y)
            ticks = (
                (cycle["switch_enable"], "enable command"),
                (cycle["next_acquisition"], "next ACQ trigger"),
                (cycle["switch_disable"], "sequence done / disable"),
            )
        else:
            painter.setPen(QtGui.QPen(red, 2))
            painter.drawLine(left, bar_y, right, bar_y)
            ticks = ((cycle["next_acquisition"], "period"),)

        painter.setFont(QtGui.QFont(painter.font().family(), 8))
        painter.setPen(text)
        painter.drawText(left - 3, axis_y + 20, "0")
        for index, (value, label) in enumerate(ticks):
            x = to_x(value)
            painter.setPen(QtGui.QPen(muted, 1))
            painter.drawLine(x, axis_y - 5, x, axis_y + 5)
            painter.setPen(text)
            caption = f"{label} {value:,.0f} µs"
            width = painter.fontMetrics().horizontalAdvance(caption)
            label_x = max(left, min(right - width, x - width // 2))
            painter.drawText(label_x, axis_y + 20 + (index % 2) * 16, caption)
        painter.setFont(QtGui.QFont(painter.font().family(), 10, QtGui.QFont.Bold))
        painter.drawText(
            QtCore.QRect(0, 180, self.width(), 24),
            QtCore.Qt.AlignCenter,
            f"Duty cycle: {cycle['duty_cycle']:.2f}%",
        )


class GainProfilePreview(QtWidgets.QWidget):
    """Render the configured receive gain over the ADC sampling window."""

    def __init__(self, parent=None):
        """Initialize the live receive-gain preview."""
        super().__init__(parent)
        self._values = {}
        self.setMinimumSize(520, 260)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )

    def set_values(self, values):
        """Replace gain/timing values and schedule a repaint."""
        self._values = dict(values)
        self.update()

    def gain_snapshot(self):
        """Calculate gain samples using the firmware configuration equations."""
        count = max(1, int(self._values.get("num_samples", 1)))
        frequency = max(1.0, float(self._values.get("sampling_freq", 1)))
        rx_gain = float(self._values.get("rx_gain", 0))
        precharge_cycles = float(self._values.get("vga_rc_prech_cyc", 0))
        slope_code = int(self._values.get("vga_slope_code", 0))
        pregain_v = vga_precharge_voltage(precharge_cycles)
        initial_gain = float(
            min(vga_volts_to_gain_db(pregain_v), VGA_MAX_GAIN_DB) + rx_gain
        )
        fixed = slope_code >= VGA_SLOPE_CODE_FIXED_GAIN_MODE
        inflection = (
            float(self._values.get("start_hvmuxrx", 0))
            - float(self._values.get("start_adcsampl", 0))
            + VGA_RC_EN_DELAY_US
        )
        times = tuple(index * 1e6 / frequency for index in range(count))
        gains = [initial_gain] * count
        if not fixed:
            rc_slope = (
                VGA_RC_SER_RES + digipot_code_to_res(slope_code)
            ) * VGA_RC_CAP_VAL
            for index, time_us in enumerate(times):
                if time_us >= inflection:
                    ramp_v = 3.3 * ((time_us - inflection) * 1e-6 / rc_slope)
                    gains[index] = float(
                        min(
                            vga_volts_to_gain_db(pregain_v + ramp_v),
                            VGA_MAX_GAIN_DB,
                        )
                        + rx_gain
                    )
        return {
            "times": times,
            "gains": tuple(gains),
            "fixed": fixed,
            "initial_gain": initial_gain,
            "inflection": inflection,
            "duration": count * 1e6 / frequency,
        }

    def paintEvent(self, event):
        """Paint gain in dB against time from ADC sampling start."""
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().color(QtGui.QPalette.Base))
        if not self._values:
            return
        profile = self.gain_snapshot()
        text = self.palette().color(QtGui.QPalette.Text)
        muted = self.palette().color(QtGui.QPalette.Mid)
        accent = QtGui.QColor("#9c36b5")
        left, right = 82, max(120, self.width() - 22)
        top, bottom = 45, max(90, self.height() - 58)
        minimum, maximum = -10, 120

        def to_x(time_us):
            return int(left + time_us / max(profile["duration"], 1) * (right - left))

        def to_y(gain):
            return int(bottom - (gain - minimum) / (maximum - minimum) * (bottom - top))

        painter.setPen(text)
        painter.setFont(QtGui.QFont(painter.font().family(), -1, QtGui.QFont.Bold))
        painter.drawText(
            QtCore.QRect(0, 6, self.width(), 24),
            QtCore.Qt.AlignCenter,
            "Receive Gain Profile",
        )
        painter.setFont(QtGui.QFont(painter.font().family(), 8))
        painter.setPen(QtGui.QPen(muted, 1))
        painter.drawLine(left, top, left, bottom)
        painter.drawLine(left, bottom, right, bottom)
        for fraction in (0.0, 0.5, 1.0):
            x = int(left + fraction * (right - left))
            painter.drawLine(x, bottom - 4, x, bottom + 4)
            painter.setPen(text)
            painter.drawText(
                x - 15, bottom + 18, f"{profile['duration'] * fraction:.1f}"
            )
            painter.setPen(QtGui.QPen(muted, 1))
        for gain_tick in (*range(-10, 111, 20), 120):
            y = to_y(gain_tick)
            painter.drawLine(left - 4, y, left + 4, y)
            painter.setPen(text)
            painter.drawText(
                QtCore.QRect(30, y - 8, left - 38, 16),
                QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
                str(gain_tick),
            )
            painter.setPen(QtGui.QPen(muted, 1))
        painter.setPen(text)
        painter.drawText(right - 42, bottom + 36, "Time [µs]")
        painter.save()
        painter.translate(14, top + (bottom - top) // 2 + 28)
        painter.rotate(-90)
        painter.drawText(0, 0, "Gain [dB]")
        painter.restore()

        points = [
            QtCore.QPointF(to_x(time_us), to_y(gain))
            for time_us, gain in zip(profile["times"], profile["gains"])
        ]
        painter.setPen(QtGui.QPen(accent, 2))
        painter.drawPolyline(QtGui.QPolygonF(points))
        painter.setPen(text)
        mode = "Fixed gain" if profile["fixed"] else "Time-varying gain"
        painter.drawText(
            left + 8, top + 16, f"{mode}; start {profile['initial_gain']:.1f} dB"
        )


class PulsePreview(QtWidgets.QWidget):
    """Render the configured unipolar 50% duty-cycle excitation burst."""

    def __init__(self, parent=None):
        """Initialize the live pulse preview."""
        super().__init__(parent)
        self._values = {}
        self.setMinimumSize(500, 360)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )

    def set_values(self, values):
        """Replace excitation values and schedule a repaint."""
        self._values = dict(values)
        self.update()

    def pulse_snapshot(self):
        """Return derived pulse properties used by painting and tests."""
        frequency = max(1.0, float(self._values.get("pulse_freq", 1)))
        count = max(0, int(self._values.get("num_pulses", 0)))
        period = 1e6 / frequency
        tick_step = max(1, (count + 7) // 8)
        tick_indices = list(range(0, count + 1, tick_step))
        if tick_indices[-1] != count:
            tick_indices.append(count)
        return {
            "frequency": frequency,
            "transducer_frequency": float(self._values.get("trans_freq", 0)),
            "count": count,
            "period": period,
            "high_time": period / 2,
            "duration": count * period,
            "ticks": tuple(index * period for index in tick_indices),
        }

    def paintEvent(self, event):
        """Paint the pulse train and its derived frequency/time annotations."""
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().color(QtGui.QPalette.Base))
        if not self._values:
            return
        pulse = self.pulse_snapshot()
        text = self.palette().color(QtGui.QPalette.Text)
        muted = self.palette().color(QtGui.QPalette.Mid)
        accent = QtGui.QColor("#f08c00")
        left, right = 72, max(100, self.width() - 24)
        high_y, low_y, axis_y = 78, 180, 214
        painter.setPen(text)
        painter.setFont(QtGui.QFont(painter.font().family(), -1, QtGui.QFont.Bold))
        painter.drawText(12, 24, "Unipolar excitation burst")
        painter.setFont(QtGui.QFont(painter.font().family(), -1, QtGui.QFont.Normal))
        painter.drawText(12, high_y + 5, "+15 V")
        painter.drawText(32, low_y + 5, "0 V")
        painter.setPen(QtGui.QPen(muted, 1))
        painter.drawLine(left, low_y, right, low_y)
        painter.drawLine(left, axis_y, right, axis_y)

        count = pulse["count"]
        points = [QtCore.QPointF(left, low_y)]
        if count:
            pulse_width = (right - left) / count
            for index in range(count):
                x0 = left + index * pulse_width
                xh = x0 + pulse_width / 2
                x1 = x0 + pulse_width
                points.extend(
                    (
                        QtCore.QPointF(x0, low_y),
                        QtCore.QPointF(x0, high_y),
                        QtCore.QPointF(xh, high_y),
                        QtCore.QPointF(xh, low_y),
                        QtCore.QPointF(x1, low_y),
                    )
                )
        painter.setPen(QtGui.QPen(accent, 2))
        painter.drawPolyline(QtGui.QPolygonF(points))

        painter.setFont(QtGui.QFont(painter.font().family(), 8))
        for tick in pulse["ticks"]:
            fraction = tick / pulse["duration"] if pulse["duration"] else 0
            x = int(left + fraction * (right - left))
            painter.setPen(QtGui.QPen(muted, 1, QtCore.Qt.DotLine))
            painter.drawLine(x, high_y - 8, x, axis_y + 4)
            painter.setPen(text)
            label = f"{tick:.3f}".rstrip("0").rstrip(".")
            bounds = painter.fontMetrics().boundingRect(label)
            label_x = max(left, min(right - bounds.width(), x - bounds.width() // 2))
            painter.drawText(label_x, axis_y + 19, label)
        painter.drawText(right - 42, axis_y + 38, "Time [µs]")
        painter.setFont(QtGui.QFont(painter.font().family(), -1))
        metrics = (
            f"Pulse frequency: {pulse['frequency'] / 1e6:.3f} MHz",
            f"Pulse period: {pulse['period']:.3f} µs",
            f"High time (50%): {pulse['high_time']:.3f} µs",
            f"Pulse count: {pulse['count']}",
            f"Burst duration: {pulse['duration']:.3f} µs",
            f"Transducer frequency: {pulse['transducer_frequency'] / 1e6:.3f} MHz",
        )
        for index, metric in enumerate(metrics):
            x = 12 + (index % 2) * max(245, self.width() // 2)
            painter.drawText(x, 280 + (index // 2) * 24, metric)


class TimingDiagram(QtWidgets.QWidget):
    """Draw the live relationships between preparation and acquisition events."""

    def __init__(self, parent=None):
        """Initialize an empty timing diagram using the current Qt palette."""
        super().__init__(parent)
        self._values = {}
        self.setMinimumHeight(420)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )

    def set_values(self, values):
        """Replace displayed configuration values and schedule a repaint."""
        self._values = dict(values)
        self.update()

    def timing_snapshot(self):
        """Return derived event times used by painting and GUI regression tests."""

        def value(name, default=0):
            return float(self._values.get(name, default))

        pulse_start = value("start_ppg")
        pulse_frequency = max(1.0, value("pulse_freq", 1))
        pulse_duration = value("num_pulses") * 1e6 / pulse_frequency
        sample_start = value("start_adcsampl")
        sampling_frequency = max(1.0, value("sampling_freq", 1))
        sample_duration = value("num_samples") * 1e6 / sampling_frequency
        return {
            "adc_on": value("turnon_adc"),
            "pga_bias": value("start_pgainbias"),
            "pulse_start": pulse_start,
            "pulse_end": pulse_start + pulse_duration,
            "mux_rx": value("start_hvmuxrx"),
            "mux_tx_interval": (0, value("start_hvmuxrx")),
            "mux_rx_interval": (value("start_hvmuxrx"), sample_start + sample_duration),
            "sample_start": sample_start,
            "sample_end": sample_start + sample_duration,
        }

    def _draw_track(self, painter, label, y, start, end, to_x, color):
        """Draw one active interval with its label and boundary ticks."""
        painter.setPen(self.palette().color(QtGui.QPalette.Text))
        painter.drawText(8, y + 5, label)
        x1, x2 = to_x(start), to_x(end)
        painter.setPen(QtGui.QPen(color, 2))
        painter.drawLine(x1, y, x2, y)
        painter.drawLine(x1, y - 6, x1, y + 6)
        painter.drawLine(x2, y - 6, x2, y + 6)

    def paintEvent(self, event):
        """Paint a detailed microsecond timeline and a broken-scale DC-DC cue."""
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().color(QtGui.QPalette.Base))
        if not self._values:
            return
        times = self.timing_snapshot()
        text = self.palette().color(QtGui.QPalette.Text)
        muted = self.palette().color(QtGui.QPalette.Mid)
        accent = QtGui.QColor("#228be6")
        orange = QtGui.QColor("#f08c00")
        green = QtGui.QColor("#2f9e44")
        purple = QtGui.QColor("#9c36b5")
        left, right = 116, max(150, self.width() - 20)
        detail_end = max(
            times["pulse_end"],
            times["mux_rx"],
            times["sample_end"],
            times["adc_on"],
            times["pga_bias"],
            1.0,
        )
        detail_end = max(10.0, detail_end * 1.08)

        def to_x(value):
            return int(left + max(0.0, value) / detail_end * (right - left))

        painter.setPen(text)
        painter.setFont(QtGui.QFont(painter.font().family(), -1, QtGui.QFont.Bold))
        painter.drawText(8, 22, "Acquisition timing (µs from sequencer start)")
        painter.setFont(QtGui.QFont(painter.font().family(), -1, QtGui.QFont.Normal))
        tracks = (
            ("ADC powered", times["adc_on"], detail_end, 88, accent),
            ("PGA bias", times["pga_bias"], detail_end, 126, purple),
            ("MUX: TX config", *times["mux_tx_interval"], 164, orange),
            ("MUX: RX config", *times["mux_rx_interval"], 202, green),
            ("ADC capture", times["sample_start"], times["sample_end"], 278, accent),
        )
        for label, start, end, y, color in tracks:
            self._draw_track(painter, label, y, start, end, to_x, color)

        y = 240
        painter.setPen(text)
        painter.drawText(8, y + 5, "Pulser output")
        pulse_start, pulse_end = times["pulse_start"], times["pulse_end"]
        count = max(0, int(self._values.get("num_pulses", 0)))
        points = [QtCore.QPointF(to_x(pulse_start), y)]
        if count:
            half_period = (pulse_end - pulse_start) / (2 * count)
            for edge in range(2 * count + 1):
                x = to_x(pulse_start + edge * half_period)
                points.append(QtCore.QPointF(x, y - 10 if edge % 2 else y))
        points.append(QtCore.QPointF(to_x(pulse_end), y))
        painter.setPen(QtGui.QPen(orange, 2))
        painter.drawPolyline(QtGui.QPolygonF(points))

        axis_y = 316
        painter.setPen(QtGui.QPen(muted, 1))
        painter.drawLine(left, axis_y, right, axis_y)
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            x = int(left + fraction * (right - left))
            painter.drawLine(x, axis_y - 4, x, axis_y + 4)
            painter.setPen(text)
            painter.drawText(x - 18, axis_y + 20, f"{detail_end * fraction:.0f}")
            painter.setPen(QtGui.QPen(muted, 1))

        metrics = (
            f"MUX config switch − pulse start: {times['mux_rx'] - pulse_start:+.1f} µs",
            f"ADC warm-up: {times['sample_start'] - times['adc_on']:+.1f} µs",
            f"ADC start − pulse end: {times['sample_start'] - pulse_end:+.1f} µs",
            f"Capture window: {times['sample_end'] - times['sample_start']:.1f} µs",
        )
        painter.setPen(text)
        for index, metric in enumerate(metrics):
            x = 12 + (index % 2) * max(250, self.width() // 2)
            painter.drawText(x, 364 + (index // 2) * 28, metric)


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
        parameter_by_name = {
            param.config_name: param
            for section in configuration_package
            for param in section
        }
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
        for name in HIDDEN_PARAMETERS:
            self.inputs[name].setParent(self)
            self.inputs[name].hide()
        self.inputs["num_samples"].setEnabled(False)
        self.inputs["num_samples"].setToolTip(
            "The firmware capture length is fixed; this value cannot be edited."
        )
        self.settings_tabs = QtWidgets.QTabWidget()
        split.addWidget(self.settings_tabs)

        acquisition = QtWidgets.QWidget()
        acquisition_layout = QtWidgets.QHBoxLayout(acquisition)
        acquisition_controls = QtWidgets.QWidget()
        acquisition_controls_layout = QtWidgets.QVBoxLayout(acquisition_controls)
        acquisition_controls_layout.setContentsMargins(0, 0, 0, 0)
        acquisition_visuals = QtWidgets.QWidget()
        acquisition_visuals_layout = QtWidgets.QVBoxLayout(acquisition_visuals)
        acquisition_visuals_layout.setContentsMargins(0, 0, 0, 0)
        acquisition_parameters = QtWidgets.QGroupBox("Acquisition settings")
        acquisition_form = QtWidgets.QFormLayout(acquisition_parameters)
        for name in ACQUISITION_PARAMETERS:
            param = parameter_by_name[name]
            acquisition_form.addRow(
                LABEL_OVERRIDES.get(name, param.friendly_name), self.inputs[name]
            )
        acquisition_controls_layout.addWidget(acquisition_parameters)
        self.tx_masks = [0xFFFF] + [0] * 15
        self.rx_masks = [0xFFFF] + [0] * 15
        self.cards = {}
        self.selected_config = 0
        self.inputs["num_txrx_configs"].valueChanged.connect(self._mask_count)
        mask_box = QtWidgets.QWidget()
        mask_layout = QtWidgets.QVBoxLayout(mask_box)
        mask_count_param = parameter_by_name["num_txrx_configs"]
        self.txrx_toolbar = QtWidgets.QWidget()
        txrx_toolbar_layout = QtWidgets.QHBoxLayout(self.txrx_toolbar)
        txrx_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        txrx_toolbar_layout.addWidget(QtWidgets.QLabel(mask_count_param.friendly_name))
        txrx_toolbar_layout.addWidget(self.inputs["num_txrx_configs"])
        txrx_toolbar_layout.addSpacing(12)
        self.add_config_button = QtWidgets.QPushButton("+ Add")
        self.edit_config_button = QtWidgets.QPushButton("Edit")
        self.remove_config_button = QtWidgets.QPushButton("− Remove")
        self.load_txrx_button = QtWidgets.QPushButton("Load TX/RX file…")
        self.save_txrx_button = QtWidgets.QPushButton("Save TX/RX file…")
        self.add_config_button.clicked.connect(self.add_config)
        self.edit_config_button.clicked.connect(self.edit_config)
        self.remove_config_button.clicked.connect(self.remove_config)
        self.load_txrx_button.clicked.connect(self.load_tx_rx)
        self.save_txrx_button.clicked.connect(self.save_tx_rx)
        txrx_toolbar_layout.addWidget(self.add_config_button)
        txrx_toolbar_layout.addWidget(self.edit_config_button)
        txrx_toolbar_layout.addWidget(self.remove_config_button)
        txrx_toolbar_layout.addSpacing(12)
        txrx_toolbar_layout.addWidget(self.load_txrx_button)
        txrx_toolbar_layout.addWidget(self.save_txrx_button)
        txrx_toolbar_layout.addStretch()
        mask_layout.addWidget(self.txrx_toolbar)
        mask_layout.addWidget(QtWidgets.QLabel("TX/RX configurations (channels 0–15)"))
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        self.card_layout = QtWidgets.QVBoxLayout(content)
        self.card_layout.setContentsMargins(2, 2, 2, 2)
        self.card_layout.addStretch()
        scroll.setWidget(content)
        mask_layout.addWidget(scroll, 1)
        cycle_group = QtWidgets.QGroupBox("Live acquisition cycle")
        cycle_layout = QtWidgets.QVBoxLayout(cycle_group)
        self.acquisition_cycle = AcquisitionCyclePreview()
        cycle_layout.addWidget(self.acquisition_cycle)
        acquisition_visuals_layout.addWidget(cycle_group)
        gain_parameters = QtWidgets.QGroupBox("Gain settings")
        gain_form = QtWidgets.QFormLayout(gain_parameters)
        for name in GAIN_PARAMETERS:
            param = parameter_by_name[name]
            gain_form.addRow(param.friendly_name, self.inputs[name])
        acquisition_controls_layout.addWidget(gain_parameters)
        acquisition_controls_layout.addStretch()
        gain_profile_group = QtWidgets.QGroupBox("Live gain profile")
        gain_profile_layout = QtWidgets.QVBoxLayout(gain_profile_group)
        self.gain_profile = GainProfilePreview()
        gain_profile_layout.addWidget(self.gain_profile)
        acquisition_visuals_layout.addWidget(gain_profile_group, 1)
        acquisition_layout.addWidget(acquisition_controls, 2)
        acquisition_layout.addWidget(acquisition_visuals, 3)
        self.settings_tabs.addTab(acquisition, "Acquisition")

        excitation = QtWidgets.QWidget()
        excitation_layout = QtWidgets.QHBoxLayout(excitation)
        excitation_controls = QtWidgets.QWidget()
        excitation_controls_layout = QtWidgets.QVBoxLayout(excitation_controls)
        excitation_group = QtWidgets.QGroupBox("Pulse generation")
        excitation_form = QtWidgets.QFormLayout(excitation_group)
        for name in EXCITATION_PARAMETERS:
            param = parameter_by_name[name]
            excitation_form.addRow(param.friendly_name, self.inputs[name])
        excitation_controls_layout.addWidget(excitation_group)
        excitation_note = QtWidgets.QLabel(
            "The pulser uses a 50% duty cycle. Pulse duration is derived from "
            "pulse frequency and pulse count and is reflected in Advanced timing."
        )
        excitation_note.setWordWrap(True)
        excitation_controls_layout.addWidget(excitation_note)
        excitation_controls_layout.addStretch()
        excitation_layout.addWidget(excitation_controls, 2)
        pulse_group = QtWidgets.QGroupBox("Live pulse preview")
        pulse_layout = QtWidgets.QVBoxLayout(pulse_group)
        self.pulse_preview = PulsePreview()
        pulse_layout.addWidget(self.pulse_preview)
        excitation_layout.addWidget(pulse_group, 3)
        self.settings_tabs.addTab(excitation, "Excitation")
        self.settings_tabs.addTab(mask_box, "TX/RX")

        advanced = QtWidgets.QWidget()
        advanced_layout = QtWidgets.QHBoxLayout(advanced)
        advanced_parameters = QtWidgets.QWidget()
        advanced_form = QtWidgets.QFormLayout(advanced_parameters)
        for name in ADVANCED_PARAMETERS:
            param = parameter_by_name[name]
            advanced_form.addRow(param.friendly_name, self.inputs[name])
        advanced_scroll = QtWidgets.QScrollArea()
        advanced_scroll.setWidgetResizable(True)
        advanced_scroll.setWidget(advanced_parameters)
        advanced_scroll.setMinimumWidth(390)
        advanced_layout.addWidget(advanced_scroll, 2)
        timing_group = QtWidgets.QGroupBox("Live event timing")
        timing_layout = QtWidgets.QVBoxLayout(timing_group)
        self.timing_diagram = TimingDiagram()
        timing_layout.addWidget(self.timing_diagram)
        timing_help = QtWidgets.QLabel(
            "The detailed axis starts when the ultrasound sequencer is triggered; "
            "event times are relative to that point. The slow measurement cycle "
            "and HV supply power-switch interval are shown under Acquisition."
        )
        timing_help.setWordWrap(True)
        timing_layout.addWidget(timing_help)
        advanced_layout.addWidget(timing_group, 3)
        self.settings_tabs.addTab(advanced, "Advanced")

        split.setCollapsible(0, False)
        split.setStretchFactor(0, 1)
        for widget in self.inputs.values():
            if isinstance(widget, QtWidgets.QComboBox):
                widget.currentIndexChanged.connect(self._update_timing)
            else:
                widget.valueChanged.connect(self._update_timing)
        self._mask_count(defaults["num_txrx_configs"])
        self._update_timing()

    def _update_timing(self, *_args):
        """Refresh timing and pulse previews after any parameter change."""
        values = self.values()
        if hasattr(self, "acquisition_cycle"):
            self.acquisition_cycle.set_values(values)
        if hasattr(self, "gain_profile"):
            self.gain_profile.set_values(values)
        if hasattr(self, "pulse_preview"):
            self.pulse_preview.set_values(values)
        if hasattr(self, "timing_diagram"):
            self.timing_diagram.set_values(values)

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
            if key == "num_samples":
                continue
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
