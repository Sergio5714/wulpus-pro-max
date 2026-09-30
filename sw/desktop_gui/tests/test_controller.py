import unittest

from desktop_gui.controller import SessionController, SimulatorLink
from desktop_gui.models import build_config


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.link = SimulatorLink()
        self.session = SessionController({"Simulator": self.link})

    def test_connection_and_acquisition(self):
        device = self.session.scan()[0]
        self.session.connect(device)
        config = build_config({"num_acqs": 4, "num_samples": 20})
        events = []
        result = self.session.acquire(config, lambda: False, lambda *args: events.append(args))
        self.assertTrue(result.completed)
        self.assertEqual(result.frames.shape, (4, 20))
        self.assertEqual(len(events), 4)
        self.assertIsNone(self.session.busy_operation)

    def test_transport_cannot_change_while_connected(self):
        self.session.connect("Simulator")
        with self.assertRaisesRegex(RuntimeError, "Disconnect"):
            self.session.select_transport("Simulator")

    def test_stop_returns_partial_result(self):
        self.session.connect("Simulator")
        config = build_config({"num_acqs": 10, "num_samples": 10})
        count = [0]
        def frame(*_): count[0] += 1
        result = self.session.acquire(config, lambda: count[0] >= 2, frame)
        self.assertFalse(result.completed)
        self.assertEqual(result.frames.shape[0], 2)


if __name__ == "__main__":
    unittest.main()
