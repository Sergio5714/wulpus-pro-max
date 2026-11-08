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


Command-line entry point for the desktop application.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import APP_NAME, APP_VERSION
from .esp_flash import ESPFLASH_ENVIRONMENT, FLASH_TOOL_ENVIRONMENT, FLASH_TOOLS

ICON_NAME = "logo_raw_echoes_icon.png"


def application_icon_path() -> Path:
    """Return the application icon path in source and frozen executions."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets" / ICON_NAME


def main(argv=None):
    """Parse launch options, construct the Qt application, and run its event loop."""
    parser = argparse.ArgumentParser(description="WULPUS Pro Max desktop GUI")
    parser.add_argument(
        "--simulator", action="store_true", help="enable the development simulator"
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="construct the GUI offline and exit after processing events",
    )
    parser.add_argument(
        "--esp32-flasher",
        choices=FLASH_TOOLS,
        default="auto",
        help="source-run ESP32 flasher; packaged releases use espflash",
    )
    parser.add_argument(
        "--espflash",
        help="path to espflash for a source run",
    )
    args = parser.parse_args(argv)
    os.environ[FLASH_TOOL_ENVIRONMENT] = args.esp32_flasher
    if args.espflash:
        os.environ[ESPFLASH_ENVIRONMENT] = args.espflash
    # Keep help/argument validation independent of Qt and hardware imports.
    from PySide6 import QtCore, QtGui, QtWidgets

    from .controller import SessionController, SimulatorLink
    from .window import MainWindow

    app = QtWidgets.QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QtGui.QIcon(str(application_icon_path())))
    app.setStyle("Fusion")
    session = (
        SessionController({"Simulator": SimulatorLink()}) if args.smoke_test else None
    )
    window = MainWindow(args.simulator, session=session)
    window.show()
    if args.smoke_test:
        # Close the window instead of only stopping the event loop so that the
        # normal shutdown path also tears down discovery and worker resources.
        QtCore.QTimer.singleShot(1000, window.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
