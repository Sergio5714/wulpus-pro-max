from unittest import mock
import unittest

from wulpus.esp32_update import Esp32FlashImage, Esp32ReleasePackage

from desktop_gui.esp_flash import flash_package


class EspFlashTests(unittest.TestCase):
    def test_uses_in_process_esptool_with_extracted_images(self):
        package = Esp32ReleasePackage(
            "1.2.3", "dio", "80m", "4MB",
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
        package = Esp32ReleasePackage("1.2.3", "dio", "80m", "4MB", ())
        with mock.patch("desktop_gui.esp_flash.esptool.main", side_effect=SystemExit(2)):
            with self.assertRaisesRegex(RuntimeError, "exit code 2"):
                flash_package(package, "COM10", lambda _message: None)

    def test_esptool_error_is_not_masked_by_windows_cleanup(self):
        package = Esp32ReleasePackage(
            "1.2.3", "dio", "80m", "4MB",
            (Esp32FlashImage(0, "bootloader.bin", "unused", b"image"),),
        )
        held = []

        def fail_with_open_image(arguments):
            held.append(open(arguments[-1], "rb"))
            raise RuntimeError("original esptool failure")

        try:
            with mock.patch("desktop_gui.esp_flash.esptool.main", side_effect=fail_with_open_image):
                with self.assertRaisesRegex(RuntimeError, "original esptool failure"):
                    flash_package(package, "COM10", lambda _message: None)
        finally:
            for stream in held:
                stream.close()


if __name__ == "__main__":
    unittest.main()
