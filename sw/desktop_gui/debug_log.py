"""Low-overhead batched file logging for the desktop application."""

from __future__ import annotations

import logging
from pathlib import Path
import queue
import threading


class BatchedFileHandler(logging.Handler):
    """Queue records quickly and write them from one background thread."""

    def __init__(self, path: str | Path, interval: float = 1.0, capacity: int = 10_000):
        super().__init__(logging.DEBUG)
        self.path = Path(path)
        self.interval = interval
        self.records: queue.Queue[str | None] = queue.Queue(maxsize=capacity)
        self.dropped = 0
        self.error: Exception | None = None
        self.setFormatter(logging.Formatter(
            "%(asctime)s.%(msecs)03d\t%(levelname)s\t%(threadName)s\t%(name)s\t%(message)s",
            "%Y-%m-%d %H:%M:%S",
        ))
        self.writer = threading.Thread(target=self._write, name="debug-log-writer", daemon=True)
        self.writer.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.put_nowait(self.format(record) + "\n")
        except queue.Full:
            self.dropped += 1
        except Exception:
            self.handleError(record)

    def _write(self) -> None:
        try:
            with self.path.open("a", encoding="utf-8", buffering=64 * 1024) as output:
                stopping = False
                while not stopping:
                    try:
                        item = self.records.get(timeout=self.interval)
                    except queue.Empty:
                        item = ""
                    batch = []
                    if item is None:
                        stopping = True
                    elif item:
                        batch.append(item)
                    while len(batch) < 1000:
                        try:
                            item = self.records.get_nowait()
                        except queue.Empty:
                            break
                        if item is None:
                            stopping = True
                            break
                        batch.append(item)
                    if self.dropped:
                        batch.append(f"Debug log queue dropped {self.dropped} message(s)\n")
                        self.dropped = 0
                    if batch:
                        output.writelines(batch)
                    output.flush()
        except Exception as error:
            self.error = error

    def close(self) -> None:
        if self.writer.is_alive():
            try:
                self.records.put(None, timeout=1)
            except queue.Full:
                pass
            self.writer.join(timeout=3)
        super().close()
