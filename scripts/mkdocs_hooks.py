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

MkDocs hooks for values derived from repository metadata.
"""

import re
from pathlib import Path


RELEASE_HEADING = re.compile(r"^## \[(?!Unreleased\])([^]]+)\](?: - .+)?$", re.MULTILINE)


def _latest_release(changelog: Path) -> str:
    match = RELEASE_HEADING.search(changelog.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError(f"No released version found in {changelog}")
    return match.group(1)


def on_page_markdown(markdown, page, config, files):
    """Replace version placeholders with the latest changelog releases."""
    repository_root = Path(config.config_file_path).resolve().parent
    versions = {
        "{{ platform_version }}": _latest_release(repository_root / "CHANGELOG.md"),
        "{{ documentation_version }}": _latest_release(
            repository_root / "docs" / "CHANGELOG.md"
        ),
    }
    for placeholder, version in versions.items():
        markdown = markdown.replace(placeholder, version)
    return markdown
