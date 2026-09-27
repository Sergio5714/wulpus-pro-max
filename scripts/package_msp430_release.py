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


Find, validate, and package a WULPUS Pro Max MSP430 TI-TXT build.
"""


from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "fw" / "msp430" / "wulpus_msp430_firmware"
VERSION_HEADER = PROJECT / "wulpus" / "firmware_version.h"
CHANGELOG = PROJECT / "CHANGELOG.md"
sys.path.insert(0, str(ROOT / "sw"))

from wulpus.msp430_update import make_image, parse_ti_txt


DESCRIPTION = "Find, validate, and package a WULPUS Pro Max MSP430 TI-TXT build."
VERSION_DEFINES = (
    "WULPUS_MSP_FW_VERSION_MAJOR",
    "WULPUS_MSP_FW_VERSION_MINOR",
    "WULPUS_MSP_FW_VERSION_PATCH",
)
HELLO_DEFINE = "WULPUS_MSP_FW_HELLO_VERSION"


def read_define(text: str, name: str) -> int:
    match = re.search(
        rf"^\s*#define\s+{re.escape(name)}\s+(\d+)\s*$", text, re.MULTILINE
    )
    if not match:
        raise ValueError(f"Could not read {name} from {VERSION_HEADER}")
    value = int(match.group(1))
    if not 0 <= value <= 255:
        raise ValueError(f"{name} must fit in one byte")
    return value


def source_version() -> tuple[str, bytes]:
    text = VERSION_HEADER.read_text(encoding="utf-8")
    parts = tuple(read_define(text, name) for name in VERSION_DEFINES)
    hello_version = read_define(text, HELLO_DEFINE)
    return ".".join(str(part) for part in parts), b"WVER" + bytes((hello_version, *parts))


def find_ti_txt(search_root: Path) -> list[Path]:
    candidates = []
    for path in search_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in (".txt", ".titxt"):
            try:
                first = next(
                    line.strip()
                    for line in path.read_text(encoding="utf-8-sig").splitlines()
                    if line.strip()
                )
            except (UnicodeDecodeError, StopIteration):
                continue
            if first.startswith("@"):
                candidates.append(path)
    return sorted(candidates)


def image_contains_marker(sections: list[tuple[int, bytes]], marker: bytes) -> bool:
    return sum(data.count(marker) for _, data in sections) == 1


def main() -> None:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--input", type=Path, help="TI-TXT file; otherwise discover it")
    parser.add_argument(
        "--search-dir", type=Path, default=PROJECT,
        help="directory searched recursively when --input is omitted",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "releases",
        help="directory for the .mspfw and .sha256 artifacts",
    )
    args = parser.parse_args()

    version, marker = source_version()
    changelog = CHANGELOG.read_text(encoding="utf-8")
    if not re.search(rf"^## \[{re.escape(version)}\](?:\s|$)", changelog, re.MULTILINE):
        raise SystemExit(
            f"MSP430 version {version} has no matching heading in {CHANGELOG}"
        )

    if args.input:
        candidates = [args.input]
    else:
        candidates = find_ti_txt(args.search_dir)
        if not candidates:
            raise SystemExit(f"No TI-TXT build found below {args.search_dir}")
        if len(candidates) > 1:
            listing = "\n".join(f"  {path}" for path in candidates)
            raise SystemExit(
                "Multiple TI-TXT builds found; select one with --input:\n" + listing
            )

    source = candidates[0]
    try:
        sections = parse_ti_txt(source.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise SystemExit(f"Invalid TI-TXT image {source}: {exc}") from exc
    if not image_contains_marker(sections, marker):
        marker_hex = " ".join(f"{byte:02X}" for byte in marker)
        raise SystemExit(
            f"Compiled image does not contain exactly one firmware marker for {version} "
            f"({marker_hex}); clean and rebuild the MSP430 Debug configuration"
        )

    image = make_image(sections)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"wulpus-pro-max-msp430-{version}.mspfw"
    output.write_bytes(image)
    digest = hashlib.sha256(image).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    print(f"Source:  {source}")
    print(f"Version: {version} (compiled marker verified)")
    print(f"Created: {output}")
    print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
