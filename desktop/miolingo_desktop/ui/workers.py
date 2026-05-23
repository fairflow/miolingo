"""Qt worker plumbing to run blocking work off the UI thread.

Whisper transcription, TTS synthesis, and mic capture all block; running them on
the GUI thread would freeze the UI (the exact failure SPEC §7 forbids). These
``QRunnable`` workers run on a ``QThreadPool`` and report back via signals, so
the event loop stays responsive and the view shows progress.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    """Signals emitted by :class:`Worker` (a QObject so they're thread-safe)."""

    progress = Signal(str)
    finished = Signal(object)  # the function's return value
    error = Signal(str)


class Worker(QRunnable):
    """Run ``fn(*args, **kwargs)`` on a thread-pool thread.

    When ``pass_progress=True``, a ``progress_fn`` keyword is injected that emits
    the ``progress`` signal (so long-running work can report status). The return
    value is delivered via ``finished``; any exception via ``error``.
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        *args: Any,
        pass_progress: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.pass_progress = pass_progress
        self.signals = WorkerSignals()

    def run(self) -> None:  # noqa: D401 - Qt entry point
        try:
            if self.pass_progress:
                self.kwargs.setdefault("progress_fn", self.signals.progress.emit)
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:  # noqa: BLE001 - report any failure to the UI
            self.signals.error.emit(str(e))
            return
        self.signals.finished.emit(result)
