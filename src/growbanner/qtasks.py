"""Run a function on a background thread and report back on the UI thread."""
from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QObject, Signal

from .drive import friendly_error


class Task(QObject):
    """``done`` carries the result, ``failed`` a user-readable message. Connect both to methods
    of a QObject that lives on the UI thread so they are delivered there."""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], object]):
        super().__init__()
        self._fn = fn

    def start(self) -> "Task":
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def _run(self):
        try:
            result = self._fn()
        except Exception as e:
            self.failed.emit(friendly_error(e))
        else:
            self.done.emit(result)
