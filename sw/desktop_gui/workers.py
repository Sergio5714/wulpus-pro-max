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


Qt worker adapters; hardware code stays GUI-independent.
"""

from __future__ import annotations

import time
import traceback

from PySide6 import QtCore


class TaskSignals(QtCore.QObject):
    """Deliver a result or traceback, followed by completion, for a pool task."""

    result = QtCore.Signal(object)
    error = QtCore.Signal(str)
    finished = QtCore.Signal()


class Task(QtCore.QRunnable):
    """Execute one blocking callable without giving it access to Qt widgets."""

    def __init__(self, function, *args, **kwargs):
        """Store a blocking callable and arguments for thread-pool execution."""
        super().__init__()
        self.function, self.args, self.kwargs = function, args, kwargs
        self.signals = TaskSignals()

    @QtCore.Slot()
    def run(self):
        """Emit result/error and always signal completion to release UI state."""
        try:
            self.signals.result.emit(self.function(*self.args, **self.kwargs))
        except Exception:
            self.signals.error.emit(traceback.format_exc())
        finally:
            self.signals.finished.emit()


class AcquisitionWorker(QtCore.QObject):
    """Receive every frame while limiting expensive GUI updates to a set rate.

    Move this object to a dedicated QThread before calling run. The controller
    owns capture/storage; dropped display updates do not drop recorded frames.
    """

    frame = QtCore.Signal(object, int, int, int, int)
    completed = QtCore.Signal(object)
    error = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, controller, config, display_mode="Off", display_fps=20):
        """Initialize continuous acquisition with throttled display updates."""
        super().__init__()
        self.controller, self.config = controller, config
        self.display_mode = display_mode
        self.display_fps = display_fps
        self._stop = False

    @QtCore.Slot()
    def run(self):
        """Capture until completion or cooperative cancellation, then signal exit."""
        try:
            received = 0
            next_update = 0.0

            def publish(samples, number, config_id, gaps):
                """Emit a rate-limited sample update and track received frames."""
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

            result = self.controller.acquire(self.config, lambda: self._stop, publish)
            self.completed.emit(result)
        except Exception:
            self.error.emit(traceback.format_exc())
        finally:
            self.finished.emit()

    @QtCore.Slot()
    def stop(self):
        """Request cancellation; the current blocking transport read finishes first."""
        self._stop = True

    def set_display(self, mode, fps):
        """Update rendering preferences without queueing behind the receive loop."""
        # The acquisition loop occupies the worker thread, so this deliberately
        # updates two atomic Python values instead of relying on a queued slot.
        self.display_mode = mode
        self.display_fps = fps
