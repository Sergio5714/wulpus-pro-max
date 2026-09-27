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


MSP430FR5043 image packaging, upload, and Jupyter update widget.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import struct
import threading
import time
import zlib
from typing import Callable, Dict, Iterable, List, Optional, Tuple
import zipfile

from .wifi_link import (
    WulpusProCommandError,
    WulpusProWiFiCommand,
    WulpusProWiFiDisconnected,
    WulpusProWiFiLink,
    WulpusProWiFiProtocolError,
    WulpusProWiFiTimeout,
)

MSP_IMAGE_MAGIC = 0x3150534D
MSP_IMAGE_VERSION = 1
MSP430FR5043_TARGET_ID = 0x00005043
HEADER = struct.Struct("<IHHIIIHH")
SECTION = struct.Struct("<III")
STATUS = struct.Struct("<BBHIIIIIi")
DIAGNOSTICS = struct.Struct("<BBHHHIHH")
DATA_HEADER = struct.Struct("<IHHI")
MAX_RELEASE_ENTRIES = 32
MAX_RELEASE_UNCOMPRESSED_BYTES = 2 * 1024 * 1024
MAX_MSPFW_BYTES = 256 * 1024


class MSP430UpdateState(IntEnum):
    IDLE = 0
    RECEIVING = 1
    READY = 2
    VALIDATING = 3
    PROGRAMMING = 4
    VERIFYING = 5
    RESETTING = 6
    WAITING_FOR_BOOT = 7
    COMPLETE = 8
    FAILED = 9
    ABORTED = 10


@dataclass(frozen=True)
class MSP430UpdateStatus:
    version: int
    state: MSP430UpdateState
    received_bytes: int
    total_bytes: int
    processed_bytes: int
    current_address: int
    target_device_id: int
    error: int


@dataclass(frozen=True)
class MSP430Diagnostics:
    version: int
    stage: int
    jtag_id: int
    core_id: int
    control_signal: int
    descriptor_pointer: int
    quick_device_id: int
    direct_device_id: int


def _sections_from_bytes(memory: Dict[int, int]) -> List[Tuple[int, bytes]]:
    if not memory:
        raise ValueError("Firmware contains no data")
    sections: List[Tuple[int, bytes]] = []
    start = previous = min(memory)
    data = bytearray([memory[start]])
    for address in sorted(memory)[1:]:
        if address != previous + 1:
            sections.append((start, bytes(data)))
            start, data = address, bytearray()
        data.append(memory[address])
        previous = address
    sections.append((start, bytes(data)))
    filtered: List[Tuple[int, bytes]] = []
    for address, payload in sections:
        # FR5043 JTAG/BSL signatures occupy 0xFF80..0xFF8F. Hex utilities
        # commonly emit an erased placeholder here; never write that range.
        protected_start, protected_end = 0xFF80, 0xFF90
        start, end = address, address + len(payload)
        if start < protected_end and end > protected_start:
            overlap_start = max(start, protected_start)
            overlap_end = min(end, protected_end)
            protected = payload[overlap_start - start:overlap_end - start]
            if any(value != 0xFF for value in protected):
                raise ValueError("Image attempts to program protected FR5043 signatures")
            if start < protected_start:
                filtered.append((start, payload[:protected_start - start]))
            if end > protected_end:
                filtered.append((protected_end, payload[protected_end - start:]))
        else:
            filtered.append((address, payload))

    result = []
    for address, payload in filtered:
        if address & 1:
            raise ValueError(f"Section starts at odd address 0x{address:05X}")
        if len(payload) & 1:
            payload += b"\xff"
        end = address + len(payload)
        if not (0x6000 <= address and end <= 0x15FF8):
            raise ValueError(f"Section 0x{address:05X}..0x{end - 1:05X} is outside FR5043 application FRAM")
        result.append((address, payload))
    return result


def parse_ti_txt(text: str) -> List[Tuple[int, bytes]]:
    memory: Dict[int, int] = {}
    address: Optional[int] = None
    for token in text.replace("\r", " ").split():
        if token.lower() == "q":
            break
        if token.startswith("@"):
            address = int(token[1:], 16)
        else:
            if address is None:
                raise ValueError("TI-TXT data appears before an address")
            memory[address] = int(token, 16)
            address += 1
    return _sections_from_bytes(memory)


