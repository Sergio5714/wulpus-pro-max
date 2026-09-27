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


Validated ESP32-C6 release packages and Jupyter flashing widget.
"""


from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from typing import Callable, Dict, Optional, Tuple
import zipfile

from .usb_cdc_link import WulpusProUsbCdcLink


PACKAGE_FORMAT_VERSION = 1
EXPECTED_PRODUCT = "WULPUS Pro Max"
EXPECTED_CHIP = "esp32c6"
EXPECTED_IMAGES = (
    (0x0, "bootloader.bin"),
    (0x8000, "partition-table.bin"),
    (0x10000, "wulpus-pro-fw.bin"),
)


@dataclass(frozen=True)
class Esp32FlashImage:
    offset: int
    path: str
    sha256: str
    data: bytes


@dataclass(frozen=True)
class Esp32ReleasePackage:
    version: str
    flash_mode: str
    flash_frequency: str
    flash_size: str
    images: Tuple[Esp32FlashImage, ...]

    @classmethod
    def load(cls, source: str | Path | bytes) -> "Esp32ReleasePackage":
        payload = source if isinstance(source, bytes) else Path(source).read_bytes()
        try:
            archive = zipfile.ZipFile(io.BytesIO(payload))
        except zipfile.BadZipFile as exc:
            raise ValueError("Select a WULPUS Pro Max ESP32 release ZIP") from exc

        with archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Release ZIP contains duplicate paths")
            if "manifest.json" not in names:
                raise ValueError("Release ZIP has no manifest.json")
            if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
                raise ValueError("Release ZIP contains an unsafe path")
            try:
                manifest = json.loads(archive.read("manifest.json"))
            except (json.JSONDecodeError, KeyError) as exc:
                raise ValueError("Release manifest is invalid") from exc

            if manifest.get("format_version") != PACKAGE_FORMAT_VERSION:
                raise ValueError("Unsupported release-package format")
            if manifest.get("product") != EXPECTED_PRODUCT:
                raise ValueError("Release package is for another product")
            if manifest.get("chip") != EXPECTED_CHIP:
                raise ValueError("Release package is not for ESP32-C6")
            version = manifest.get("firmware_version")
            if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
                raise ValueError("Release package has no semantic firmware version")

            flash = manifest.get("flash")
            if not isinstance(flash, dict):
                raise ValueError("Release manifest has no flash configuration")
            entries = flash.get("files")
            if not isinstance(entries, list) or len(entries) != len(EXPECTED_IMAGES):
                raise ValueError("Release package must contain three ESP32 images")

            images = []
            actual_layout = []
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError("Invalid image entry in release manifest")
                try:
                    offset = int(str(entry["offset"]), 0)
                    path = str(entry["path"])
                    expected_hash = str(entry["sha256"]).lower()
                    data = archive.read(path)
                except (KeyError, ValueError) as exc:
                    raise ValueError("Invalid image entry in release manifest") from exc
                if len(expected_hash) != 64 or any(c not in "0123456789abcdef" for c in expected_hash):
                    raise ValueError(f"Invalid SHA-256 for {path}")
                actual_hash = hashlib.sha256(data).hexdigest()
                if actual_hash != expected_hash:
                    raise ValueError(f"Checksum mismatch for {path}")
                actual_layout.append((offset, path))
                images.append(Esp32FlashImage(offset, path, actual_hash, data))

            if tuple(actual_layout) != EXPECTED_IMAGES:
                raise ValueError("Release package contains an unexpected flash layout")
            settings = (
                str(flash.get("mode", "")),
                str(flash.get("frequency", "")),
                str(flash.get("size", "")),
            )
            if settings != ("dio", "80m", "4MB"):
                raise ValueError("Release package contains unexpected flash settings")
            return cls(
                version=version,
                flash_mode=settings[0],
                flash_frequency=settings[1],
                flash_size=settings[2],
                images=tuple(images),
            )


class Esp32Flasher:
    """Flash a validated package with the esptool installed in this environment."""

    def __init__(self, output: Optional[Callable[[str], None]] = None):
        self.output = output or (lambda message: None)

    def command(self, package: Esp32ReleasePackage, port: str, directory: Path,
                baud: int = 460800) -> list[str]:
        command = [
            sys.executable, "-m", "esptool", "--chip", EXPECTED_CHIP,
            "--port", port, "--baud", str(baud), "--before", "default_reset",
            "--after", "hard_reset", "write_flash", "--flash_mode",
            package.flash_mode, "--flash_freq", package.flash_frequency,
            "--flash_size", package.flash_size,
        ]
        for image in package.images:
            command.extend((hex(image.offset), str(directory / image.path)))
        return command

    def flash(self, package: Esp32ReleasePackage, port: str,
              baud: int = 460800) -> None:
        if not port:
            raise ValueError("Select an ESP32-C6 serial port")
        with tempfile.TemporaryDirectory(prefix="wulpus-esp32-") as temporary:
            directory = Path(temporary)
            for image in package.images:
                (directory / image.path).write_bytes(image.data)
            process = subprocess.Popen(
                self.command(package, port, directory, baud),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.output(line)
            result = process.wait()
            if result:
                raise RuntimeError(f"esptool failed with exit code {result}")


class Esp32UpdateGui:
    """Jupyter widget for installing validated ESP32 release packages."""

    def __init__(self):
        try:
            import ipywidgets as widgets
        except ImportError as exc:
            raise RuntimeError("Install the software environment to use this GUI") from exc
        self.widgets = widgets
        self.scanner = WulpusProUsbCdcLink()
        self.package: Optional[Esp32ReleasePackage] = None
        self.port = widgets.Dropdown(description="COM port:", options=[])
        self.refresh = widgets.Button(description="Refresh ports", icon="refresh")
        self.upload = widgets.FileUpload(accept=".zip", multiple=False, description="Release ZIP")
        self.confirm = widgets.Checkbox(description="Keep USB and power connected")
        self.flash_button = widgets.Button(description="Flash ESP32", button_style="danger", disabled=True)
        self.status = widgets.HTML(value="<b>Status:</b> Select a release ZIP")
        self.progress = widgets.IntProgress(min=0, max=100, value=0, description="ESP32")
        self.output = widgets.Output()
        self.refresh.on_click(self._refresh_ports)
        self.upload.observe(self._package_selected, names="value")
        self.confirm.observe(self._controls_changed, names="value")
        self.port.observe(self._controls_changed, names="value")
        self.flash_button.on_click(self._flash_clicked)
        self._refresh_ports()

    @staticmethod
    def _uploaded_file(value) -> Tuple[str, bytes]:
        item = next(iter(value.values())) if isinstance(value, dict) else value[0]
        return item["name"], bytes(item["content"])

    def _refresh_ports(self, _=None) -> None:
        devices = self.scanner.get_available()
        self.port.options = [(str(device), device.device) for device in devices]
        self._controls_changed()

    def _controls_changed(self, _=None) -> None:
        self.flash_button.disabled = not (
            self.package is not None and self.port.value and self.confirm.value
        )

    def _package_selected(self, _=None) -> None:
        self.package = None
        self.progress.value = 0
        try:
            name, content = self._uploaded_file(self.upload.value)
            self.package = Esp32ReleasePackage.load(content)
            self.status.value = (
                f"<b>Ready:</b> {name} — ESP32-C6 firmware {self.package.version}; "
                "checksums and flash layout verified"
            )
        except Exception as exc:
            self.status.value = f"<b>Package error:</b> {exc}"
        self._controls_changed()

    def _flash_clicked(self, _=None) -> None:
        assert self.package is not None and self.port.value
        package, port = self.package, self.port.value
        self.flash_button.disabled = True
        self.upload.disabled = True
        self.refresh.disabled = True
        self.output.clear_output()
        self.progress.value = 5
        self.status.value = "<b>Status:</b> Flashing; do not disconnect USB or power"

        def append(message: str) -> None:
            self.output.append_stdout(message)
            if "Writing at" in message:
                self.progress.value = min(90, self.progress.value + 1)
            elif "Hash of data verified" in message:
                self.progress.value = 95

        def run() -> None:
            try:
                Esp32Flasher(append).flash(package, port)
                self.progress.value = 100
                self.status.value = (
                    f"<b>Complete:</b> ESP32 firmware {package.version} flashed and verified"
                )
            except Exception as exc:
                self.status.value = f"<b>Flash failed:</b> {exc}"
                append(f"Flash failed: {exc}\n")
                append("If connection failed, hold BOOT, tap RESET, release BOOT, and retry.\n")
            finally:
                self.upload.disabled = False
                self.refresh.disabled = False
                self._controls_changed()

        threading.Thread(target=run, name="esp32-update", daemon=True).start()

    def show(self) -> None:
        from IPython.display import display
        panel = self.widgets.VBox([
            self.widgets.HBox([self.port, self.refresh]),
            self.upload,
            self.status,
            self.confirm,
            self.flash_button,
            self.progress,
            self.output,
        ])
        display(panel)
