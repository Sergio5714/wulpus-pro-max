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

Format tracked project-owned ESP32 C sources using the sw uv environment.
"""

import argparse
import importlib.metadata
from pathlib import Path
import subprocess
import sys

DESCRIPTION = "Format tracked project-owned ESP32 C sources."
ROOT = Path(__file__).resolve().parents[1]
ROOTS = ("fw/esp32/main/", "fw/esp32/components/")
EXCLUDED = ("fw/esp32/components/msp430_programmer/ti/",)


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--fix", action="store_true", help="format files in place")
    modes.add_argument("--check", action="store_true", help="check without editing")
    args = parser.parse_args()
    try:
        # Use the formatter installed in this Python environment, not one from
        # ESP-IDF or an unrelated executable found earlier on PATH.
        distribution = importlib.metadata.distribution("clang-format")
        executable = next(
            distribution.locate_file(file) for file in distribution.files
            if str(file).replace("\\", "/") in (
                "clang_format/data/bin/clang-format",
                "clang_format/data/bin/clang-format.exe",
            )
        )
        tracked = subprocess.check_output(
            ["git", "ls-files", "-z", "--", *ROOTS], cwd=ROOT
        ).decode("utf-8").split("\0")
        files = sorted({name for name in tracked if name
                        and name.startswith(ROOTS)
                        and not name.startswith(EXCLUDED)
                        and Path(name).suffix in (".c", ".h")
                        and (ROOT / name).is_file()})
        if not files:
            print("No tracked ESP32 C sources found.")
            return 0
        options = ["-i"] if args.fix else ["--dry-run", "--Werror"]
        failed = 0
        for name in files:
            result = subprocess.run(
                [str(executable), "--style=file", *options, name], cwd=ROOT
            )
            failed += result.returncode != 0
        if args.fix:
            print(f"Formatted {len(files)} ESP32 source files in place.")
            return 0
        if failed:
            print(
                f"Checked {len(files)} ESP32 source files; "
                f"{failed} need formatting.",
                file=sys.stderr,
            )
            return 1
        print(f"Checked {len(files)} ESP32 source files; all are formatted.")
        return 0
    except (importlib.metadata.PackageNotFoundError, StopIteration):
        print("clang-format is missing; run through uv run --project sw.", file=sys.stderr)
        return 2
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Formatting failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
