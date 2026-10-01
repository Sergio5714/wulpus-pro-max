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


Standalone WULPUS Pro Max desktop application.
"""

import re
from pathlib import Path


def _project_version():
    """Read the application version from the bundled software project metadata."""
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    project = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", text)
    version = re.search(r'^version\s*=\s*"([^"]+)"', project.group(1), re.MULTILINE)
    if version is None:
        raise RuntimeError(f"No project version found in {pyproject}")
    return version.group(1)


APP_NAME = "WULPUS Pro Max"
APP_VERSION = _project_version()
