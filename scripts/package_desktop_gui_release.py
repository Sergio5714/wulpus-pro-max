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


Build and package the versioned one-file desktop GUI release.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SW = ROOT / "sw"
DEFAULT_OUTPUT = ROOT / "releases"
DESCRIPTION = "Build the desktop GUI release executable and SHA-256 checksum."


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    """Build the one-file application and write its checksum sidecar."""
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    sys.path.insert(0, str(SW))
    from desktop_gui import APP_VERSION

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_desktop_gui.py"),
            "--clean",
            "--onefile",
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        check=True,
    )

    executable = output / f"WULPUS-Pro-Max-{APP_VERSION}.exe"
    if not executable.is_file():
        raise SystemExit(f"Expected build output was not created: {executable}")

    checksum = executable.with_suffix(executable.suffix + ".sha256")
    digest = sha256(executable)
    checksum.write_text(f"{digest}  {executable.name}\n", encoding="utf-8")
    print(f"Executable: {executable}")
    print(f"Checksum: {checksum}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
