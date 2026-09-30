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


Exclusive device session and acquisition engine.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any, Callable

import numpy as np
from wulpus.ble_dongle import WulpusBleDongle
from wulpus.usb_cdc_link import WulpusProUsbCdcLink
from wulpus.wifi_link import WulpusProWiFiLink

from .models import CAPABILITIES, AcquisitionResult, frame_gap

logger = logging.getLogger(__name__)


class SimulatorLink:
    """Deterministic synthetic transport for offline acquisition development."""

    acq_length = 400

    def __init__(self) -> None:
        """Initialize deterministic simulator connection and sample state."""
        self.connected = False
        self.running = False
        self.number = 0

    def get_available(self):
        """Return the simulator as the only available device."""
        return ["Simulator"]

    def open(self, _device=None):
        """Mark the simulated device as connected."""
        self.connected = True
        return True

    def close(self):
        """Mark the simulated device as disconnected."""
        self.connected = False
        return True

    def send_acq_config(self, _payload):
        """Accept an acquisition configuration payload."""
        return True

    def toggle_rx(self, state):
        """Start or stop simulated sample production."""
        self.running = state

    def receive_data(self):
        """Return one deterministic simulated acquisition frame when running."""
        if not self.running:
            return None
        time.sleep(0.002)
        x = np.arange(self.acq_length)
        rng = np.random.default_rng(self.number)
        data = 1800 * np.sin(2 * math.pi * 0.04 * x + self.number * 0.1)
        data *= np.exp(-(((x - 160) / 55) ** 2))
        data += rng.normal(0, 70, x.size)
        result = (data.astype("<i2"), self.number & 0xFFFF, self.number % 1)
        self.number += 1
        return result


def default_links(include_simulator: bool = False) -> dict[str, Any]:
    """Create independent transport adapters in the UI's default selection order."""
    links: dict[str, Any] = {
        "USB CDC": WulpusProUsbCdcLink(),
        "Wi-Fi": WulpusProWiFiLink(
            service_name="wulpus_pro", service_type="tcp", port=2121
        ),
        "BLE": WulpusBleDongle(),
    }
    if include_simulator:
        links["Simulator"] = SimulatorLink()
    return links


class SessionController:
    """Own exactly one link and serialize operations across all tabs."""

    def __init__(self, links: dict[str, Any] | None = None) -> None:
        """Initialize the session with supplied or default transport links."""
        self.links = links or default_links()
        self.transport = next(iter(self.links))
        self.link: Any | None = None
        self.device: Any | None = None
        self.busy_operation: str | None = None
        self._lock = threading.RLock()
        self.events: list[str] = []

    @property
    def capabilities(self):
        """Return capabilities advertised by the selected transport."""
        return CAPABILITIES[self.transport]

    @property
    def connected(self) -> bool:
        """Report whether a transport link is currently open."""
        return self.link is not None

    def log(self, message: str) -> None:
        """Record a timestamped session event and emit it to debug logging."""
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.events.append(f"{stamp}\t{message}")
        logger.debug(message)

    def select_transport(self, name: str) -> None:
        """Select an available transport while the session is disconnected."""
        if self.connected:
            raise RuntimeError("Disconnect before changing transport")
        if name not in self.links:
            raise ValueError(f"Unknown transport: {name}")
        self.transport = name

    def scan(self):
        """Discover endpoints on the selected transport without opening them."""
        if self.busy_operation:
            raise RuntimeError(f"Device is busy: {self.busy_operation}")
        found = self.links[self.transport].get_available()
        self.log(f"{self.transport}: found {len(found)} device(s)")
        return found

    def connect(self, device: Any) -> None:
        """Open one endpoint exclusively and retain its transport adapter."""
        with self._lock:
            if self.connected:
                raise RuntimeError("A device is already connected")
            candidate = self.links[self.transport]
            if not candidate.open(device):
                raise RuntimeError("Could not open device")
            self.link, self.device = candidate, device
            self.log(f"Connected using {self.transport}: {device}")

    def disconnect(self) -> None:
        """Close an idle session; reject closure during a device operation."""
        with self._lock:
            if self.busy_operation:
                raise RuntimeError(f"Cannot disconnect during {self.busy_operation}")
            if self.link is not None:
                self.link.close()
                self.log(f"Disconnected {self.transport}")
            self.link = self.device = None

    def reboot(self) -> None:
        """Reboot the connected device and release the now-invalid session."""
        with self._lock:
            if self.busy_operation:
                raise RuntimeError(f"Cannot reboot during {self.busy_operation}")
            link = self.require("reset_device")
            try:
                link.reset()
            finally:
                try:
                    link.close()
                finally:
                    self.link = self.device = None
        self.log(f"Rebooted {self.transport} device")

    def reset_msp(self) -> None:
        """Reset the MSP430 while keeping the host connection open."""
        with self._lock:
            if self.busy_operation:
                raise RuntimeError(f"Cannot reset MSP430 during {self.busy_operation}")
            self.require("reset_msp").reset_msp()
        self.log("Reset MSP430")

    def require(self, capability: str | None = None):
        """Return the active link or raise if disconnected/unsupported."""
        if self.link is None:
            raise RuntimeError("Connect to a device first")
        if capability and not getattr(self.capabilities, capability):
            raise RuntimeError(
                f"{capability.replace('_', ' ').title()} is unavailable over {self.transport}"
            )
        return self.link

    def acquire(
        self,
        config,
        stopped: Callable[[], bool],
        on_frame: Callable[[np.ndarray, int, int, int], None],
    ) -> AcquisitionResult:
        """Capture frames and metadata, checking cancellation between reads.

        The caller runs this method off the GUI thread. ``on_frame`` receives
        samples, sequence number, configuration ID, and cumulative gaps. Always
        attempt STOP/restart cleanup, including on transport or callback errors.
        """
        link = self.require("acquisition")
        with self._lock:
            if self.busy_operation:
                raise RuntimeError(f"Device is busy: {self.busy_operation}")
            self.busy_operation = "acquisition"
        frames, numbers, ids = [], [], []
        gaps, previous = 0, None
        try:
            link.acq_length = config.num_samples
            link.send_acq_config(config.get_restart_package())
            link.send_acq_config(config.get_conf_package())
            link.toggle_rx(True)
            self.log(f"Acquisition started: {config.num_acqs} frame(s)")
            while len(frames) < config.num_acqs and not stopped():
                packet = link.receive_data()
                if packet is None:
                    continue
                samples, number, tx_rx_id = packet
                samples = np.asarray(samples, dtype="<i2")
                if samples.size != config.num_samples:
                    raise RuntimeError(
                        f"Received {samples.size} samples; expected {config.num_samples}"
                    )
                gaps += frame_gap(previous, number)
                previous = number
                frames.append(samples.copy())
                numbers.append(number)
                ids.append(tx_rx_id)
                on_frame(samples, int(number), int(tx_rx_id), gaps)
            completed = len(frames) >= config.num_acqs
            self.log(
                f"Acquisition {'completed' if completed else 'stopped'}: {len(frames)} frame(s)"
            )
            shape = (0, config.num_samples) if not frames else None
            return AcquisitionResult(
                np.asarray(frames, dtype="<i2").reshape(
                    shape or (-1, config.num_samples)
                ),
                np.asarray(numbers, dtype="<u2"),
                np.asarray(ids, dtype=np.uint8),
                gaps,
                completed,
            )
        finally:
            try:
                link.toggle_rx(False)
                link.send_acq_config(config.get_restart_package())
            except Exception as error:
                self.log(f"Acquisition cleanup warning: {error}")
            with self._lock:
                self.busy_operation = None
