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


Format and lint desktop code with the pinned Ruff version.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    """Run Ruff linting and formatting in check-only or fix mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    targets = [
        "sw/desktop_gui",
        "scripts/format_desktop_gui.py",
        "scripts/build_desktop_gui.py",
        "scripts/package_desktop_gui_release.py",
    ]
    base = [sys.executable, "-m", "ruff"]
    subprocess.run(
        base
        + ["check", "--config", "sw/pyproject.toml"]
        + ([] if args.check else ["--fix"])
        + targets,
        cwd=root,
        check=True,
    )
    subprocess.run(
        base
        + ["format", "--config", "sw/pyproject.toml"]
        + (["--check"] if args.check else [])
        + targets,
        cwd=root,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
