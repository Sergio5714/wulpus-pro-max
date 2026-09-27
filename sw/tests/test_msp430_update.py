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

Tests for validated MSP430 release ZIP loading.
"""

import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wulpus.msp430_update import HEADER, MSP_IMAGE_MAGIC, load_image, load_release_zip


def valid_image():
    return HEADER.pack(MSP_IMAGE_MAGIC, 1, HEADER.size, 0x5043, HEADER.size,
                       0, 0, 0)


def package_bytes(*, corrupt=False, checksum=True, duplicate_firmware=False,
                  unsafe=False):
    image = valid_image()
    firmware_name = "wulpus-pro-max-msp430-1.1.0.mspfw"
    digest = hashlib.sha256(image).hexdigest()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(firmware_name, image + (b"bad" if corrupt else b""))
        if checksum:
            archive.writestr("SHA256SUMS.txt", f"{digest}  {firmware_name}\n")
        archive.writestr("THIRD_PARTY_NOTICES.txt", "notices")
        if duplicate_firmware:
            archive.writestr("other.mspfw", image)
        if unsafe:
            archive.writestr("../outside.txt", "unsafe")
    return stream.getvalue()


class Msp430PackageTests(unittest.TestCase):
    def test_valid_package(self):
        self.assertEqual(load_release_zip(package_bytes()), valid_image())

    def test_load_image_accepts_release_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release.zip"
            path.write_bytes(package_bytes())
            self.assertEqual(load_image(path), valid_image())

    def test_checksum_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            load_release_zip(package_bytes(corrupt=True))

    def test_missing_checksum_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no SHA256SUMS"):
            load_release_zip(package_bytes(checksum=False))

    def test_multiple_firmware_images_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            load_release_zip(package_bytes(duplicate_firmware=True))

    def test_unsafe_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsafe path"):
            load_release_zip(package_bytes(unsafe=True))


if __name__ == "__main__":
    unittest.main()
