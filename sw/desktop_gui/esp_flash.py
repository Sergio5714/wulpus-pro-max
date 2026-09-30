"""ESP32 flashing that also works inside a frozen PyInstaller process."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import gc
import io
from pathlib import Path
import shutil
import tempfile
from typing import Callable

import esptool


class _LineWriter(io.TextIOBase):
    def __init__(self, output: Callable[[str], None]):
        self.output = output
        self.pending = ""

    def write(self, text):
        self.pending += str(text)
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            self.output(line + "\n")
        return len(text)

    def flush(self):
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
            "--chip", "esp32c6", "--port", port, "--baud", str(baud),
            "--before", "default_reset", "--after", "hard_reset",
            "write_flash", "--flash_mode", package.flash_mode,
            "--flash_freq", package.flash_frequency,
            "--flash_size", package.flash_size,
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
                raise RuntimeError(f"esptool failed with exit code {error.code}") from error
        finally:
            writer.flush()
    finally:
        # Release parser/file objects created by esptool, then clean up without
        # replacing a useful flashing exception with a Windows cleanup error.
        gc.collect()
        shutil.rmtree(directory, ignore_errors=True)
