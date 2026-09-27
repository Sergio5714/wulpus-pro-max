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
"""

import asyncio
import io
from pathlib import Path
from typing import Optional, Tuple, Union

import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
from IPython.display import display
from scipy import signal as ss
from scipy.signal import hilbert


class WulpusProNpzViewer(widgets.VBox):
    """Interactive viewer for GUI- and profiler-generated WULPUS Pro Max NPZ files."""

    REQUIRED_ARRAYS = ("data_arr", "acq_num_arr", "tx_rx_id_arr")

    def __init__(self, filename: Optional[Union[str, Path]] = None):
        self.data_arr = np.empty((0, 0), dtype="<i2")
        self.acq_num_arr = np.empty(0, dtype="<u2")
        self.tx_rx_id_arr = np.empty(0, dtype=np.uint8)
        self.filtered_indices = np.empty(0, dtype=np.intp)
        self.filename = ""

        self.upload = widgets.FileUpload(
            accept=".npz",
            multiple=False,
            description="Select .npz",
        )
        self.path = widgets.Text(
            description="File path:",
            placeholder="path/to/acquisition.npz",
            layout=widgets.Layout(width="70%"),
            style={"description_width": "initial"},
        )
        self.load_button = widgets.Button(description="Load path")
        self.config = widgets.Dropdown(
            description="TX/RX config:",
            disabled=True,
            style={"description_width": "initial"},
        )
        self.acquisition = widgets.IntSlider(
            description="Acquisition:",
            min=0,
            max=0,
            value=0,
            continuous_update=False,
            disabled=True,
            readout=True,
            layout=widgets.Layout(width="75%"),
            style={"description_width": "initial"},
        )
        self.sample_rate = widgets.BoundedFloatText(
            value=8.0, min=0.5, max=100.0, step=0.1,
            description="Sampling (MHz):",
            style={"description_width": "initial"},
        )
        self.band_pass = widgets.FloatRangeSlider(
            value=(0.4, 3.6), min=0.2, max=3.8, step=0.1,
            description="Band pass (MHz):", continuous_update=False,
            readout_format=".1f", layout=widgets.Layout(width="65%"),
            style={"description_width": "initial"},
        )
        self.show_raw = widgets.Checkbox(value=True, description="Raw")
        self.show_filtered = widgets.Checkbox(value=False, description="Filtered")
        self.show_envelope = widgets.Checkbox(value=False, description="Envelope")
        self.replay_fps = widgets.BoundedFloatText(
            value=20.0,
            min=0.1,
            max=500.0,
            step=1.0,
            description="Replay FPS:",
            style={"description_width": "initial"},
        )
        self.replay_button = widgets.Button(
            description="Replay", icon="play", button_style="success"
        )
        self.stop_button = widgets.Button(
            description="Stop", icon="stop", button_style="danger", disabled=True
        )
        self._replay_task = None
        self._replay_ylim = None
        self.file_info = widgets.HTML(value="No acquisition file loaded")
        self.frame_info = widgets.HTML(value="")
        self.message = widgets.HTML(value="")
        # Prevent pyplot from automatically displaying a second figure when
        # `%matplotlib widget` is active. The live canvas is embedded directly
        # in this viewer below.
        with plt.ioff():
            self.figure, self.axis = plt.subplots(figsize=(9, 4))
        (self.raw_line,) = self.axis.plot(
            [], [], color="tab:blue", linewidth=1, label="Raw"
        )
        (self.filtered_line,) = self.axis.plot(
            [], [], color="tab:green", linewidth=1.2, label="Filtered"
        )
        (self.envelope_line,) = self.axis.plot(
            [], [], color="tab:red", linewidth=1.2, label="Envelope"
        )
        self.axis.set_title("WULPUS Pro Max acquisition")
        self.axis.set_xlabel("Sample")
        self.axis.set_ylabel("ADC code")
        self.axis.grid(True, alpha=0.3)
        self.axis.legend(loc="upper right")
        if isinstance(self.figure.canvas, widgets.Widget):
            self.plot_widget = self.figure.canvas
        else:
            self.plot_widget = widgets.Output()
            with self.plot_widget:
                display(self.figure)

        controls = widgets.HBox([self.upload, self.path, self.load_button])
        selectors = widgets.HBox([self.config, self.acquisition])
        signal_controls = widgets.HBox(
            [self.show_raw, self.show_filtered, self.show_envelope,
             self.sample_rate]
        )
        replay_controls = widgets.HBox(
            [self.replay_fps, self.replay_button, self.stop_button]
        )
        super().__init__(
            [controls, self.message, self.file_info, selectors,
             replay_controls, signal_controls, self.band_pass,
             self.frame_info, self.plot_widget]
        )

        self.upload.observe(self._on_upload, names="value")
        self.load_button.on_click(self._on_load_path)
        self.config.observe(self._on_config_changed, names="value")
        self.acquisition.observe(self._on_acquisition_changed, names="value")
        self.sample_rate.observe(self._on_sample_rate_changed, names="value")
        self.band_pass.observe(self._on_signal_controls_changed, names="value")
        self.show_raw.observe(self._on_signal_controls_changed, names="value")
        self.show_filtered.observe(self._on_signal_controls_changed, names="value")
        self.show_envelope.observe(self._on_signal_controls_changed, names="value")
        self.replay_button.on_click(self._on_replay)
        self.stop_button.on_click(self._on_stop)

        if filename is not None:
            self.path.value = str(filename)
            self.load(filename)

    @staticmethod
    def _validate_arrays(
        data_arr: np.ndarray,
        acq_num_arr: np.ndarray,
        tx_rx_id_arr: np.ndarray,
    ) -> None:
        if data_arr.ndim != 2:
            raise ValueError("data_arr must be a two-dimensional samples-by-frames array")
        if acq_num_arr.ndim != 1 or tx_rx_id_arr.ndim != 1:
            raise ValueError("acq_num_arr and tx_rx_id_arr must be one-dimensional")
        frame_count = data_arr.shape[1]
        if len(acq_num_arr) != frame_count or len(tx_rx_id_arr) != frame_count:
            raise ValueError(
                "metadata lengths must match the number of data_arr columns"
            )

    @classmethod
    def _read_npz(cls, source) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        with np.load(source, allow_pickle=False) as archive:
            missing = [name for name in cls.REQUIRED_ARRAYS if name not in archive]
            if missing:
                raise ValueError(f"missing required NPZ arrays: {', '.join(missing)}")
            data_arr = np.asarray(archive["data_arr"])
            acq_num_arr = np.asarray(archive["acq_num_arr"])
            tx_rx_id_arr = np.asarray(archive["tx_rx_id_arr"])
        cls._validate_arrays(data_arr, acq_num_arr, tx_rx_id_arr)
        return data_arr, acq_num_arr, tx_rx_id_arr

    def load(self, filename: Union[str, Path]) -> None:
        """Load an NPZ file available on the Jupyter server filesystem."""
        path = Path(filename).expanduser()
        arrays = self._read_npz(path)
        self.path.value = str(path)
        self._set_data(path.name, *arrays)

    def _set_data(
        self,
        filename: str,
        data_arr: np.ndarray,
        acq_num_arr: np.ndarray,
        tx_rx_id_arr: np.ndarray,
    ) -> None:
        self._cancel_replay()
        self.filename = filename
        self.data_arr = data_arr
        self.acq_num_arr = acq_num_arr
        self.tx_rx_id_arr = tx_rx_id_arr
        self.message.value = ""

        configs, counts = np.unique(tx_rx_id_arr, return_counts=True)
        options = [("All configurations", None)]
        options.extend(
            (f"Config {int(config)} ({int(count)} frames)", int(config))
            for config, count in zip(configs, counts)
        )
        self.config.options = options
        self.config.disabled = len(tx_rx_id_arr) == 0
        self.config.value = None
        self.file_info.value = (
            f"<b>{filename}</b> &mdash; {data_arr.shape[1]} frames, "
            f"{data_arr.shape[0]} samples/frame, {len(configs)} configurations"
        )
        self._update_filter()

    def _update_filter(self) -> None:
        selected_config = self.config.value
        if selected_config is None:
            self.filtered_indices = np.arange(self.data_arr.shape[1], dtype=np.intp)
        else:
            self.filtered_indices = np.flatnonzero(
                self.tx_rx_id_arr == selected_config
            )

        count = len(self.filtered_indices)
        self.acquisition.disabled = count == 0
        self.acquisition.max = max(0, count - 1)
        self.acquisition.value = 0
        self.acquisition.description = f"Acquisition (of {count}):"
        self._update_plot()

    def _update_plot(self) -> None:
        if not len(self.filtered_indices):
            self.raw_line.set_data([], [])
            self.filtered_line.set_data([], [])
            self.envelope_line.set_data([], [])
            self.frame_info.value = "No acquisitions match this configuration"
            self.figure.canvas.draw_idle()
            return

        filtered_position = self.acquisition.value
        frame_index = int(self.filtered_indices[filtered_position])
        samples = self.data_arr[:, frame_index]
        acquisition_number = int(self.acq_num_arr[frame_index])
        config_id = int(self.tx_rx_id_arr[frame_index])

        sample_indices = np.arange(len(samples))
        self.raw_line.set_data(sample_indices, samples)
        self.raw_line.set_visible(self.show_raw.value)
        self.filtered_line.set_visible(self.show_filtered.value)
        self.envelope_line.set_visible(self.show_envelope.value)

        filtered = None
        envelope = None
        if self.show_filtered.value or self.show_envelope.value:
            try:
                filtered = self._filter_data(samples)
                envelope = np.abs(hilbert(filtered))
                self.message.value = ""
            except ValueError as exc:
                self.message.value = (
                    "<span style='color:#b00020'>Signal processing failed: "
                    f"{exc}</span>"
                )
        self.filtered_line.set_data(
            sample_indices if filtered is not None else [],
            filtered if filtered is not None else [],
        )
        self.envelope_line.set_data(
            sample_indices if envelope is not None else [],
            envelope if envelope is not None else [],
        )
        self.axis.set_xlim(0, max(1, len(samples) - 1))
        visible_data = []
        if self.show_raw.value:
            visible_data.append(samples)
        if filtered is not None and self.show_filtered.value:
            visible_data.append(filtered)
        if envelope is not None and self.show_envelope.value:
            visible_data.append(envelope)
        if self._replay_ylim is not None:
            self.axis.set_ylim(self._replay_ylim)
        elif visible_data:
            data_min = min(float(np.min(values)) for values in visible_data)
            data_max = max(float(np.max(values)) for values in visible_data)
            margin = max(1.0, (data_max - data_min) * 0.05)
            self.axis.set_ylim(data_min - margin, data_max + margin)
        self.axis.set_title(
            f"Frame {frame_index} | acquisition {acquisition_number} | config {config_id}"
        )
        self.frame_info.value = (
            f"File frame: <b>{frame_index}</b>; acquisition number: "
            f"<b>{acquisition_number}</b>; TX/RX config: <b>{config_id}</b>"
        )
        self.figure.canvas.draw_idle()

    def _filter_data(self, samples: np.ndarray) -> np.ndarray:
        sampling_hz = self.sample_rate.value * 1e6
        low_hz, high_hz = (value * 1e6 for value in self.band_pass.value)
        transition_hz = 0.2e6
        coefficients = ss.remez(
            31,
            [0, low_hz - transition_hz, low_hz, high_hz,
             high_hz + transition_hz, sampling_hz / 2],
            [0, 1, 0],
            Hz=sampling_hz,
            maxiter=2500,
        )
        return ss.filtfilt(coefficients, 1, samples)

    def _on_config_changed(self, change) -> None:
        if change.get("name") == "value":
            self._cancel_replay()
            self._update_filter()

    def _on_acquisition_changed(self, change) -> None:
        if change.get("name") == "value":
            self._update_plot()

    def _on_sample_rate_changed(self, change) -> None:
        if change.get("name") != "value":
            return
        transition_mhz = 0.2
        maximum = max(transition_mhz, change["new"] / 2 - transition_mhz)
        low, high = self.band_pass.value
        low = min(max(transition_mhz, low), maximum)
        high = min(max(low, high), maximum)
        self.band_pass.value = (low, high)
        self.band_pass.max = maximum
        self._update_plot()

    def _on_signal_controls_changed(self, change) -> None:
        if change.get("name") == "value":
            self._update_plot()

    def _on_replay(self, _button) -> None:
        if self.acquisition.disabled:
            return
        self._cancel_replay()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self.message.value = (
                "<span style='color:#b00020'>Replay requires a running "
                "Jupyter event loop</span>"
            )
            return
        self.message.value = ""
        self.replay_button.disabled = True
        self.stop_button.disabled = False
        self._replay_ylim = self.axis.get_ylim()
        self._replay_task = loop.create_task(self._replay())

    async def _replay(self) -> None:
        task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        period = 1.0 / self.replay_fps.value
        next_frame_time = loop.time()
        start = self.acquisition.value
        try:
            for position in range(start, self.acquisition.max + 1):
                self.acquisition.value = position
                next_frame_time += period
                await asyncio.sleep(max(0.0, next_frame_time - loop.time()))
        except asyncio.CancelledError:
            pass
        finally:
            if self._replay_task is task:
                self._replay_task = None
                self._replay_ylim = None
                self.replay_button.disabled = False
                self.stop_button.disabled = True

    def _cancel_replay(self) -> None:
        task = self._replay_task
        self._replay_task = None
        if task is not None and not task.done():
            task.cancel()
        self._replay_ylim = None
        self.replay_button.disabled = False
        self.stop_button.disabled = True

    def _on_stop(self, _button) -> None:
        self._cancel_replay()

    def close(self) -> None:
        self._cancel_replay()
        plt.close(self.figure)
        super().close()

    def _on_load_path(self, _button) -> None:
        try:
            self.load(self.path.value)
        except (OSError, ValueError) as exc:
            self.message.value = f"<span style='color:#b00020'>Could not load file: {exc}</span>"

    def _on_upload(self, change) -> None:
        value = change.get("new")
        if not value:
            return
        try:
            if isinstance(value, dict):
                filename, item = next(iter(value.items()))
                content = item["content"]
            else:
                item = value[0]
                filename = item["name"]
                content = item["content"]
            arrays = self._read_npz(io.BytesIO(bytes(content)))
            self._set_data(filename, *arrays)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.message.value = f"<span style='color:#b00020'>Could not load file: {exc}</span>"
