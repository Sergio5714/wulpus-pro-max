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


Tests for session control and simulated acquisition.
"""

import unittest

from desktop_gui.controller import SessionController, SimulatorLink
from desktop_gui.models import build_config


class ControllerTests(unittest.TestCase):
    def setUp(self):
        """Create a fresh simulator-backed session for each test."""
        self.link = SimulatorLink()
        self.session = SessionController({"Simulator": self.link})

    def test_connection_and_acquisition(self):
        """Exercise simulator connection, acquisition, and disconnection."""
        device = self.session.scan()[0]
        self.session.connect(device)
        config = build_config({"num_acqs": 4, "num_samples": 20})
        events = []
        result = self.session.acquire(
            config, lambda: False, lambda *args: events.append(args)
        )
        self.assertTrue(result.completed)
        self.assertEqual(result.frames.shape, (4, 20))
        self.assertEqual(len(events), 4)
        self.assertIsNone(self.session.busy_operation)

    def test_transport_cannot_change_while_connected(self):
        """Verify an active session prevents transport replacement."""
        self.session.connect("Simulator")
        with self.assertRaisesRegex(RuntimeError, "Disconnect"):
            self.session.select_transport("Simulator")

    def test_stop_returns_partial_result(self):
        """Verify stopping acquisition preserves already received frames."""
        self.session.connect("Simulator")
        config = build_config({"num_acqs": 10, "num_samples": 10})
        count = [0]

        def frame(*_):
            """Count frames so the stop callback can terminate acquisition."""
            count[0] += 1

        result = self.session.acquire(config, lambda: count[0] >= 2, frame)
        self.assertFalse(result.completed)
        self.assertEqual(result.frames.shape[0], 2)


if __name__ == "__main__":
    unittest.main()
