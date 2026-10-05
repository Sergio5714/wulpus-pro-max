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

from desktop_gui import APP_VERSION
from desktop_gui.controller import SimulatorLink
from desktop_gui.models import TransportCapabilities, build_config
from desktop_gui.txrx import TxRxConfigDialog
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
            self.assertRegex(APP_VERSION, r"^\d+\.\d+\.\d+$")
            self.assertEqual(window.windowTitle(), f"WULPUS Pro Max {APP_VERSION}")
            self.assertEqual(window.tabs.tabText(2), "Data Viewer")
            self.assertFalse(window.connection.connect.property("connected"))
            window.session.connect("Simulator")
            window.connection._connected(None)
            self.assertTrue(window.connection.connect.property("connected"))
            self.assertFalse(window.connection.connect.isEnabled())
            window.configuration.inputs["num_acqs"].setValue(2)
            tab = window.acquisition
            tab.band_pass_range.set_values(750, 2750)
            self.assertEqual(tab.low_cutoff.value(), 0.75)
            self.assertEqual(tab.high_cutoff.value(), 2.75)
            tab.low_cutoff.setValue(1.0)
            self.assertEqual(tab.band_pass_range.low, 1000)
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

    def test_firmware_versions_refresh_on_connect_and_after_acquisition(self):
        """Keep desktop firmware reporting in step with MSP430 discovery."""
        capabilities = TransportCapabilities(firmware_info=True)
        with (
            patch(
                "desktop_gui.window.default_links",
                return_value={"Simulator": SimulatorLink()},
            ),
            patch("desktop_gui.window.QtCore.QSettings") as settings,
            patch.dict(
                "desktop_gui.controller.CAPABILITIES",
                {"Simulator": capabilities},
            ),
        ):
            settings.return_value.value.return_value = "light"
            window = MainWindow(True)
        try:
            with (
                patch.dict(
                    "desktop_gui.controller.CAPABILITIES",
                    {"Simulator": capabilities},
                ),
                patch.object(window.firmware, "load_versions") as load_versions,
            ):
                window.session.connect("Simulator")
                window.update_capabilities()
                self.app.processEvents()
                load_versions.assert_called_once_with()

                window.operation_changed(True)
                load_versions.assert_called_once_with()
                window.operation_changed(False)
                self.assertEqual(load_versions.call_count, 2)
        finally:
            window.close()

    def test_tx_rx_editor_separates_channel_groups(self):
        """Verify TX and RX selectors use distinct two-row channel groups."""
        dialog = TxRxConfigDialog(0, 0x0001, 0x8000)
        try:
            self.assertEqual(dialog.tx_group.title(), "TX channels")
            self.assertEqual(dialog.rx_group.title(), "RX channels")
            self.assertGreaterEqual(dialog.layout().spacing(), 10)
            tx_grid = dialog.tx_group.layout()
            rx_grid = dialog.rx_group.layout()
            self.assertEqual(tx_grid.getItemPosition(0)[:2], (0, 0))
            self.assertEqual(tx_grid.getItemPosition(8)[:2], (1, 0))
            self.assertEqual(rx_grid.getItemPosition(0)[:2], (0, 0))
            self.assertEqual(rx_grid.getItemPosition(8)[:2], (1, 0))
        finally:
            dialog.close()

    def test_configuration_groups_and_live_timing(self):
        """Verify setting groups and timing relationships update immediately."""
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
            editor = window.configuration
            self.assertEqual(
                [editor.settings_tabs.tabText(index) for index in range(4)],
                ["Acquisition", "Excitation", "TX/RX", "Advanced"],
            )
            acquisition_settings = editor.settings_tabs.widget(0)
            self.assertTrue(
                acquisition_settings.isAncestorOf(editor.inputs["vga_rc_prech_cyc"])
            )
            self.assertTrue(
                acquisition_settings.isAncestorOf(editor.inputs["vga_slope_code"])
            )
            tx_rx_settings = editor.settings_tabs.widget(2)
            self.assertTrue(
                tx_rx_settings.isAncestorOf(editor.inputs["num_txrx_configs"])
            )
            self.assertEqual(tx_rx_settings.layout().indexOf(editor.txrx_toolbar), 0)
            self.assertTrue(editor.txrx_toolbar.isAncestorOf(editor.add_config_button))
            self.assertTrue(
                editor.txrx_toolbar.isAncestorOf(editor.remove_config_button)
            )
            self.assertTrue(editor.txrx_toolbar.isAncestorOf(editor.load_txrx_button))
            self.assertTrue(editor.txrx_toolbar.isAncestorOf(editor.save_txrx_button))
            self.assertTrue(editor.inputs["restart_capt"].isHidden())
            self.assertFalse(editor.inputs["num_samples"].isEnabled())
            editor.set_config(build_config({"num_samples": 100}))
            self.assertEqual(editor.inputs["num_samples"].value(), 400)
            editor.inputs["start_ppg"].setValue(100)
            editor.inputs["pulse_freq"].setValue(1_000_000)
            editor.inputs["num_pulses"].setValue(4)
            editor.inputs["start_hvmuxrx"].setValue(106)
            editor.inputs["turnon_adc"].setValue(20)
            editor.inputs["start_adcsampl"].setValue(110)
            editor.inputs["dcdc_turnon"].setValue(200_000)
            editor.inputs["meas_period"].setValue(250_000)
            timing = editor.timing_diagram.timing_snapshot()
            self.assertEqual(timing["pulse_start"], 100)
            self.assertEqual(timing["pulse_end"], 104)
            self.assertEqual(timing["mux_rx"], 106)
            self.assertEqual(timing["mux_tx_interval"], (0, 106))
            self.assertEqual(timing["mux_rx_interval"], (106, 160))
            self.assertEqual(timing["sample_start"], 110)
            pulse = editor.pulse_preview.pulse_snapshot()
            self.assertEqual(pulse["count"], 4)
            self.assertEqual(pulse["period"], 1)
            self.assertEqual(pulse["high_time"], 0.5)
            self.assertEqual(pulse["duration"], 4)
            self.assertEqual(pulse["ticks"], (0, 1, 2, 3, 4))
            gain = editor.gain_profile.gain_snapshot()
            self.assertTrue(gain["fixed"])
            editor.inputs["vga_slope_code"].setValue(128)
            gain_without_precharge = editor.gain_profile.gain_snapshot()
            self.assertFalse(gain_without_precharge["fixed"])
            self.assertGreater(
                gain_without_precharge["gains"][-1],
                gain_without_precharge["gains"][0],
            )
            editor.inputs["vga_rc_prech_cyc"].setValue(100)
            gain = editor.gain_profile.gain_snapshot()
            self.assertGreater(
                gain["initial_gain"], gain_without_precharge["initial_gain"] + 5
            )
            self.assertLessEqual(max(gain["gains"]), gain["initial_gain"] + 80)
            configured = editor.config()
            self.assertLessEqual(max(gain["gains"]), configured.rx_gain + 80)
            configured.calc_gain_curve()
            self.assertLessEqual(
                configured.gain_curve_db.max(), configured.rx_gain + 80
            )
            cycle = editor.acquisition_cycle.cycle_snapshot()
            self.assertTrue(cycle["switch_enabled"])
            self.assertEqual(cycle["lead_time"], 50_000)
            self.assertEqual(cycle["acquisition_end"], 160)
            self.assertEqual(cycle["switch_disable"], 250_160)
            self.assertAlmostEqual(cycle["duty_cycle"], 20.064)
            editor.inputs["dcdc_turnon"].setValue(250_000)
            self.assertFalse(
                editor.acquisition_cycle.cycle_snapshot()["switch_enabled"]
            )
            self.assertEqual(editor.acquisition_cycle.cycle_snapshot()["duty_cycle"], 0)
        finally:
            window.close()
