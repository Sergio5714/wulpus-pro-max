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


Low-overhead batched file logging for the desktop application.
"""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path


class BatchedFileHandler(logging.Handler):
    """Queue records quickly and write them from one background thread."""

    def __init__(self, path: str | Path, interval: float = 1.0, capacity: int = 10_000):
        """Open the log destination and start the bounded background writer."""
        if interval <= 0 or capacity <= 0:
            raise ValueError("Logging interval and capacity must be positive")
        super().__init__(logging.DEBUG)
        self.path = Path(path)
        self.interval = interval
        self.records: queue.Queue[str | None] = queue.Queue(maxsize=capacity)
        self.dropped = 0
        self.error: Exception | None = None
        self._stop = threading.Event()
        # Fail immediately on an invalid destination, before enabling the UI.
        self._stream = self.path.open("a", encoding="utf-8", buffering=64 * 1024)
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s.%(msecs)03d\t%(levelname)s\t%(threadName)s\t%(name)s\t%(message)s",
                "%Y-%m-%d %H:%M:%S",
            )
        )
        self.writer = threading.Thread(
            target=self._write, name="debug-log-writer", daemon=True
        )
        self.writer.start()

    def emit(self, record: logging.LogRecord) -> None:
        """Enqueue a formatted record without waiting for disk or queue capacity."""
        if self._stop.is_set() or self.error is not None:
            return
        try:
            self.records.put_nowait(self.format(record) + "\n")
        except queue.Full:
            self.dropped += 1
        except Exception:
            self.handleError(record)

    def _write(self) -> None:
        """Drain queued records in batches until shutdown is requested."""
        try:
            with self._stream as output:
                while True:
                    # A timer forms real batches even with sparse messages.
                    stopping = self._stop.wait(self.interval)
                    batch = []
                    for _ in range(self.records.maxsize):
                        try:
                            item = self.records.get_nowait()
                        except queue.Empty:
                            break
                        batch.append(item)
                    with self.lock:
                        dropped, self.dropped = self.dropped, 0
                    if dropped:
                        batch.append(f"Debug log queue dropped {dropped} message(s)\n")
                    if batch:
                        output.writelines(batch)
                        output.flush()
                    if stopping and self.records.empty():
                        break
        except Exception as error:
            self.error = error

    def close(self) -> None:
        """Stop accepting records and allow up to three seconds for final drainage."""
        with self.lock:
            self._stop.set()
        if hasattr(self, "writer") and self.writer.is_alive():
            self.writer.join(timeout=3)
        super().close()
