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


Download and verify the pinned espflash release for the host platform.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ESPFLASH_VERSION = "4.7.0"
_RELEASE_BASE = (
    f"https://github.com/esp-rs/espflash/releases/download/v{ESPFLASH_VERSION}"
)
_ASSETS = {
    ("win32", "x86_64"): (
        "espflash-x86_64-pc-windows-msvc.zip",
        "2b10333e4f4f1a26024259b0cc1942ba17f27b3c530621c6111f4c10ac70213e",
    ),
    ("linux", "x86_64"): (
        "espflash-x86_64-unknown-linux-gnu.zip",
        "8ab3bafeb212ccb1d7a9c422936b9bc86f8b00fe2731053ed8ab875c8d2f0c4d",
    ),
    ("linux", "aarch64"): (
        "espflash-aarch64-unknown-linux-gnu.zip",
        "3158e1c78f3e80ad0389c1d925b69736e1955a60b3cadf932e6d0d74d731b448",
    ),
    ("darwin", "x86_64"): (
        "espflash-x86_64-apple-darwin.zip",
        "3e3ca415f15f58000d351ca8dd22137c2d04384a8153f65b831553074601ee03",
    ),
    ("darwin", "aarch64"): (
        "espflash-aarch64-apple-darwin.zip",
        "4313a4cf3e05036d4e1d8edeef938a11661eb5b9ba5759cabbf48ad4f6fbc180",
    ),
}


def _architecture() -> str:
    """Normalize common platform architecture names."""
    machine = platform.machine().lower()
    return {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)


def _sha256(path: Path) -> str:
    """Hash a file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> None:
    """Download over verified HTTPS, using Windows trust as a fallback."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "wulpus-pro-max-build"},
    )
    try:
        with (
            urllib.request.urlopen(request) as response,
            destination.open("wb") as out,
        ):
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        return
    except urllib.error.URLError as error:
        certificate_error = isinstance(error.reason, ssl.SSLCertVerificationError)
        curl = shutil.which("curl.exe") if os.name == "nt" else None
        if not certificate_error or curl is None:
            raise

    print(
        "Python could not verify the HTTPS certificate; "
        "retrying with the Windows certificate store.",
        file=sys.stderr,
    )
    subprocess.run(
        [
            curl,
            "--fail",
            "--location",
            "--proto",
            "=https",
            "--show-error",
            "--silent",
            "--output",
            str(destination),
            url,
        ],
        check=True,
    )


def ensure_espflash(root: Path | None = None, *, force: bool = False) -> Path:
    """Return a verified host espflash executable, downloading when needed."""
    key = (sys.platform, _architecture())
    try:
        asset, expected_hash = _ASSETS[key]
    except KeyError as error:
        raise RuntimeError(f"Unsupported espflash host: {key[0]} {key[1]}") from error

    repository = root or Path(__file__).resolve().parents[1]
    cache = repository / "sw" / ".tools" / "espflash" / ESPFLASH_VERSION
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / asset
    executable = cache / ("espflash.exe" if os.name == "nt" else "espflash")

    valid_archive = archive.is_file() and _sha256(archive) == expected_hash
    if force or not valid_archive:
        temporary = archive.with_suffix(".download")
        try:
            _download(f"{_RELEASE_BASE}/{asset}", temporary)
            actual_hash = _sha256(temporary)
            if actual_hash != expected_hash:
                raise RuntimeError(f"espflash archive checksum mismatch: {actual_hash}")
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)

    if force or not executable.is_file():
        expected_name = executable.name
        with zipfile.ZipFile(archive) as package:
            matches = [
                name for name in package.namelist() if Path(name).name == expected_name
            ]
            if len(matches) != 1:
                raise RuntimeError(f"espflash archive has no unique {expected_name}")
            executable.write_bytes(package.read(matches[0]))
        if os.name != "nt":
            executable.chmod(executable.stat().st_mode | 0o111)
    return executable.resolve()


def main() -> int:
    """Fetch the pinned executable and print its local path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="download again")
    args = parser.parse_args()
    print(ensure_espflash(force=args.force))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
