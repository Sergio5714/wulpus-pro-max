"""Qt worker adapters; hardware code stays GUI-independent."""

from __future__ import annotations

import traceback
import time

from PySide6 import QtCore


class TaskSignals(QtCore.QObject):
    result = QtCore.Signal(object)
    error = QtCore.Signal(str)
    finished = QtCore.Signal()


class Task(QtCore.QRunnable):
    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.function, self.args, self.kwargs = function, args, kwargs
        self.signals = TaskSignals()

    @QtCore.Slot()
    def run(self):
        try:
            self.signals.result.emit(self.function(*self.args, **self.kwargs))
        except Exception:
            self.signals.error.emit(traceback.format_exc())
        finally:
            self.signals.finished.emit()


class AcquisitionWorker(QtCore.QObject):
    frame = QtCore.Signal(object, int, int, int, int)
    completed = QtCore.Signal(object)
    error = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, controller, config, display_mode="Off", display_fps=20):
        super().__init__()
        self.controller, self.config = controller, config
        self.display_mode = display_mode
        self.display_fps = display_fps
        self._stop = False

    @QtCore.Slot()
    def run(self):
        try:
            received = 0
            next_update = 0.0
            def publish(samples, number, config_id, gaps):
                nonlocal received, next_update
                received += 1
                now = time.monotonic()
                if now >= next_update or received >= self.config.num_acqs:
                    # Off mode deliberately does not copy RF samples through the
                    # Qt event queue. Only counters are published at 10 Hz.
                    displayed = None if self.display_mode == "Off" else samples
                    self.frame.emit(displayed, number, config_id, gaps, received)
                    rate = 10 if self.display_mode == "Off" else self.display_fps
                    next_update = now + 1.0 / max(1, rate)
            result = self.controller.acquire(
                self.config, lambda: self._stop, publish
            )
            self.completed.emit(result)
        except Exception:
            self.error.emit(traceback.format_exc())
        finally:
            self.finished.emit()

    @QtCore.Slot()
    def stop(self):
        self._stop = True

    def set_display(self, mode, fps):
        # The acquisition loop occupies the worker thread, so this deliberately
        # updates two atomic Python values instead of relying on a queued slot.
        self.display_mode = mode
        self.display_fps = fps
