"""
Copyright (C) 2026 ETH Zurich. All rights reserved.
Author: Sergei Vostrikov, ETH Zurich
        Cedric Hirschi, ETH Zurich
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

from scipy import signal as ss
from scipy.signal import hilbert
import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
import time
from threading import Thread
import os.path
import logging
from collections.abc import Mapping
from typing import Any, Optional, Protocol, Sequence, Union

from .wifi_link import WulpusProWiFiBusy, WulpusProWiFiError


class WulpusProCommunicationLink(Protocol):
    """Communication operations required by :class:`WulpusGuiSingleCh`."""

    acq_length: int

    def get_available(self) -> Sequence[Any]: ...

    def open(self, device: Optional[Any] = None) -> bool: ...

    def close(self) -> bool: ...

    def send_acq_config(self, conf_bytes_pack: bytes) -> Any: ...

    def receive_data(self) -> Any: ...

    def toggle_rx(self, state: bool) -> Any: ...

    def reset_msp(self) -> Any: ...

    def get_status(self, timeout: float = 5.0) -> Any: ...

    def get_firmware_info(self, timeout: float = 5.0) -> Any: ...

    def clear_status(
        self,
        error_mask: int = 0xFFFFFFFF,
        clear_counters: bool = False,
        timeout: float = 5.0,
    ) -> Any: ...

# plt.ioff()

V_TISSUE = 1540  # m/s

LOWER_BOUNDS_MM = 7  # data below this depth will be discarded

LINE_N_SAMPLES = 400

FILE_NAME_BASE = "data_"

GAIN_PLOT_LOW_Y_MARGIN_DB = 20

PROGRESS_UPDATE_PERIOD_S = 0.1

STATUS_ERROR_NAMES = {
    1 << 0: "acquisition buffer overflow",
    1 << 1: "data-ready overflow",
    1 << 2: "SPI timeout",
    1 << 3: "SPI failure",
    1 << 4: "link timeout",
    1 << 5: "link disconnected",
    1 << 6: "protocol error",
}

box_layout = widgets.Layout(
    display="flex", flex_flow="column", align_items="center", width="50%"
)

# Grab the logger you use in this file (e.g. “WiFi” in your __init__)
gui_logger = logging.getLogger("GUI ")
gui_logger.setLevel(logging.DEBUG)
# Prevent messages from bubbling up to the root logger
gui_logger.propagate = False

# Create and attach a FileHandler just for this logger
file_handler = logging.FileHandler("wulpus.log")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s\t%(name)s\t%(funcName)s\t%(levelname)s\t%(message)s",
    "%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(formatter)
gui_logger.addHandler(file_handler)


class WulpusGuiSingleCh(widgets.VBox):
    def __init__(
        self,
        com_link: Union[
            WulpusProCommunicationLink,
            Mapping[str, WulpusProCommunicationLink],
        ],
        uss_conf,
        max_vis_fps=20,
    ):
        super().__init__()
        self.log = gui_logger

        # Communication links. Passing one link preserves the original API;
        # passing a mapping enables transport selection in the GUI.
        if isinstance(com_link, Mapping):
            if not com_link:
                raise ValueError("At least one communication link is required")
            self.com_links = dict(com_link)
        else:
            self.com_links = {type(com_link).__name__: com_link}
        self.com_link = next(iter(self.com_links.values()))
        self.log.debug(f"Communication link: {self.com_link}")

        # Ultrasound Subsystem Configurator
        self.uss_conf = uss_conf
        self.com_link.acq_length = uss_conf.num_samples

        # Allocate memory to store the data and other parameters
        self.data_arr = np.zeros(
            (self.com_link.acq_length, uss_conf.num_acqs), dtype="<i2"
        )
        self.data_arr_bmode = np.zeros((uss_conf.num_txrx_configs, self.com_link.acq_length), dtype="<i2")
        self.acq_num_arr = np.zeros(uss_conf.num_acqs, dtype="<u2")
        self.tx_rx_id_arr = np.zeros(uss_conf.num_acqs, dtype=np.uint8)

        # For visualization FPS control
        self.vis_fps_period = 1 / max_vis_fps

        # Extra variables to control visualization
        self.rx_tx_conf_to_display = 0
        self.current_bmode_frame = None

        # For Signal Processing
        self.f_low_cutoff = self.uss_conf.sampling_freq / 2 * 0.1
        self.f_high_cutoff = self.uss_conf.sampling_freq / 2 * 0.9
        self.design_filter(
            self.uss_conf.sampling_freq, self.f_low_cutoff, self.f_high_cutoff
        )

        # Define widgets
        # Communication-device related
        self.transport_dd = widgets.Dropdown(
            options=list(self.com_links),
            value=next(iter(self.com_links)),
            description="Transport:",
            disabled=len(self.com_links) == 1,
            style={"description_width": "initial"},
        )

        self.ser_scan_button = widgets.Button(
            description="Scan devices",
            disabled=False,
            style={"description_width": "initial"},
        )

        self.ser_open_button = widgets.Button(description="Open device", disabled=True)

        self.port_opened = False
        self.opened_link = None
        self.acquisition_running = False

        devices = self.com_link.get_available()

        if len(devices) == 0:
            self.ports_dd = widgets.Dropdown(
                options=["No ports found"],
                value="No ports found",
                description="Device:",
                disabled=True,
                style={"description_width": "initial"},
            )
        else:
            self.ports_dd = widgets.Dropdown(
                options=[device.description for device in devices],
                value=devices[0].description,
                description="Device:",
                disabled=True,
                style={"description_width": "initial"},
            )
            self.click_scan_ports(self.ser_scan_button)

        # Visualization-related
        self.raw_data_check = widgets.Checkbox(
            value=True, description="Show Raw Data", disabled=True
        )

        self.filt_data_check = widgets.Checkbox(
            value=False, description="Show Filtered Data", disabled=True
        )

        self.env_data_check = widgets.Checkbox(
            value=False, description="Show Envelope", disabled=True
        )

        self.bmode_check = widgets.Checkbox(
            value=False, description="Show B-Mode", disabled=True
        )

        opt = [str(x) for x in range(self.uss_conf.num_txrx_configs)]
        self.tx_rx_sel_dd = widgets.Dropdown(
            options=opt,
            value=opt[0],
            description="Active RX config:",
            disabled=True,
            style={"description_width": "initial"},
        )

        self.band_pass_frs = widgets.FloatRangeSlider(
            value=[self.f_low_cutoff / 10**6, self.f_high_cutoff / 10**6],
            min=self.f_low_cutoff / 10**6,
            max=self.f_high_cutoff / 10**6,
            step=0.1,
            description="Band pass (MHz):",
            disabled=True,
            continuous_update=False,
            orientation="horizontal",
            readout=True,
            readout_format=".1f",
            style={"description_width": "initial"},
        )

        # Progress bar, Start and Stop button, save data checkbox and label
        self.frame_progr_bar = widgets.IntProgress(
            value=0,
            min=0,
            max=self.uss_conf.num_acqs,
            step=1,
            description="Progress:",
            bar_style="success",  # 'success', 'info', 'warning', 'danger' or ''
            orientation="horizontal",
            style={"description_width": "initial"},
        )

        self.start_stop_button = widgets.Button(
            description="Start measurement", disabled=True
        )

        self.reset_msp_button = widgets.Button(
            description="Reset MSP", disabled=True
        )

        self.save_data_check = widgets.Checkbox(
            value=True, description="Save Data as .npz", disabled=True
        )

        self.save_data_label = widgets.Label(value="")
        self.acquisition_status_label = widgets.Label(value="Status: Idle")
        self.firmware_version_label = widgets.Label(value="Firmware: not connected")

        # Setup Visualization
        self.output = widgets.Output()
        self.one_time_fig_config()

        # Construct GUI grid
        controls_1 = widgets.VBox(
            [
                self.raw_data_check,
                self.filt_data_check,
                self.env_data_check,
                self.bmode_check,
            ]
        )

        controls_2 = widgets.VBox(
            [
                self.transport_dd,
                widgets.HBox([self.ser_open_button, self.ser_scan_button]),
                self.firmware_version_label,
                self.ports_dd,
                self.tx_rx_sel_dd,
                self.band_pass_frs,
            ]
        )

        controls = widgets.HBox([controls_1, controls_2])

        out_box = widgets.Box([self.output])

        progr_ctl_box_1 = widgets.VBox(
            [
                self.start_stop_button,
                self.reset_msp_button,
                self.frame_progr_bar,
                self.acquisition_status_label,
            ]
        )
        progr_ctl_box_2 = widgets.VBox([self.save_data_check, self.save_data_label])
        progr_ctl_box = widgets.HBox([progr_ctl_box_1, progr_ctl_box_2])

        main_box = widgets.VBox([controls, out_box, progr_ctl_box])

        # Connect callbacks

        # To serial port related buttons
        self.transport_dd.observe(self.change_transport, "value")
        self.ser_scan_button.on_click(self.click_scan_ports)
        self.ser_open_button.on_click(self.click_open_port)

        # To checkboxes
        self.raw_data_check.observe(self.turn_on_off_raw_data_plot, "value")
        self.filt_data_check.observe(self.turn_on_off_filt_data_plot, "value")
        self.env_data_check.observe(self.turn_on_off_env_plot, "value")
        self.bmode_check.observe(self.toggle_bmode, "value")

        # To TX RX select dropdown
        self.tx_rx_sel_dd.observe(self.select_rx_conf_to_plot, "value")

        # To progress slider
        self.band_pass_frs.observe(self.update_band_pass_range, "value")

        # To start stop acqusition button
        self.start_stop_button.on_click(self.click_start_stop_acq)
        self.reset_msp_button.on_click(self.click_reset_msp)

        # add to children
        self.children = [main_box]

        self.log.debug("WulpusGUISingleCh initialized")

    def one_time_fig_config(self):
        with self.output:
            self.fig, self.ax = plt.subplots(
                constrained_layout=True, figsize=(8, 4), ncols=1, nrows=1
            )

        if self.bmode_check.value:
            self.setup_bmode_plot()
        else:
            self.setup_amode_plot()

        self.fig.canvas.toolbar_position = "bottom"

    def setup_amode_plot(self):
        self.ax.clear()

        (self.raw_data_line,) = self.ax.plot(
            np.zeros(LINE_N_SAMPLES),
            color="blue",
            marker="o",
            markersize=1,
            label="Raw data",
        )

        (self.filt_data_line,) = self.ax.plot(
            np.zeros(LINE_N_SAMPLES),
            color="green",
            marker="o",
            markersize=1,
            label="Filtered data",
        )

        (self.envelope_line,) = self.ax.plot(
            np.zeros(LINE_N_SAMPLES),
            color="red",
            marker="o",
            markersize=1,
            label="Envelope",
        )

        # Create secondary y-axis
        self.ax2 = self.ax.twinx()

        # Calculate the gain curve
        self.uss_conf.calc_gain_curve()

        # Plot on secondary y-axis
        (self.gain_curve,) = self.ax2.plot(
            self.uss_conf.gain_curve_db,
            color="black",
            linestyle="dashed",
            label="Gain curve",
            zorder=-10,
        )

        # Add legends from both axes
        lines = [
            self.raw_data_line,
            self.filt_data_line,
            self.envelope_line,
            self.gain_curve,
        ]
        labels = [line.get_label() for line in lines]

        # Set axes labels and title
        self.ax.set_xlabel("Samples")
        self.ax.set_ylabel("ADC digital code")
        self.ax2.set_ylabel("Gain [dB]")
        self.ax.set_title("A-mode data")

        self.filt_data_line.set_visible(self.filt_data_check.value)
        self.envelope_line.set_visible(self.env_data_check.value)

        self.ax.set_ylim(-3000, 3000)
        self.ax2.set_ylim(
            0 + self.uss_conf.rx_gain - GAIN_PLOT_LOW_Y_MARGIN_DB,
            80 + self.uss_conf.rx_gain,
        )

        # Add and elevate legend
        legend = self.ax.legend(lines, labels, loc="lower right", ncol=4)
        legend.get_frame().set_alpha(1.0)
        legend.set_zorder(10)

        self.ax.grid(True)

    def setup_bmode_plot(self):
        self.ax.clear()

        self.bmode_image = self.ax.imshow(np.zeros((self.uss_conf.num_txrx_configs, LINE_N_SAMPLES)), aspect="auto")

        self.ax.set_xlabel("Depth (mm)")
        self.ax.set_ylabel("Channel number")
        self.ax.set_title("B-mode data")
        # self.bmode_image.set_clim(0, 2)
        self.bmode_image.set_clim(0, 200)

        meas_time = LINE_N_SAMPLES / self.uss_conf.sampling_freq
        meas_depth = meas_time * V_TISSUE * 1000 / 2
        # self.bmode_image.set_extent((LOWER_BOUNDS_MM, meas_depth, 0.5, 7.5))
        # Subtracting 0.5 ensures the extent aligns with the center of the first and last channels,
        # which is a common adjustment for half-pixel offsets in plotting.
        self.bmode_image.set_extent((0, meas_depth, 0.5, self.uss_conf.num_txrx_configs - 0.5))
        self.ax.set_yticks(np.arange(0, self.uss_conf.num_txrx_configs, 1))

    # Callbacks

    def change_transport(self, change):
        """Select a communication link and scan its available devices."""
        if not change.new or change.new == change.old:
            return
        if self.port_opened:
            self.com_link.close()
            self.port_opened = False
            self.opened_link = None
            self.ser_open_button.description = "Open device"
            self.start_stop_button.disabled = True
            self.reset_msp_button.disabled = True
            self.firmware_version_label.value = "Firmware: not connected"

        self.com_link = self.com_links[change.new]
        self.com_link.acq_length = self.uss_conf.num_samples
        self.log.info(f"Communication transport changed to {change.new}")
        self.click_scan_ports(self.ser_scan_button)

    def click_scan_ports(self, b):
        self.log.info("Scanning ports...")

        # Update drop-down for ports and make it enabled
        self.found_devices = self.com_link.get_available()
        self.log.info(f"Found {len(self.found_devices)} devices")
        for device in self.found_devices:
            self.log.debug(f"Device: {device.description}")

        if len(self.found_devices) == 0:
            self.log.warning("No devices found")
            self.ports_dd.options = ["No ports found"]
            self.ports_dd.value = "No ports found"
            self.ports_dd.disabled = True
            self.ser_open_button.disabled = True
        else:
            self.ports_dd.options = [
                device.description for device in self.found_devices
            ]
            self.ports_dd.value = self.found_devices[0].description
            self.ports_dd.disabled = False
            self.ser_open_button.disabled = False

        self.log.debug("Done scanning ports")

    def click_open_port(self, b):
        self.log.info("Opening/Closing port...")

        if not self.port_opened and len(self.ports_dd.options) > 0:
            self.log.info("Opening port")

            device = self.found_devices[self.ports_dd.index]

            if not self.com_link.open(device):
                b.description = "Open device"
                self.port_opened = False
                self.opened_link = None
                self.start_stop_button.disabled = True
                self.reset_msp_button.disabled = True
                self.log.error("Port not opened")
                return

            b.description = "Close device"
            self.port_opened = True
            self.opened_link = self.com_link
            self.start_stop_button.disabled = False
            self.reset_msp_button.disabled = not hasattr(self.com_link, "reset_msp")
            self.transport_dd.disabled = True

            self.update_firmware_version()

            self.log.debug("Port opened")

        else:
            self.log.info("Closing port")

            self.com_link.close()
            b.description = "Open device"
            self.port_opened = False
            self.opened_link = None
            self.start_stop_button.disabled = True
            self.reset_msp_button.disabled = True
            self.transport_dd.disabled = len(self.com_links) == 1
            self.firmware_version_label.value = "Firmware: not connected"

            self.log.debug("Port closed")

    def update_firmware_version(self):
        """Read and display firmware versions when supported by the transport."""
        if not hasattr(self.com_link, "get_firmware_info"):
            self.firmware_version_label.value = "Firmware: unavailable"
            return
        try:
            info = self.com_link.get_firmware_info(timeout=2.0)
            msp_version = info.msp_version or "unknown (configure device to detect)"
            self.firmware_version_label.value = (
                f"Firmware: ESP32 {info.esp_version}; MSP430 {msp_version}"
            )
        except Exception as exc:
            self.firmware_version_label.value = "Firmware: unavailable"
            self.log.warning("Could not read firmware versions: %s", exc)

    def turn_on_off_raw_data_plot(self, change):
        self.raw_data_line.set_visible(change.new)

    def turn_on_off_filt_data_plot(self, change):
        self.filt_data_line.set_visible(change.new)

    def turn_on_off_env_plot(self, change):
        self.envelope_line.set_visible(change.new)

    def toggle_bmode(self, change):
        if change.new:
            self.setup_bmode_plot()
            self.tx_rx_sel_dd.disabled = True
        else:
            self.setup_amode_plot()
            self.tx_rx_sel_dd.disabled = False

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def select_rx_conf_to_plot(self, change):
        self.rx_tx_conf_to_display = int(change.new)

    def update_band_pass_range(self, change):
        self.design_filter(
            self.uss_conf.sampling_freq, change.new[0] * 10**6, change.new[1] * 10**6
        )

    def click_reset_msp(self, _button):
        """Reset the MSP430, stopping stale firmware acquisition if necessary."""
        self.log.info("Resetting MSP430")
        self.reset_msp_button.disabled = True
        self.acquisition_status_label.value = "Status: Resetting MSP430"
        try:
            try:
                self.com_link.reset_msp()
            except WulpusProWiFiBusy:
                self.log.info("MSP430 reset was busy; sending STOP_RX and retrying")
                self.com_link.toggle_rx(False)
                self.com_link.reset_msp()
            self.acquisition_status_label.value = "Status: MSP430 reset"
            self.log.info("MSP430 reset complete")
        except Exception as exc:
            self.acquisition_status_label.value = "Status: MSP430 reset failed"
            self.log.exception("Could not reset MSP430: %s", exc)
        finally:
            self.reset_msp_button.disabled = (
                not self.port_opened
                or self.acquisition_running
                or not hasattr(self.com_link, "reset_msp")
            )

    def click_start_stop_acq(self, b):
        self.log.info("Start/Stop acquisition")

        if not self.acquisition_running:
            self.log.info("Starting acquisition")
            # Enable the widgets active during acquisition
            self.raw_data_check.disabled = False
            self.filt_data_check.disabled = False
            self.env_data_check.disabled = False
            self.bmode_check.disabled = False
            self.tx_rx_sel_dd.disabled = False
            self.band_pass_frs.disabled = False
            self.save_data_check.disabled = False

            # Disable serial port related widgets
            self.ser_open_button.disabled = True
            self.reset_msp_button.disabled = True

            # Clean Save data label
            self.save_data_label.value = ""

            # Change state of the button
            b.description = "Stop measurement"

            # Declare that acquisition is running
            self.acquisition_running = True

            # Run data acquisition loop
            self.log.info("Starting acquisition thread")
            self.current_data = None
            self.acquisition_thread = Thread(target=self.run_acquisition_loop)
            self.acquisition_thread.start()

            self.log.debug("Acquisition started")
        else:
            self.log.info("Stopping acquisition")

            # Stop acquisition, thread will stop by itself
            self.acquisition_running = False

            # Change state of the button
            b.description = "Start measurement"

            # Disable the widgets when not acquiring
            self.raw_data_check.disabled = True
            self.filt_data_check.disabled = True
            self.env_data_check.disabled = True
            self.bmode_check.disabled = True
            self.tx_rx_sel_dd.disabled = True
            self.band_pass_frs.disabled = True
            self.save_data_check.disabled = True

            # The acquisition thread still owns the transport while it sends
            # STOP_RX and performs cleanup. It re-enables these controls when
            # that work has actually finished.

            self.log.debug("Acquisition stopped")

    def run_acquisition_loop(self):
        """Run acquisition and keep transport failures inside the GUI thread."""
        try:
            self._run_acquisition_loop()
        except Exception as exc:
            self.log.exception("Acquisition failed on the selected transport")
            self.acquisition_running = False
            self.visualize = False
            self.acquisition_status_label.value = f"Status: Acquisition failed: {exc}"
            self.save_data_label.value = str(exc)
            self.start_stop_button.description = "Start measurement"
            self.ser_open_button.disabled = not self.port_opened
            self.reset_msp_button.disabled = (
                not self.port_opened
                or self.opened_link is None
                or not hasattr(self.opened_link, "reset_msp")
            )

    def _run_acquisition_loop(self):
        if not self.port_opened or self.opened_link is None:
            raise RuntimeError("No communication device is open")
        # Use the exact link that was opened. The visible transport selector
        # cannot redirect a running acquisition to another link instance.
        self.com_link = self.opened_link
        #         self.fig.show()
        self.log.info("Acquisition thread started")

        # Clean data buffer
        acq_length = self.com_link.acq_length
        number_of_acq = self.uss_conf.num_acqs
        self.data_arr = np.zeros((acq_length, number_of_acq), dtype="<i2")
        self.acq_num_arr = np.zeros(number_of_acq, dtype="<u2")
        self.tx_rx_id_arr = np.zeros(number_of_acq, dtype=np.uint8)
        # Acquisition counter
        self.data_cnt = 0
        next_progress_update = time.monotonic()
        self.acquisition_status_label.value = "Status: Preparing acquisition"
        self.log.debug("Data buffer cleaned")

        # Send TX stop
        self.log.info("Sending RX stop command")
        self.com_link.toggle_rx(False)
        self.log.debug("RX stop command sent")

        # Send a restart command (if system is already running)
        self.log.info("Sending restart command")
        self.com_link.send_acq_config(self.uss_conf.get_restart_package())
        self.log.debug("Restart command sent")

        # Wait 2.5 seconds (much larger than max measurement period = 2s)
        self.log.debug("Waiting for 2.5 seconds")
        time.sleep(2.5)

        # Generate and send a configuration package
        try:
            self.log.info("Sending configuration package")
            self.com_link.send_acq_config(self.uss_conf.get_conf_package())
            self.update_firmware_version()
            self.log.debug("Configuration package sent")
        except ValueError as e:
            self.log.error(f"Error sending configuration package: {e}")
            self.save_data_label.value = str(e)
            self.acquisition_running = False
            if self.ser_open_button.disabled:
                self.click_start_stop_acq(self.start_stop_button)
            return

        self.log.info("Starting visualization thread")
        self.visualize = True
        self.current_data = None
        self.current_bmode_frame = None
        self.current_amode_data = None
        t2 = Thread(target=self.visualization, args=(number_of_acq,))
        t2.start()

        # Make any status reported below specific to this acquisition. Older
        # transports do not implement the ESP32 status commands.
        if hasattr(self.com_link, "clear_status"):
            try:
                self.com_link.clear_status(clear_counters=True, timeout=2.0)
            except Exception as exc:
                self.log.warning("Could not clear acquisition status: %s", exc)

        # Send RX start command
        self.log.info("Sending RX start command")
        self.com_link.toggle_rx(True)
        self.acquisition_status_label.value = "Status: Acquiring"
        self.log.debug("RX start command sent")

        # Readout data in a loop
        self.log.info("Starting data acquisition loop")
        while self.data_cnt < number_of_acq and self.acquisition_running:
            # Receive the data
            packet = self.com_link.receive_data()
            if packet is None:
                self.log.warning("Timed out waiting for acquisition data")
                if not self.acquisition_running:
                    break
                if hasattr(self.com_link, "get_status"):
                    try:
                        status = self.com_link.get_status(timeout=2.0)
                        errors = [
                            name
                            for flag, name in STATUS_ERROR_NAMES.items()
                            if status.error_flags & flag
                        ]
                        error_text = ", ".join(errors) if errors else "none"
                        self.acquisition_status_label.value = (
                            f"Status: stalled; errors={error_text}; "
                            f"overflow={status.buffer_overflow_count}; "
                            f"SPI={status.completed_spi_count}; "
                            f"TX={status.transmitted_frame_count}; "
                            f"discarded={status.discarded_frame_count}; "
                            f"buffer={status.current_buffer_usage}/"
                            f"{status.maximum_buffer_usage}"
                        )
                        self.log.error(
                            "Acquisition stalled; firmware status: %s", status
                        )
                        if status.error_flags:
                            break
                    except Exception as exc:
                        self.acquisition_status_label.value = (
                            f"Status: stalled; status query failed: {exc}"
                        )
                        self.log.exception("Could not read firmware status")
                        break
                continue
            rf_arr, acq_nr, tx_rx_id = packet
            # self.save_data_label.value = (
            #     f"{np.array(rf_arr).shape}, {acq_nr}, {tx_rx_id}"
            # )
            # For now, we just ignore invalid data
            if (
                rf_arr is not None
                # The device acquisition number is a wrapping uint16 sequence
                # counter and does not necessarily restart at zero for each GUI
                # run.  Frames are stored by data_cnt below, so restricting the
                # sequence number to number_of_acq rejects valid frames and can
                # leave the progress bar permanently stalled.
                and (acq_nr >= 0 and acq_nr <= 0xFFFF)
                and (tx_rx_id >= 0 and tx_rx_id < self.uss_conf.num_txrx_configs)
            ):
                # self.log.debug("Data received")
                self.current_data = rf_arr
                self.current_bmode_frame = (tx_rx_id, rf_arr)

                if (
                    tx_rx_id == self.rx_tx_conf_to_display
                    and not self.bmode_check.value
                ):
                    self.current_amode_data = rf_arr

                # Save data
                self.data_arr[:, self.data_cnt] = rf_arr

                # and other params
                self.acq_num_arr[self.data_cnt] = acq_nr
                self.tx_rx_id_arr[self.data_cnt] = tx_rx_id

                self.data_cnt = self.data_cnt + 1

                # Widget trait updates and file logging are expensive in a
                # Jupyter background thread. Keep the receive path fast and
                # publish progress at 10 Hz instead of once per RF frame.
                now = time.monotonic()
                if now >= next_progress_update or self.data_cnt == number_of_acq:
                    self.frame_progr_bar.description = (
                        "Progress: " + str(self.data_cnt) + "/" + str(number_of_acq)
                    )
                    self.frame_progr_bar.value = self.data_cnt
                    self.log.debug(
                        "Progress: %d/%d; last frame=%d, RX/TX=%d",
                        self.data_cnt,
                        number_of_acq,
                        acq_nr,
                        tx_rx_id,
                    )
                    next_progress_update = now + PROGRESS_UPDATE_PERIOD_S
            else:
                self.log.warning("No data received")

        self.log.info(
            f"Acquisition loop finished. data_cnt = {self.data_cnt}, acq_running = {self.acquisition_running}"
        )

        if self.data_cnt >= number_of_acq:
            self.acquisition_status_label.value = (
                f"Status: Complete ({self.data_cnt}/{number_of_acq} frames)"
            )
        elif self.acquisition_status_label.value == "Status: Acquiring":
            self.acquisition_status_label.value = (
                f"Status: Stopped ({self.data_cnt}/{number_of_acq} frames)"
            )

        self.log.info("Stopping RX")
        try:
            self.com_link.toggle_rx(False)
            self.log.debug("RX stopped")
        except WulpusProWiFiError as exc:
            self.log.warning("Could not stop RX during acquisition cleanup: %s", exc)

        self.log.debug("Stopping visualization thread")
        self.visualize = False
        t2.join()

        self.log.info("Sending restart command")
        try:
            self.com_link.send_acq_config(self.uss_conf.get_restart_package())
        except (ValueError, WulpusProWiFiError) as e:
            self.log.error(f"Error sending restart command: {e}")
            self.save_data_label.value = str(e)
        self.log.debug("Restart command sent")

        # Save data to file if needed
        if self.save_data_check.value:
            self.save_data_to_file()

        # Stop acquisition
        if self.ser_open_button.disabled:
            self.click_start_stop_acq(self.start_stop_button)

        # All background communication has stopped, so GUI callbacks can now
        # safely use or close the transport without racing its packet reader.
        self.ser_open_button.disabled = False
        self.reset_msp_button.disabled = (
            not self.port_opened or not hasattr(self.com_link, "reset_msp")
        )

        # self.click_open_port(self.ser_open_button) # if you want to close the port after acquisition

    def visualization(self, number_of_acq):
        self.log.info("Visualization thread started")

        self.frame_progr_bar.max = number_of_acq

        while self.visualize:
            # Update the visualization

            begin_time = time.time()

            # B-mode
            if self.bmode_check.value:
                if self.current_data is None:
                    time.sleep(self.vis_fps_period)
                    continue
                try:
                    # Filtering and envelope extraction used to run for every
                    # received frame. Do it only at the visualization rate so
                    # USB reception is never blocked by display processing.
                    bmode_frame = self.current_bmode_frame
                    if bmode_frame is not None:
                        tx_rx_id, rf_data = bmode_frame
                        self.data_arr_bmode[tx_rx_id] = (
                            self.get_envelope(self.filter_data(rf_data))
                        )
                    # self.bmode_image.set_data(np.log10(np.add(self.data_arr_bmode, 0.1)))                                # log scale
                    # self.bmode_image.set_data(self.data_arr_bmode[:,10*LOWER_BOUNDS_MM:])                                # linear scale
                    self.bmode_image.set_data(
                        self.data_arr_bmode
                    )  # linear scale, all data
                except Exception as _:
                    # B-mode graph is not initialized yet
                    pass

            # Check the id of RX TX config
            else:
                if self.current_amode_data is None:
                    time.sleep(self.vis_fps_period)
                    continue
                filt_data = None

                # Raw RF data
                if self.raw_data_check.value:
                    self.raw_data_line.set_ydata(self.current_amode_data)

                # Filtered data
                if self.filt_data_check.value:
                    filt_data = self.filter_data(self.current_amode_data)
                    self.filt_data_line.set_ydata(filt_data)

                # Envelope
                if self.env_data_check.value:
                    if filt_data is None:
                        filt_data = self.filter_data(self.current_amode_data)
                    self.envelope_line.set_ydata(self.get_envelope(filt_data))

            self.fig.canvas.draw()
            # This will run the GUI event
            # loop until all UI events
            # currently waiting have been processed
            self.fig.canvas.flush_events()

            # send thread to sleep for max_vis_fps_period
            sleep_time = self.vis_fps_period - (time.time() - begin_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.log.info("Visualization thread finished")

    # Design bandpass filter
    def design_filter(
        self,
        f_sampling,
        f_low_cutoff,
        f_high_cutoff,
        trans_width=0.2 * 10**6,
        n_taps=31,
    ):
        temp = [
            0,
            f_low_cutoff - trans_width,
            f_low_cutoff,
            f_high_cutoff,
            f_high_cutoff + trans_width,
            f_sampling / 2,
        ]

        self.filt_b = ss.remez(n_taps, temp, [0, 1, 0], Hz=f_sampling, maxiter=2500)
        self.filt_a = 1

    def filter_data(self, data_in):
        return ss.filtfilt(self.filt_b, self.filt_a, data_in)

    def get_envelope(self, data_in):
        return np.abs(hilbert(data_in))

    def save_data_to_file(self):
        self.log.info("Saving data to file")

        # Check filename
        for i in range(100):
            filename = FILE_NAME_BASE + str(i) + ".npz"
            if not os.path.isfile(filename):
                break

        self.log.info(f"Saving data to {filename}")

        # Save numpy data array to file
        np.savez(
            filename[:-4],
            data_arr=self.data_arr,
            acq_num_arr=self.acq_num_arr,
            tx_rx_id_arr=self.tx_rx_id_arr,
        )

        self.save_data_label.value = "Data saved in " + filename

        self.log.info("Data saved")