def parse_intel_hex(text: str) -> List[Tuple[int, bytes]]:
    memory: Dict[int, int] = {}
    base = 0
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip().lstrip("\ufeff")
        if not line:
            continue
        if not line.startswith(":"):
            raise ValueError(f"Invalid Intel HEX record on line {line_number}")
        record = bytes.fromhex(line[1:])
        if len(record) < 5 or len(record) != record[0] + 5 or sum(record) & 0xFF:
            raise ValueError(f"Invalid Intel HEX checksum/length on line {line_number}")
        count, address, kind = record[0], int.from_bytes(record[1:3], "big"), record[3]
        data = record[4:4 + count]
        if kind == 0:
            for index, byte in enumerate(data):
                memory[base + address + index] = byte
        elif kind == 1:
            break
        elif kind == 2 and count == 2:
            base = int.from_bytes(data, "big") << 4
        elif kind == 4 and count == 2:
            base = int.from_bytes(data, "big") << 16
        elif kind not in (3, 5):
            raise ValueError(f"Unsupported Intel HEX record type {kind}")
    return _sections_from_bytes(memory)


def parse_text_image(content: bytes) -> List[Tuple[int, bytes]]:
    """Detect TI-TXT or Intel HEX by content, independent of its filename."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Firmware is not TI-TXT or Intel HEX text") from exc
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first.startswith("@"):
        return parse_ti_txt(text)
    if first.startswith(":"):
        return parse_intel_hex(text)
    preview = first[:40].replace("<", "&lt;").replace(">", "&gt;")
    raise ValueError(
        f"Unknown firmware text format; first line is {preview!r}, expected '@' or ':'"
    )


def make_image(sections: Iterable[Tuple[int, bytes]]) -> bytes:
    items = list(sections)
    if not items or len(items) > 64:
        raise ValueError("Image must contain 1..64 sections")
    table = b"".join(SECTION.pack(address, len(data), zlib.crc32(data))
                     for address, data in items)
    payload = b"".join(data for _, data in items)
    total = HEADER.size + len(table) + len(payload)
    header = HEADER.pack(MSP_IMAGE_MAGIC, MSP_IMAGE_VERSION, HEADER.size,
                         MSP430FR5043_TARGET_ID, total, zlib.crc32(payload),
                         len(items), 0)
    return header + table + payload


def validate_image(image: bytes) -> bytes:
    if len(image) < HEADER.size or HEADER.unpack_from(image)[0] != MSP_IMAGE_MAGIC:
        raise ValueError("Invalid MSP firmware container")
    return image


def load_release_zip(payload: bytes) -> bytes:
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise ValueError("Select a WULPUS Pro Max MSP430 release ZIP") from exc

    with archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(entries) > MAX_RELEASE_ENTRIES:
            raise ValueError("MSP430 release ZIP contains too many entries")
        if len(names) != len(set(names)):
            raise ValueError("MSP430 release ZIP contains duplicate paths")
        if sum(entry.file_size for entry in entries) > MAX_RELEASE_UNCOMPRESSED_BYTES:
            raise ValueError("MSP430 release ZIP is too large")
        for name in names:
            path = PurePosixPath(name.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("MSP430 release ZIP contains an unsafe path")

        firmware_names = [
            name for name in names
            if PurePosixPath(name).suffix.lower() == ".mspfw"
        ]
        if len(firmware_names) != 1:
            raise ValueError("MSP430 release ZIP must contain exactly one .mspfw file")
        firmware_name = firmware_names[0]
        if PurePosixPath(firmware_name).parent != PurePosixPath("."):
            raise ValueError("MSP430 firmware must be at the root of the release ZIP")
        if "SHA256SUMS.txt" not in names:
            raise ValueError("MSP430 release ZIP has no SHA256SUMS.txt")

        try:
            checksum_text = archive.read("SHA256SUMS.txt").decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("MSP430 SHA256SUMS.txt is not ASCII") from exc
        matches = []
        for line in checksum_text.splitlines():
            match = re.fullmatch(r"([0-9A-Fa-f]{64})[ \t]+\*?(.+)", line.strip())
            if match and match.group(2) == firmware_name:
                matches.append(match.group(1).lower())
        if len(matches) != 1:
            raise ValueError("MSP430 checksum file must identify the firmware exactly once")

        image = archive.read(firmware_name)
        if len(image) > MAX_MSPFW_BYTES:
            raise ValueError("MSP430 firmware image is too large")
        if hashlib.sha256(image).hexdigest() != matches[0]:
            raise ValueError(f"Checksum mismatch for {firmware_name}")
        return validate_image(image)


def load_image(path: str | Path) -> bytes:
    path = Path(path)
    payload = path.read_bytes()
    if path.suffix.lower() in (".txt", ".titxt", ".hex", ".ihex"):
        return make_image(parse_text_image(payload))
    if path.suffix.lower() == ".mspfw":
        return validate_image(payload)
    if path.suffix.lower() == ".zip":
        return load_release_zip(payload)
    raise ValueError(
        "Select an MSP430 release ZIP, TI-TXT (.txt), Intel HEX (.hex), or .mspfw file"
    )


class MSP430Updater:
    def __init__(self, link: WulpusProWiFiLink, chunk_size: int = 128,
                 data_retries: int = 3):
        if not 1 <= chunk_size <= 792:
            raise ValueError("Chunk size must be 1..792 bytes")
        if data_retries < 0:
            raise ValueError("Data retries must not be negative")
        self.link, self.chunk_size = link, chunk_size
        self.data_retries = data_retries
        self._link_lock = threading.RLock()

    def status(self, timeout: float = 5.0) -> MSP430UpdateStatus:
        with self._link_lock:
            self.link.send_command(WulpusProWiFiCommand.MSP_UPDATE_GET_STATUS, timeout=timeout)
            header, payload = self.link.receive_command(timeout)
        if header.command != WulpusProWiFiCommand.MSP_UPDATE_STATUS or len(payload) != STATUS.size:
            raise WulpusProWiFiProtocolError("Invalid MSP update status")
        version, state, _flags, received, total, processed, address, device, error = STATUS.unpack(payload)
        return MSP430UpdateStatus(version, MSP430UpdateState(state), received, total,
                                  processed, address, device, error)

    def diagnostics(self, timeout: float = 5.0) -> MSP430Diagnostics:
        with self._link_lock:
            header, payload = self.link.send_command(
                WulpusProWiFiCommand.MSP_UPDATE_GET_DIAGNOSTICS,
                expected_response=WulpusProWiFiCommand.MSP_UPDATE_DIAGNOSTICS,
                timeout=timeout,
            )
        if (header.command != WulpusProWiFiCommand.MSP_UPDATE_DIAGNOSTICS or \
                len(payload) != DIAGNOSTICS.size):
            raise WulpusProWiFiProtocolError("Invalid MSP diagnostics response")
        return MSP430Diagnostics(*DIAGNOSTICS.unpack(payload))

    def program(self, image: bytes, progress: Optional[Callable[[MSP430UpdateStatus], None]] = None,
                timeout: float = 120.0) -> MSP430UpdateStatus:
        with self._link_lock:
            self.link.send_command(WulpusProWiFiCommand.MSP_UPDATE_BEGIN,
                                   struct.pack("<BBHII", 1, 0, 0, len(image), zlib.crc32(image)))
        for sequence, offset in enumerate(range(0, len(image), self.chunk_size)):
            data = image[offset:offset + self.chunk_size]
            request = DATA_HEADER.pack(offset, sequence, len(data), zlib.crc32(data)) + data
            for attempt in range(self.data_retries + 1):
                try:
                    with self._link_lock:
                        _, response = self.link.send_command(
                            WulpusProWiFiCommand.MSP_UPDATE_DATA, request
                        )
                    break
                except WulpusProCommandError as exc:
                    # ESP_ERR_INVALID_CRC means this chunk was rejected before
                    # it was written, so resending the identical offset is safe.
                    if exc.error != 0x109 or attempt == self.data_retries:
                        raise WulpusProWiFiProtocolError(
                            f"MSP data chunk failed at offset {offset} "
                            f"(sequence {sequence}, attempt {attempt + 1}): {exc}"
                        ) from exc
            if response is None or len(response) != 8:
                raise WulpusProWiFiProtocolError("Invalid MSP update data acknowledgement")
            next_offset, accepted, reserved = struct.unpack("<IHH", response)
            if next_offset != offset + len(data) or accepted != sequence or reserved:
                raise WulpusProWiFiProtocolError("MSP update offset/sequence mismatch")
            # Native USB CDC is reliable, but a short scheduling interval keeps
            # its RX ring from being driven continuously across wrap points.
            time.sleep(0.005)
        commit_acknowledged = True
        try:
            with self._link_lock:
                self.link.send_command(WulpusProWiFiCommand.MSP_UPDATE_COMMIT)
        except WulpusProWiFiTimeout:
            # COMMIT may have reached the device even when its acknowledgement
            # is delayed by JTAG work. Determine the outcome from status rather
            # than restarting an update that may already be programming.
            commit_acknowledged = False
        deadline = time.monotonic() + timeout
        commit_retried = False
        if not commit_acknowledged:
            # Do not fill the USB CDC receive queue with status requests while
            # the bit-banged JTAG worker temporarily monopolizes the device.
            time.sleep(10.0)
        while True:
            try:
                current = self.status()
            except (WulpusProWiFiTimeout, WulpusProWiFiDisconnected):
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "MSP430 programming status remained unavailable"
                    )
                if not self.link.connected:
                    try:
                        with self._link_lock:
                            self.link.open()
                    except Exception:
                        pass
                # Space recovery probes so a busy USB endpoint cannot be
                # saturated by the status polling itself.
                time.sleep(2.0)
                continue
            if progress:
                progress(current)
            if (not commit_acknowledged and not commit_retried and
                    current.state == MSP430UpdateState.READY):
                # READY proves that no worker accepted the first COMMIT, making
                # one retransmission safe. A second lost acknowledgement is
                # handled by status polling in the same way.
                commit_retried = True
                try:
                    with self._link_lock:
                        self.link.send_command(WulpusProWiFiCommand.MSP_UPDATE_COMMIT)
                    commit_acknowledged = True
                except WulpusProWiFiTimeout:
                    pass
                continue
            if current.state in (MSP430UpdateState.COMPLETE, MSP430UpdateState.FAILED,
                                 MSP430UpdateState.ABORTED):
                return current
            if time.monotonic() >= deadline:
                raise TimeoutError("MSP430 programming timed out")
            time.sleep(0.25)

    def program_file(self, path: str | Path, **kwargs) -> MSP430UpdateStatus:
        return self.program(load_image(path), **kwargs)

    def show_widget(self):
        try:
            import ipywidgets as widgets
            from IPython.display import display
        except ImportError as exc:
            raise RuntimeError("Install ipywidgets to use the updater GUI") from exc
        upload = widgets.FileUpload(
            accept=".zip,.txt,.titxt,.hex,.ihex,.mspfw", multiple=False,
            description="Release ZIP",
        )
        button = widgets.Button(description="Upload and program", button_style="warning")
        status_button = widgets.Button(description="Check status", icon="refresh")
        bar = widgets.IntProgress(min=0, max=100, description="MSP430")
        status_text = widgets.HTML(value="State: IDLE")
        diagnostics_text = widgets.HTML(value="")
        output = widgets.Output()
        gui_state = {"running": False, "latest": None}

        def show_status(status: MSP430UpdateStatus) -> None:
            gui_state["latest"] = status
            done = status.processed_bytes or status.received_bytes
            fraction = min(1.0, done / max(1, status.total_bytes))
            if status.state == MSP430UpdateState.RECEIVING:
                bar.description = "Uploading"
                value = 30 * fraction
            elif status.state in (MSP430UpdateState.READY,
                                  MSP430UpdateState.VALIDATING):
                bar.description = "Validating"
                value = 30
            elif status.state == MSP430UpdateState.PROGRAMMING:
                bar.description = "Programming"
                value = 30 + 35 * fraction
            elif status.state == MSP430UpdateState.VERIFYING:
                bar.description = "Verifying"
                value = 65 + 35 * fraction
            elif status.state == MSP430UpdateState.COMPLETE:
                bar.description = "Complete"
                value = 100
            else:
                bar.description = status.state.name.title()
                value = bar.value
            bar.value = max(bar.value, min(100, int(value)))
            status_text.value = (
                f"<b>State:</b> {status.state.name} &nbsp; "
                f"<b>Bytes:</b> {done}/{status.total_bytes} &nbsp; "
                f"<b>Address:</b> 0x{status.current_address:05X} &nbsp; "
                f"<b>Device:</b> 0x{status.target_device_id:08X} &nbsp; "
                f"<b>Error:</b> 0x{status.error & 0xffffffff:08X}"
            )

        def show_diagnostics(diag: MSP430Diagnostics) -> None:
            stages = {
                0: "NOT_STARTED", 1: "JTAG_ENTRY", 2: "CORE_ID",
                3: "DESCRIPTOR_POINTER", 4: "SYNCHRONIZATION",
                5: "DEVICE_MEMORY_READ", 6: "DEVICE_VALIDATED",
            }
            diagnostics_text.value = (
                "<b>JTAG diagnostics:</b> "
                f"Stage={stages.get(diag.stage, str(diag.stage))} &nbsp; "
                f"JTAG ID=0x{diag.jtag_id:04X} &nbsp; "
                f"Core ID=0x{diag.core_id:04X} &nbsp; "
                f"Control=0x{diag.control_signal:04X}<br>"
                f"Descriptor=0x{diag.descriptor_pointer:05X} &nbsp; "
                f"Quick[0x1A04]=0x{diag.quick_device_id:04X} &nbsp; "
                f"Direct[0x1A04]=0x{diag.direct_device_id:04X} &nbsp; "
                "Expected=0x8317"
            )

        def format_diagnostics(diag: MSP430Diagnostics) -> str:
            stages = {
                0: "NOT_STARTED", 1: "JTAG_ENTRY", 2: "CORE_ID",
                3: "DESCRIPTOR_POINTER", 4: "SYNCHRONIZATION",
                5: "DEVICE_MEMORY_READ", 6: "DEVICE_VALIDATED",
            }
            return (
                "MSP430 JTAG diagnostics:\n"
                f"  Diagnostic version : {diag.version}\n"
                f"  Last stage         : {stages.get(diag.stage, str(diag.stage))}\n"
                f"  JTAG ID            : 0x{diag.jtag_id:04X} (expected 0x0099)\n"
                f"  Core ID            : 0x{diag.core_id:04X} (expected nonzero)\n"
                f"  Control signal     : 0x{diag.control_signal:04X}\n"
                f"  Descriptor pointer : 0x{diag.descriptor_pointer:05X} "
                "(expected 0x01A00)\n"
                f"  Quick read 0x1A04 : 0x{diag.quick_device_id:04X}\n"
                f"  Direct read 0x1A04: 0x{diag.direct_device_id:04X}\n"
                "  Expected device ID : 0x8317\n"
            )

        def clicked(_):
            output.clear_output()
            if not upload.value:
                output.append_stdout("Select a firmware file first\n")
                return
            try:
                item = next(iter(upload.value.values())) if isinstance(upload.value, dict) else upload.value[0]
                name, content = item["name"], bytes(item["content"])
                suffix = Path(name).suffix.lower()
                if suffix in (".txt", ".titxt", ".hex", ".ihex"):
                    image = make_image(parse_text_image(content))
                elif suffix == ".mspfw":
                    image = validate_image(content)
                elif suffix == ".zip":
                    image = load_release_zip(content)
                else:
                    raise ValueError("Select an MSP430 release ZIP")
            except Exception as exc:
                status_text.value = f"<b>Image error:</b> {exc}"
                output.append_stdout(f"Image error: {exc}\n")
                return
            button.disabled = True
            bar.value = 0
            bar.description = "Uploading"
            gui_state["running"] = True
            gui_state["latest"] = None

            def run_update():
                try:
                    final = self.program(image, show_status)
                    show_status(final)
                    output.append_stdout(
                        f"Finished: {final.state.name}, "
                        f"error=0x{final.error & 0xffffffff:08x}\n"
                    )
                    try:
                        diag = self.diagnostics(timeout=10.0)
                        show_diagnostics(diag)
                        output.append_stdout(format_diagnostics(diag))
                    except Exception as diag_exc:
                        diagnostics_text.value = (
                            f"<b>Diagnostics unavailable:</b> {diag_exc}"
                        )
                        output.append_stdout(
                            f"Diagnostics unavailable: {diag_exc}\n"
                        )
                except Exception as exc:
                    status_text.value = f"<b>Update request failed:</b> {exc}"
                    output.append_stdout(f"Update request failed: {exc}\n")
                finally:
                    gui_state["running"] = False
                    button.disabled = False

            threading.Thread(target=run_update, name="msp430-update", daemon=True).start()

        def check_status(_):
            status_button.disabled = True
            try:
                # status() serializes a complete request/response transaction,
                # so this is safe alongside the background polling worker.
                current = self.status()
                show_status(current)
                output.clear_output()
                output.append_stdout(
                    f"Current state: {current.state.name}, "
                    f"error=0x{current.error & 0xffffffff:08x}\n"
                )
                try:
                    diag = self.diagnostics(timeout=10.0)
                    show_diagnostics(diag)
                    output.append_stdout(format_diagnostics(diag))
                except Exception as diag_exc:
                    diagnostics_text.value = (
                        f"<b>Diagnostics unavailable:</b> {diag_exc}"
                    )
                    output.append_stdout(
                        f"Diagnostics unavailable: {diag_exc}\n"
                    )
            except Exception as exc:
                status_text.value = f"<b>Status request failed:</b> {exc}"
                output.clear_output()
                output.append_stdout(f"Status request failed: {exc}\n")
            finally:
                status_button.disabled = False

        button.on_click(clicked)
        status_button.on_click(check_status)
        controls = widgets.HBox([button, status_button])
        display(widgets.VBox([upload, controls, bar, status_text, diagnostics_text, output]))
        return upload, button, status_button, bar, status_text, diagnostics_text, output
