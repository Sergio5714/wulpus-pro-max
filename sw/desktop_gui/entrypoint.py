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


PyInstaller-friendly desktop application entry point.
"""

import multiprocessing

if __name__ == "__main__":
    # Frozen child processes must be dispatched before importing Qt/NumPy.
    multiprocessing.freeze_support()
    from desktop_gui.main import main

    raise SystemExit(main())
