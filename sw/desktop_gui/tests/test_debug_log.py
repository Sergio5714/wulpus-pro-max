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


Regression coverage for batching, overflow, and shutdown drainage.
"""

import logging
import tempfile
import unittest
from pathlib import Path

from desktop_gui.debug_log import BatchedFileHandler


class DebugLogTests(unittest.TestCase):
    def test_shutdown_flushes_and_reports_overflow(self):
        """Verify shutdown drains records and reports a bounded-queue overflow."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "debug.log"
            handler = BatchedFileHandler(path, interval=60, capacity=2)
            for index in range(3):
                handler.handle(
                    logging.LogRecord(
                        "test", logging.DEBUG, "", 0, "message %s", (index,), None
                    )
                )
            self.assertEqual(path.read_text(), "")
            handler.close()
            self.assertFalse(handler.writer.is_alive())
            text = path.read_text()
            self.assertIn("message 0", text)
            self.assertIn("message 1", text)
            self.assertIn("dropped 1", text)
            handler.close()

    def test_invalid_destination_fails_at_enable_time(self):
        """Verify an unusable log destination fails during handler creation."""
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(OSError):
                BatchedFileHandler(Path(directory) / "missing" / "debug.log")
