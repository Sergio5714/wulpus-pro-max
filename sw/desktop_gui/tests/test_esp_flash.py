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


Tests for in-process ESP32 firmware flashing.
"""

import unittest
from unittest import mock

from wulpus.esp32_update import Esp32FlashImage, Esp32ReleasePackage

from desktop_gui.esp_flash import flash_package


class EspFlashTests(unittest.TestCase):
    def test_uses_in_process_esptool_with_extracted_images(self):
        """Verify flashing invokes esptool with extracted package images."""
        package = Esp32ReleasePackage(
            "1.2.3",
            "dio",
            "80m",
            "4MB",
            (Esp32FlashImage(0, "bootloader.bin", "unused", b"image"),),
        )
        with mock.patch("desktop_gui.esp_flash.esptool.main") as main:
            flash_package(package, "COM10", lambda _message: None)
        arguments = main.call_args.args[0]
        self.assertEqual(arguments[:4], ["--chip", "esp32c6", "--port", "COM10"])
        self.assertIn("write_flash", arguments)
        self.assertIn("0x0", arguments)
        self.assertTrue(arguments[-1].endswith("bootloader.bin"))

    def test_nonzero_esptool_exit_is_an_error(self):
        """Verify a nonzero esptool exit becomes a flashing failure."""
        package = Esp32ReleasePackage("1.2.3", "dio", "80m", "4MB", ())
        with mock.patch(
            "desktop_gui.esp_flash.esptool.main", side_effect=SystemExit(2)
        ):
            with self.assertRaisesRegex(RuntimeError, "exit code 2"):
                flash_package(package, "COM10", lambda _message: None)

    def test_esptool_error_is_not_masked_by_windows_cleanup(self):
        """Verify cleanup does not replace the original esptool exception."""
        package = Esp32ReleasePackage(
            "1.2.3",
            "dio",
            "80m",
            "4MB",
            (Esp32FlashImage(0, "bootloader.bin", "unused", b"image"),),
        )
        held = []

        def fail_with_open_image(arguments):
            """Hold an image open while simulating an esptool failure."""
            held.append(open(arguments[-1], "rb"))
            raise RuntimeError("original esptool failure")

        try:
            with mock.patch(
                "desktop_gui.esp_flash.esptool.main", side_effect=fail_with_open_image
            ):
                with self.assertRaisesRegex(RuntimeError, "original esptool failure"):
                    flash_package(package, "COM10", lambda _message: None)
        finally:
            for stream in held:
                stream.close()


if __name__ == "__main__":
    unittest.main()
