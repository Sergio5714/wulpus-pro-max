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


Selectable ESP32 flashing for source runs and embedded espflash for releases.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

ESPFLASH_ENVIRONMENT = "WULPUS_ESPFLASH_EXECUTABLE"
FLASH_TOOL_ENVIRONMENT = "WULPUS_ESP32_FLASH_TOOL"
FLASH_TOOLS = ("auto", "espflash", "esptool")
ESPFLASH_VERSION = "4.7.0"


def espflash_executable() -> Path:
    """Locate espflash in an override, frozen bundle, or development PATH."""
    override = os.environ.get(ESPFLASH_ENVIRONMENT)
    if override:
        path = Path(override).resolve()
        if path.is_file():
            return path
        raise FileNotFoundError(f"espflash executable does not exist: {path}")

    executable_name = "espflash.exe" if os.name == "nt" else "espflash"
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        path = Path(bundle) / executable_name
        if path.is_file():
            return path

    cached = (
        Path(__file__).resolve().parents[1]
        / ".tools"
        / "espflash"
        / ESPFLASH_VERSION
        / executable_name
    )
    if cached.is_file():
        return cached

    installed = shutil.which("espflash")
    if installed:
        return Path(installed).resolve()
    raise FileNotFoundError(
        "espflash is unavailable; rebuild the application with an embedded binary"
    )


def _run(command: list[str], output: Callable[[str], None]) -> None:
    """Run a flashing command and stream its combined output."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        output(line)
    result = process.wait()
    if result:
        raise RuntimeError(f"firmware flasher failed with exit code {result}")


def _write_images(package, directory: Path) -> list[tuple[object, Path]]:
    """Extract validated package images into a temporary directory."""
    images = []
    for image in package.images:
        path = directory / image.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image.data)
        images.append((image, path))
    return images


def _flash_with_esptool(package, port, output, baud, directory):
    """Flash a source run through the optional esptool dependency group."""
    command = [
        sys.executable,
        "-m",
        "esptool",
        "--chip",
        "esp32c6",
        "--port",
        port,
        "--baud",
        str(baud),
        "--before",
        "default_reset",
        "--after",
        "hard_reset",
        "write_flash",
        "--flash_mode",
        package.flash_mode,
        "--flash_freq",
        package.flash_frequency,
        "--flash_size",
        package.flash_size,
    ]
    for image, path in _write_images(package, directory):
        command.extend((hex(image.offset), str(path)))
    _run(command, output)


def _flash_with_espflash(package, port, output, baud, directory, executable):
    """Flash sequential images through espflash in one bootloader session."""
    images = _write_images(package, directory)
    for index, (image, path) in enumerate(images):
        first = index == 0
        last = index == len(images) - 1
        output(
            f"Writing {image.path} at {hex(image.offset)} ({len(image.data)} bytes)\n"
        )
        _run(
            [
                str(executable),
                "write-bin",
                "--port",
                port,
                "--chip",
                "esp32c6",
                "--baud",
                str(baud),
                "--before",
                "default-reset" if first else "no-reset",
                "--after",
                "hard-reset" if last else "no-reset",
                "--non-interactive",
                "--skip-update-check",
                hex(image.offset),
                str(path),
            ],
            output,
        )


def flash_package(package, port: str, output: Callable[[str], None], baud=460800):
    """Flash with the selected source tool or the frozen embedded espflash."""
    if not port:
        raise ValueError("Select an ESP32-C6 serial port")
    tool = os.environ.get(FLASH_TOOL_ENVIRONMENT, "auto").lower()
    if tool not in FLASH_TOOLS:
        raise ValueError(f"Unsupported ESP32 flash tool: {tool}")
    frozen = bool(getattr(sys, "frozen", False))
    if frozen and tool == "esptool":
        raise RuntimeError("Packaged releases support only embedded espflash")

    with tempfile.TemporaryDirectory(prefix="wulpus-espflash-") as temporary:
        directory = Path(temporary)
        if tool in ("auto", "espflash"):
            try:
                executable = espflash_executable()
            except FileNotFoundError:
                if tool == "espflash" or frozen:
                    raise
            else:
                output("Using espflash\n")
                _flash_with_espflash(package, port, output, baud, directory, executable)
                return
        output("Using esptool\n")
        _flash_with_esptool(package, port, output, baud, directory)
