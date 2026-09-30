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


Async UI components for the desktop application.
"""

from __future__ import annotations

import logging

from PySide6 import QtCore, QtWidgets

from .workers import Task

logger = logging.getLogger(__name__)


def _error_text(traceback_text: str) -> str:
    """Return the final traceback line for compact user-facing error dialogs."""
    lines = traceback_text.strip().splitlines()
    return lines[-1] if lines else traceback_text


class AsyncMixin:
    """Run short blocking operations while retaining their Qt signal owners.

    Hosts must be QWidget instances and supply a QThreadPool. Call run_task
    from the GUI thread; result callbacks may update widgets.
    """

    pool: QtCore.QThreadPool

    def run_task(self, function, done=None, *, busy=None):
        """Submit a callable, optionally apply its result, and surface failures.

        ``busy`` accepts an enabled flag (False before execution, True after).
        Return the task so callers can connect additional lifecycle handlers.
        """
        task = Task(function)
        # Keep the Python worker and its signal object alive until queued GUI
        # callbacks have been delivered. QThreadPool retains only the C++
        # QRunnable; without this reference fast tasks can lose their result.
        if not hasattr(self, "_active_tasks"):
            self._active_tasks = set()
        self._active_tasks.add(task)
        if done:
            task.signals.result.connect(done)

        def show_error(text):
            """Log a worker failure and present its traceback to the user."""
            logger.error("Background operation failed\n%s", text.rstrip())
            QtWidgets.QMessageBox.critical(self, "Operation failed", _error_text(text))

        task.signals.error.connect(show_error)
        if busy:
            busy(False)
            task.signals.finished.connect(lambda: busy(True))
        task.signals.finished.connect(
            lambda worker=task: self._active_tasks.discard(worker)
        )
        self.pool.start(task)
        return task
