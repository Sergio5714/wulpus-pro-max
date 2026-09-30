import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from desktop_gui.models import (
    AcquisitionResult, build_config, config_values, decoded_errors, frame_gap,
    load_config, save_config, save_npz,
)


class ModelTests(unittest.TestCase):
    def test_config_json_round_trip_includes_masks(self):
        config = build_config({
            "num_txrx_configs": 2,
            "tx_configs": [1, 2],
            "rx_configs": [4, 8],
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            save_config(path, config)
            loaded = load_config(path)
        self.assertEqual(config_values(loaded)["tx_configs"], [1, 2])
        self.assertEqual(config_values(loaded)["rx_configs"], [4, 8])

    def test_bad_mask_lengths_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "lengths"):
            build_config({"num_txrx_configs": 2, "tx_configs": [1], "rx_configs": [1]})

    def test_wrapping_frame_gap(self):
        self.assertEqual(frame_gap(65535, 1), 1)
        self.assertEqual(frame_gap(9, 10), 0)
        self.assertEqual(frame_gap(None, 10), 0)

    def test_error_decode_keeps_unknown_bits(self):
        self.assertIn("SPI timeout", decoded_errors(1 << 2))
        self.assertTrue(any("Unknown" in item for item in decoded_errors(1 << 12)))

    def test_npz_layout_matches_notebook(self):
        result = AcquisitionResult(
            frames=np.arange(12, dtype=np.int16).reshape(3, 4),
            acquisition_numbers=np.array([10, 11, 12]),
            tx_rx_ids=np.array([0, 1, 0]), frame_gaps=0, completed=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.npz"
            save_npz(path, result)
            with np.load(path) as saved:
                self.assertEqual(saved["data_arr"].shape, (4, 3))
                self.assertEqual(saved["acq_num_arr"].tolist(), [10, 11, 12])


if __name__ == "__main__":
    unittest.main()
