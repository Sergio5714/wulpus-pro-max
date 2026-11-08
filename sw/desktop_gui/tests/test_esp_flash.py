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


Tests for ESP32 firmware flashing through espflash.
"""

import unittest
from pathlib import Path
from unittest import mock

from wulpus.esp32_update import Esp32FlashImage, Esp32ReleasePackage

from desktop_gui.esp_flash import flash_package


class _Process:
    def __init__(self, result=0):
        """Provide the subprocess surface used by the flashing adapter."""
        self.stdout = iter(["progress\n"])
        self.result = result

    def wait(self):
        """Return the configured process result."""
        return self.result


class EspFlashTests(unittest.TestCase):
    def test_writes_package_images_in_one_bootloader_session(self):
        """Write each image sequentially and reset only after the final image."""
        package = Esp32ReleasePackage(
            "1.2.3",
            "dio",
            "80m",
            "4MB",
            (
                Esp32FlashImage(0, "bootloader.bin", "unused", b"boot"),
                Esp32FlashImage(0x8000, "partition.bin", "unused", b"part"),
                Esp32FlashImage(0x10000, "app.bin", "unused", b"app"),
            ),
        )
        output = []
        with (
            mock.patch(
                "desktop_gui.esp_flash.espflash_executable",
                return_value=Path("espflash"),
            ),
            mock.patch(
                "desktop_gui.esp_flash.subprocess.Popen",
                side_effect=lambda *_args, **_kwargs: _Process(),
            ) as popen,
        ):
            flash_package(package, "COM10", output.append)
        commands = [call.args[0] for call in popen.call_args_list]
        self.assertEqual(len(commands), 3)
        self.assertEqual(commands[0][1:4], ["write-bin", "--port", "COM10"])
        self.assertEqual(commands[0][-2], "0x0")
        self.assertEqual(commands[1][-2], "0x8000")
        self.assertEqual(commands[2][-2], "0x10000")
        self.assertEqual(
            commands[0][commands[0].index("--before") + 1], "default-reset"
        )
        self.assertEqual(commands[1][commands[1].index("--before") + 1], "no-reset")
        self.assertEqual(commands[0][commands[0].index("--after") + 1], "no-reset")
        self.assertEqual(commands[2][commands[2].index("--after") + 1], "hard-reset")
        self.assertIn("progress\n", output)

    def test_nonzero_espflash_exit_is_an_error(self):
        """Convert a nonzero espflash result into an operation failure."""
        package = Esp32ReleasePackage(
            "1.2.3",
            "dio",
            "80m",
            "4MB",
            (Esp32FlashImage(0, "bootloader.bin", "unused", b"image"),),
        )
        with (
            mock.patch(
                "desktop_gui.esp_flash.espflash_executable",
                return_value=Path("espflash"),
            ),
            mock.patch(
                "desktop_gui.esp_flash.subprocess.Popen",
                return_value=_Process(2),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "exit code 2"):
                flash_package(package, "COM10", lambda _message: None)

    def test_auto_falls_back_to_esptool_for_source_run(self):
        """Use optional esptool when a source run cannot find espflash."""
        package = Esp32ReleasePackage(
            "1.2.3",
            "dio",
            "80m",
            "4MB",
            (Esp32FlashImage(0, "bootloader.bin", "unused", b"image"),),
        )
        with (
            mock.patch.dict(
                "desktop_gui.esp_flash.os.environ",
                {"WULPUS_ESP32_FLASH_TOOL": "auto"},
                clear=True,
            ),
            mock.patch(
                "desktop_gui.esp_flash.espflash_executable",
                side_effect=FileNotFoundError,
            ),
            mock.patch("desktop_gui.esp_flash._run") as run,
        ):
            flash_package(package, "COM10", lambda _message: None)
        command = run.call_args.args[0]
        self.assertEqual(command[1:3], ["-m", "esptool"])
        self.assertIn("write_flash", command)

    def test_packaged_release_rejects_esptool_selection(self):
        """Never permit a frozen release to select the unbundled GPL tool."""
        package = Esp32ReleasePackage("1.2.3", "dio", "80m", "4MB", ())
        with (
            mock.patch.dict(
                "desktop_gui.esp_flash.os.environ",
                {"WULPUS_ESP32_FLASH_TOOL": "esptool"},
                clear=True,
            ),
            mock.patch("desktop_gui.esp_flash.sys.frozen", True, create=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "only embedded espflash"):
                flash_package(package, "COM10", lambda _message: None)


if __name__ == "__main__":
    unittest.main()
