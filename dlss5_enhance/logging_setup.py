"""Console output: a transient progress line plus a timestamped log file."""

from __future__ import annotations

import contextlib
import logging
import sys
from datetime import datetime
from pathlib import Path

LOG_NAME = "dlss5-enhance"
FORMAT = "%(asctime)s %(levelname)-7s %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


class ProgressLine:
    """A single rewritten console line; inert when stdout is not a terminal."""

    def __init__(self, stream=None, enabled: bool | None = None) -> None:
        self.stream = stream or sys.stdout
        self.enabled = bool(self.stream.isatty()) if enabled is None else enabled
        self._length = 0

    @property
    def active(self) -> bool:
        return self._length > 0

    def update(self, text: str) -> None:
        if not self.enabled:
            return
        width = _terminal_width()
        body = text if len(text) <= width else text[: max(0, width - 1)] + "…"
        padding = max(0, self._length - len(body))
        try:
            self.stream.write("\r" + body + " " * padding)
            self.stream.flush()
        except (OSError, ValueError):
            self.enabled = False
            return
        self._length = len(body)

    def clear(self) -> None:
        if not self.enabled or not self._length:
            return
        try:
            self.stream.write("\r" + " " * self._length + "\r")
            self.stream.flush()
        except (OSError, ValueError):
            self.enabled = False
        finally:
            self._length = 0


def _terminal_width(default: int = 100) -> int:
    try:
        return max(40, __import__("shutil").get_terminal_size().columns - 1)
    except OSError:
        return default


class _ConsoleHandler(logging.StreamHandler):
    def __init__(self, progress: ProgressLine | None) -> None:
        super().__init__(stream=sys.stdout)
        self.progress = progress

    def emit(self, record: logging.LogRecord) -> None:
        if self.progress is not None:
            self.progress.clear()
        super().emit(record)


class _QueueLogHandler(logging.Handler):
    """Hands formatted records to a GUI queue instead of a stream."""

    def __init__(self, messages) -> None:
        super().__init__()
        self.messages = messages

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(Exception):
            self.messages.put(("log", (record.levelname, self.format(record))))


def setup_logging(
    log_dir: Path,
    level: str = "INFO",
    progress: ProgressLine | None = None,
    quiet: bool = False,
    queue: object | None = None,
) -> tuple[logging.Logger, Path]:
    """Configure the file handler plus either a console or a queue handler."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"dlss5-enhance-{datetime.now():%Y%m%d}.log"

    logger = logging.getLogger(LOG_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(FORMAT, datefmt=DATEFMT)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(getattr(logging, level, logging.INFO))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if queue is not None:
        queue_handler = _QueueLogHandler(queue)
        queue_handler.setLevel(getattr(logging, level, logging.INFO))
        queue_handler.setFormatter(formatter)
        logger.addHandler(queue_handler)
        return logger, log_path

    console_handler = _ConsoleHandler(progress)
    console_handler.setLevel(logging.ERROR if quiet else getattr(logging, level, logging.INFO))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger, log_path
