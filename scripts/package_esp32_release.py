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


Create a validated WULPUS Pro Max ESP32-C6 release ZIP.
"""


from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


DESCRIPTION = "Create a validated WULPUS Pro Max ESP32-C6 release ZIP."
ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "fw" / "esp32"
IMAGES = (
    ("0x0", "bootloader.bin", Path("bootloader/bootloader.bin")),
    ("0x8000", "partition-table.bin", Path("partition_table/partition-table.bin")),
    ("0x10000", "wulpus-pro-fw.bin", Path("wulpus-pro-fw.bin")),
)
APP_DESC_MAGIC = b"\x32\x54\xcd\xab"


def compiled_app_version(image: bytes) -> str:
    """Read PROJECT_VER from the ESP-IDF application descriptor."""
    matches = []
    start = 0
    while True:
        offset = image.find(APP_DESC_MAGIC, start)
        if offset < 0:
            break
        # esp_app_desc_t places version at +16 and project_name at +48.
        if offset + 80 <= len(image):
            project = image[offset + 48:offset + 80].split(b"\0", 1)[0]
            if project == b"wulpus-pro-fw":
                raw_version = image[offset + 16:offset + 48].split(b"\0", 1)[0]
                try:
                    matches.append(raw_version.decode("ascii"))
                except UnicodeDecodeError:
                    pass
        start = offset + 1
    if len(matches) != 1:
        raise ValueError("Could not uniquely identify the ESP-IDF application descriptor")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--build-dir", type=Path, default=PROJECT / "build-xiao")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    version = (PROJECT / "firmware_version.txt").read_text(encoding="utf-8").strip()
    if len(version.split(".")) != 3 or not all(part.isdigit() for part in version.split(".")):
        raise SystemExit("firmware_version.txt must contain major.minor.patch")
    output = args.output or (
        ROOT / "releases" / f"wulpus-pro-max-esp32-{version}.zip"
    )

    files = []
    payloads = {}
    for offset, archive_name, relative_path in IMAGES:
        source = args.build_dir / relative_path
        if not source.is_file():
            raise SystemExit(f"Missing build output: {source}")
        payload = source.read_bytes()
        if archive_name == "wulpus-pro-fw.bin":
            compiled_version = compiled_app_version(payload)
            if compiled_version != version:
                raise SystemExit(
                    f"Compiled ESP32 application version is {compiled_version}, but "
                    f"firmware_version.txt is {version}; clean and rebuild build-xiao"
                )
        payloads[archive_name] = payload
        files.append({
            "offset": offset,
            "path": archive_name,
            "sha256": hashlib.sha256(payload).hexdigest(),
        })

    manifest = {
        "format_version": 1,
        "product": "WULPUS Pro Max",
        "chip": "esp32c6",
        "firmware_version": version,
        "flash": {
            "mode": "dio",
            "frequency": "80m",
            "size": "4MB",
            "files": files,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
        for name, payload in payloads.items():
            archive.writestr(name, payload)
    print(f"Created {output}")


if __name__ == "__main__":
    main()
