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


ESP32 flashing that also works inside a frozen PyInstaller process.
"""

from __future__ import annotations

import gc
import io
import shutil
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Callable

import esptool


class _LineWriter(io.TextIOBase):
    def __init__(self, output: Callable[[str], None]):
        """Initialize a line-buffered adapter around an output callback."""
        self.output = output
        self.pending = ""

    def write(self, text):
        """Buffer text and forward every complete line to the callback."""
        self.pending += str(text)
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            self.output(line + "\n")
        return len(text)

    def flush(self):
        """Forward any incomplete buffered line to the callback."""
        if self.pending:
            self.output(self.pending)
            self.pending = ""


def flash_package(package, port: str, output: Callable[[str], None], baud=460800):
    """Flash a validated package through esptool's supported Python entry point."""
    if not port:
        raise ValueError("Select an ESP32-C6 serial port")
    # Do not use TemporaryDirectory here. esptool opens the image paths while
    # parsing its arguments and can retain those handles when connection or
    # flashing fails. On Windows/Python 3.9, TemporaryDirectory then raises a
    # misleading WinError 267 during cleanup and hides the actual esptool error.
    directory = Path(tempfile.mkdtemp(prefix="wulpus-esp32-"))
    try:
        arguments = [
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
        for image in package.images:
            path = directory / image.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(image.data)
            arguments.extend((hex(image.offset), str(path)))
        writer = _LineWriter(output)
        try:
            with redirect_stdout(writer), redirect_stderr(writer):
                esptool.main(arguments)
        except SystemExit as error:
            if error.code not in (None, 0):
                raise RuntimeError(
                    f"esptool failed with exit code {error.code}"
                ) from error
        finally:
            writer.flush()
    finally:
        # Release parser/file objects created by esptool, then clean up without
        # replacing a useful flashing exception with a Windows cleanup error.
        gc.collect()
        shutil.rmtree(directory, ignore_errors=True)
