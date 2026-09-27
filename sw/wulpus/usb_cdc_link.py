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

USB CDC communication link for a directly connected WULPUS Pro Max ESP32-C6 host.
"""

from dataclasses import dataclass
import logging
import socket
import sys
from typing import List, Optional

import serial
from serial.tools.list_ports import comports

from .wifi_link import WulpusProWiFiLink

logger = logging.getLogger(__name__)

ESPRESSIF_USB_VID = 0x303A
ESPRESSIF_USB_SERIAL_JTAG_PID = 0x1001


@dataclass(frozen=True)
class WulpusProUsbCdcDevice:
    """USB Serial/JTAG CDC endpoint exposed by the ESP32-C6."""

    device: str
    description: str
    serial_number: Optional[str] = None

    def __str__(self) -> str:
        suffix = f" ({self.serial_number})" if self.serial_number else ""
        return f"{self.description} at {self.device}{suffix}"


class _EspUsbCdcSerial(serial.Serial):
    """Accept native ESP USB CDC ports that reject UART line settings.

    Windows' pySerial backend applies UART settings with ``SetCommState``
    whenever it opens a COM port.  The ESP32-C6's fixed USB Serial/JTAG CDC
    interface does not use those settings and can reject that call with error
    31 even though byte-oriented reads and writes are available.
    """

    def _reconfigure_port(self) -> None:
        try:
            super()._reconfigure_port()
        except serial.SerialException as exc:
            message = str(exc)
            if (
                sys.platform == "win32"
                and "Cannot configure port" in message
                and "None, 31" in message
            ):
                logger.warning(
                    "Ignoring unsupported SetCommState operation for ESP USB CDC"
                )
                return
            raise


class _SerialByteStream:
    """Adapt pyserial to the small socket API used by the stream protocol.

    WulpusProWiFiLink's protocol implementation needs only sendall(), recv(),
    timeout access, and close(). Keeping that interface here allows both links
    to use exactly the same framing, acknowledgement, and RF parsing code.
    """

    def __init__(self, port: serial.Serial) -> None:
        self.port = port

    def gettimeout(self) -> Optional[float]:
        return self.port.timeout

    def settimeout(self, timeout: Optional[float]) -> None:
        self.port.timeout = timeout

    def sendall(self, data: bytes) -> None:
        view = memoryview(data)
        written = 0
        while written < len(view):
            count = self.port.write(view[written:])
            if count is None or count <= 0:
                raise serial.SerialTimeoutException("USB CDC write timed out")
            written += count

    def recv(self, length: int) -> bytes:
        if length <= 0:
            return b""

        # pySerial's read(length) waits for all requested bytes or the timeout.
        # The framed parser may request a large chunk while a command ack is
        # only nine bytes, so first block for one byte and then drain whatever
        # is already buffered without waiting to fill the entire request.
        data = self.port.read(1)
        if not data:
            # Match socket semantics so the shared protocol distinguishes a
            # finite read timeout from a disconnected stream.
            raise socket.timeout()
        available = min(length - 1, self.port.in_waiting)
        if available > 0:
            data += self.port.read(available)
        return data

    def close(self) -> None:
        self.port.close()


class WulpusProUsbCdcLink(WulpusProWiFiLink):
    """Run the WULPUS Pro Max stream protocol over native ESP32-C6 USB CDC.

    The ESP32-C6 exposes one fixed USB Serial/JTAG device. The GUI must close
    this link before ``idf.py flash`` or a serial monitor can claim the COM
    port. JTAG remains a separate interface of the same composite USB device.
    """

    def __init__(self, port: str = "", timeout: float = 5.0) -> None:
        # Initialize the shared protocol state. Wi-Fi discovery is not used by
        # this subclass, but retaining the base layout avoids duplicating the
        # protocol and acquisition lifecycle.
        super().__init__()
        self.port = port
        self.timeout = timeout
        self.device: Optional[WulpusProUsbCdcDevice] = None

    def get_available(self, timeout: float = 0.0) -> List[WulpusProUsbCdcDevice]:
        del timeout  # Serial enumeration is synchronous.
        devices: List[WulpusProUsbCdcDevice] = []
        for port in comports():
            if (
                port.vid == ESPRESSIF_USB_VID
                and port.pid == ESPRESSIF_USB_SERIAL_JTAG_PID
            ):
                devices.append(
                    WulpusProUsbCdcDevice(
                        device=port.device,
                        description=port.description or "WULPUS Pro Max USB CDC",
                        serial_number=port.serial_number,
                    )
                )
        return sorted(devices, key=lambda item: item.device)

    def open(self, device: Optional[WulpusProUsbCdcDevice] = None) -> bool:
        if self.connected:
            return True
        selected_port = device.device if device is not None else self.port
        if not selected_port:
            logger.error("No WULPUS Pro Max USB CDC port was selected")
            return False

        try:
            serial_port = _EspUsbCdcSerial(
                port=selected_port,
                baudrate=115200,  # Nominal for native CDC; no UART baud clock.
                timeout=self.timeout,
                write_timeout=self.timeout,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
            # ROM/bootloader text may precede application binary traffic after
            # reset. Start with an empty host-side input buffer; the shared
            # parser also resynchronizes on the ``wulpus`` magic sequence.
            serial_port.reset_input_buffer()
        except (OSError, serial.SerialException) as exc:
            logger.error("Could not open USB CDC port %s: %s", selected_port, exc)
            return False

        self.sock = _SerialByteStream(serial_port)  # type: ignore[assignment]
        self.port = selected_port
        self.device = device or WulpusProUsbCdcDevice(
            device=selected_port,
            description="WULPUS Pro Max USB CDC",
        )
        self.backlog = b""
        self.rx_enabled = False
        logger.info("Connected to %s", self.device)
        return True
