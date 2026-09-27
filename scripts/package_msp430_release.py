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
import os
from pathlib import Path
import re
import sys
from typing import Optional
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "fw" / "msp430" / "wulpus_msp430_firmware"
VERSION_HEADER = PROJECT / "wulpus" / "firmware_version.h"
CHANGELOG = PROJECT / "CHANGELOG.md"
DRIVERLIB_LICENSE = PROJECT / "driverlib" / "license.txt"
PROJECT_LICENSE = ROOT / "sw" / "LICENSE"
CGT_VERSION = "21.6.0.LTS"
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


def find_ti_compiler_dir(explicit: Optional[Path]) -> Path:
    """Locate the exact TI compiler whose runtime is linked into the image."""
    candidates = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("TI_MSP430_CGT_DIR"):
        candidates.append(Path(os.environ["TI_MSP430_CGT_DIR"]))
    candidates.extend(
        Path(root) / relative
        for root in ("C:/ti", Path.home() / "ti", "/opt/ti")
        for relative in (
            f"ccs1100/ccs/tools/compiler/ti-cgt-msp430_{CGT_VERSION}",
            f"ccs/ccs/tools/compiler/ti-cgt-msp430_{CGT_VERSION}",
        )
    )
    candidates.extend(
        path
        for root in (Path("C:/ti"), Path.home() / "ti", Path("/opt/ti"))
        if root.is_dir()
        for path in root.glob(
            f"ccs*/ccs/tools/compiler/ti-cgt-msp430_{CGT_VERSION}"
        )
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    raise SystemExit(
        f"TI MSP430 compiler {CGT_VERSION} was not found. Install the configured "
        "compiler, pass --ti-compiler-dir, or set TI_MSP430_CGT_DIR."
    )


def ti_compliance_files(compiler_dir: Path) -> tuple[Path, Path]:
    manifest = compiler_dir / f"MSP430_RTS_{CGT_VERSION}_manifest.html"
    spdx_files = sorted(compiler_dir.glob("MSP430_RTS_21_6_0_LTS_*.spdx"))
    missing = []
    if not manifest.is_file():
        missing.append(str(manifest))
    if len(spdx_files) != 1:
        missing.append(
            f"exactly one MSP430_RTS_21_6_0_LTS_*.spdx in {compiler_dir}"
        )
    if missing:
        raise SystemExit("Missing TI compliance material: " + "; ".join(missing))
    return manifest, spdx_files[0]


def zip_add_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def main() -> None:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--input", type=Path, help="TI-TXT file; otherwise discover it")
    parser.add_argument(
        "--search-dir", type=Path, default=PROJECT,
        help="directory searched recursively when --input is omitted",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "releases",
        help="directory for the release .zip and .sha256 artifacts",
    )
    parser.add_argument(
        "--ti-compiler-dir", type=Path,
        help=f"TI MSP430 CGT {CGT_VERSION} directory containing its manifest/SPDX",
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
    compiler_dir = find_ti_compiler_dir(args.ti_compiler_dir)
    ti_manifest, ti_spdx = ti_compliance_files(compiler_dir)
    for required in (DRIVERLIB_LICENSE, PROJECT_LICENSE):
        if not required.is_file():
            raise SystemExit(f"Missing release license file: {required}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"wulpus-pro-max-msp430-{version}"
    firmware_name = f"{stem}.mspfw"
    firmware_digest = hashlib.sha256(image).hexdigest()
    notices = (
        "WULPUS Pro Max MSP430 firmware - third-party notices\n\n"
        f"This firmware was built with TI MSP430 Code Generation Tools {CGT_VERSION} "
        "for execution on a Texas Instruments MSP430 device. It incorporates Texas "
        "Instruments MSP430 DriverLib and runtime support library code.\n\n"
        "The complete DriverLib license, TI compiler/runtime manifest, and TI RTS SPDX "
        "inventory are included in the LICENSES directory. Names and trademarks of "
        "Texas Instruments and other contributors may not be used to endorse or "
        "promote this product without permission.\n"
    ).encode("utf-8")
    members = {
        firmware_name: image,
        "LICENSE": PROJECT_LICENSE.read_bytes(),
        "THIRD_PARTY_NOTICES.txt": notices,
        "LICENSES/TI-MSP430-DriverLib-BSD-3-Clause.txt": DRIVERLIB_LICENSE.read_bytes(),
        f"LICENSES/{ti_manifest.name}": ti_manifest.read_bytes(),
        f"LICENSES/{ti_spdx.name}": ti_spdx.read_bytes(),
    }
    members["SHA256SUMS.txt"] = (
        f"{firmware_digest}  {firmware_name}\n".encode("ascii")
    )
    output = args.output_dir / f"{stem}.zip"
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in members.items():
            zip_add_bytes(archive, name, data)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    print(f"Source:  {source}")
    print(f"Version: {version} (compiled marker verified)")
    print(f"Created: {output}")
    print(f"TI CGT:  {compiler_dir}")
    print(f"SHA-256: {digest} (release ZIP)")


if __name__ == "__main__":
    main()
