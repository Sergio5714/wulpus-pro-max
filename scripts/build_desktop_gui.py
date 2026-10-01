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


Build a native portable distribution, ZIP archive, and SHA-256 checksum.
"""

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    """Build on the host OS and package the complete onedir dependency tree."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--console",
        action="store_true",
        help="include a console for diagnosing packaged startup failures",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (args.output_dir or root / "sw" / "dist").resolve()
    output.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--distpath",
        str(output),
        "--workpath",
        str(root / "sw" / "build"),
    ]
    if args.clean:
        command.append("--clean")
    command.append(str(root / "sw" / "desktop_gui" / "wulpus_desktop.spec"))
    environment = dict(os.environ, WULPUS_DESKTOP_CONSOLE="1" if args.console else "0")
    subprocess.run(command, cwd=root / "sw", env=environment, check=True)
    name = f"WULPUS-Pro-Max-{platform.system().lower()}-{platform.machine().lower()}"
    archive = Path(
        shutil.make_archive(str(output / name), "zip", output, "WULPUS-Pro-Max")
    )
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    archive.with_suffix(".zip.sha256").write_text(
        f"{digest.hexdigest()}  {archive.name}\n", encoding="utf-8"
    )
    print(f"Distribution: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
