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


Build the native portable application on the current operating system.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Preserve the old invocation while delegating to one packaging script."""
    root = Path(__file__).resolve().parents[2]
    return subprocess.call(
        [sys.executable, str(root / "scripts" / "build_desktop_gui.py"), *sys.argv[1:]],
        cwd=root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
