"""Output sinks: the CLI writes to the console, the GUI posts to a queue."""

from __future__ import annotations

import queue
from typing import Any

from .logging_setup import ProgressLine

LINE = "line"
PROGRESS = "progress"
CLEAR = "clear"
LOG = "log"
DONE = "done"
STATUS = "status"


class Sink:
    """Where a run's human-readable output goes."""

    interactive: bool = False

    def line(self, text: str = "") -> None:
        raise NotImplementedError

    def progress(self, text: str) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError


class ConsoleSink(Sink):
    def __init__(self, progress: ProgressLine, stream: Any = None) -> None:
        self.progress_line = progress
        self.stream = stream

    @property
    def interactive(self) -> bool:
        return self.progress_line.enabled

    def line(self, text: str = "") -> None:
        self.progress_line.clear()
        print(text, file=self.stream)

    def progress(self, text: str) -> None:
        self.progress_line.update(text)

    def clear(self) -> None:
        self.progress_line.clear()


class QueueSink(Sink):
    """Posts messages a GUI thread can drain; never touches a widget."""

    interactive = True

    def __init__(self, messages: queue.Queue) -> None:
        self.messages = messages

    def line(self, text: str = "") -> None:
        self.messages.put((LINE, text))

    def progress(self, text: str) -> None:
        self.messages.put((PROGRESS, text))

    def clear(self) -> None:
        self.messages.put((CLEAR, None))

    def status(self, text: str) -> None:
        self.messages.put((STATUS, text))

    def finished(self, code: int) -> None:
        self.messages.put((DONE, code))


class CollectSink(Sink):
    """Keeps the output in memory; used by tests."""

    interactive = False

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.progress_text = ""
        self.cleared = 0

    def line(self, text: str = "") -> None:
        self.lines.append(text)

    def progress(self, text: str) -> None:
        self.progress_text = text

    def clear(self) -> None:
        self.cleared += 1
