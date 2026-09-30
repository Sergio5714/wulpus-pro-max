"""Build the native portable application on the current operating system."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", help="remove PyInstaller cache before building")
    args = parser.parse_args()
    sw = Path(__file__).resolve().parents[1]
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm"]
    if args.clean:
        command.append("--clean")
    command.append(str(sw / "desktop_gui" / "wulpus_desktop.spec"))
    return subprocess.call(command, cwd=sw)


if __name__ == "__main__":
    raise SystemExit(main())
