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


Offline integration tests for module wiring and plot modes.
"""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets

from desktop_gui.controller import SimulatorLink
from desktop_gui.window import MainWindow


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Create the shared offscreen Qt application."""
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_window_and_acquisition_mode_transitions(self):
        """Verify window construction and A/B-mode visualization transitions."""
        with (
            patch(
                "desktop_gui.window.default_links",
                return_value={"Simulator": SimulatorLink()},
            ),
            patch("desktop_gui.window.QtCore.QSettings") as settings,
        ):
            settings.return_value.value.return_value = "light"
            window = MainWindow(True)
        try:
            self.assertEqual(window.tabs.tabText(2), "Data Viewer")
            self.assertFalse(window.connection.connect.property("connected"))
            window.session.connect("Simulator")
            window.connection._connected(None)
            self.assertTrue(window.connection.connect.property("connected"))
            self.assertFalse(window.connection.connect.isEnabled())
            window.configuration.inputs["num_acqs"].setValue(2)
            tab = window.acquisition
            for mode in ("B-mode", "A-mode"):
                tab.mode.setCurrentText(mode)
                tab.start_acquisition()
                ticks = tab.plot.getAxis("left")._tickLevels
                self.assertEqual(ticks is None, mode == "A-mode")
                loop = QtCore.QEventLoop()
                tab.thread.finished.connect(loop.quit)
                QtCore.QTimer.singleShot(5000, loop.quit)
                loop.exec()
                self.assertIsNone(tab.worker)
                self.assertEqual(len(tab.result.frames), 2)
        finally:
            window.close()
