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

Package the acquisition and WiFi host PCB fabrication releases.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import zipfile


DESCRIPTION = "Package the acquisition and WiFi host PCB fabrication releases."
ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "hw"
ACQUISITION = HW / "wulpus_pro_acq_pcb_dev_board"
WIFI_HOST = HW / "wulpus_wifi_host_pcb"


def latest_changelog_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", text, re.MULTILINE)
    if not match:
        raise ValueError(f"No semantic release heading found in {path}")
    return match.group(1)


def files_below(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise ValueError(f"Required directory does not exist: {directory}")
    files = sorted(path for path in directory.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"Required directory is empty: {directory}")
    return files


def create_package(output: Path, project: Path, license_path: Path,
                   include_changelog: bool) -> str:
    inputs: list[tuple[Path, Path]] = []
    for directory_name in ("fabrication_outputs", "docs"):
        directory = project / directory_name
        for source in files_below(directory):
            inputs.append((source, Path(directory_name) / source.relative_to(directory)))
    if not license_path.is_file():
        raise ValueError(f"Required license does not exist: {license_path}")
    inputs.append((license_path, Path(license_path.name)))
    if include_changelog:
        changelog = project / "CHANGELOG.md"
        if not changelog.is_file():
            raise ValueError(f"Required changelog does not exist: {changelog}")
        inputs.append((changelog, Path("CHANGELOG.md")))

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, archive_path in inputs:
            archive.write(source, archive_path.as_posix())

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    return digest


def main() -> None:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--acquisition-version", default="1.0.0")
    parser.add_argument(
        "--wifi-host-version",
        default=latest_changelog_version(WIFI_HOST / "CHANGELOG.md"),
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "releases")
    args = parser.parse_args()

    version_pattern = re.compile(r"\d+\.\d+\.\d+")
    for name, value in (
        ("acquisition", args.acquisition_version),
        ("WiFi host", args.wifi_host_version),
    ):
        if not version_pattern.fullmatch(value):
            raise SystemExit(f"Invalid {name} PCB version: {value}")

    recorded_wifi_version = latest_changelog_version(WIFI_HOST / "CHANGELOG.md")
    if args.wifi_host_version != recorded_wifi_version:
        raise SystemExit(
            f"WiFi host version {args.wifi_host_version} does not match the latest "
            f"CHANGELOG release {recorded_wifi_version}"
        )

    packages = (
        (
            args.output_dir
            / f"wulpus-pro-max-acquisition-pcb-{args.acquisition_version}.zip",
            ACQUISITION,
            HW / "LICENSE_ETH",
            False,
        ),
        (
            args.output_dir
            / f"wulpus-pro-max-wifi-host-pcb-{args.wifi_host_version}.zip",
            WIFI_HOST,
            HW / "LICENSE",
            True,
        ),
    )
    for output, project, license_path, include_changelog in packages:
        digest = create_package(output, project, license_path, include_changelog)
        print(f"Created: {output}")
        print(f"SHA-256: {digest}")


if __name__ == "__main__":
    main()
