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

Tests for validated ESP32 release packages and flash-command construction.
"""

import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wulpus.esp32_update import Esp32Flasher, Esp32ReleasePackage


def package_bytes(*, corrupt=False, offset="0x0", version="1.2.0"):
    content = {
        "bootloader.bin": b"bootloader",
        "partition-table.bin": b"partitions",
        "wulpus-pro-fw.bin": b"application",
    }
    layout = ((offset, "bootloader.bin"), ("0x8000", "partition-table.bin"),
              ("0x10000", "wulpus-pro-fw.bin"))
    manifest = {
        "format_version": 1,
        "product": "WULPUS Pro Max",
        "chip": "esp32c6",
        "firmware_version": version,
        "flash": {
            "mode": "dio", "frequency": "80m", "size": "4MB",
            "files": [
                {"offset": address, "path": name,
                 "sha256": hashlib.sha256(content[name]).hexdigest()}
                for address, name in layout
            ],
        },
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, data in content.items():
            archive.writestr(name, data + (b"bad" if corrupt and name == "bootloader.bin" else b""))
    return stream.getvalue()


class Esp32PackageTests(unittest.TestCase):
    def test_valid_package_and_command(self):
        package = Esp32ReleasePackage.load(package_bytes())
        self.assertEqual(package.version, "1.2.0")
        command = Esp32Flasher().command(package, "COM10", Path("images"))
        self.assertIn("esp32c6", command)
        self.assertEqual(command[-6::2], ["0x0", "0x8000", "0x10000"])

    def test_checksum_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            Esp32ReleasePackage.load(package_bytes(corrupt=True))

    def test_unexpected_offset_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unexpected flash layout"):
            Esp32ReleasePackage.load(package_bytes(offset="0x1000"))

    def test_invalid_version_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "semantic firmware version"):
            Esp32ReleasePackage.load(package_bytes(version="next.release.now"))


if __name__ == "__main__":
    unittest.main()
