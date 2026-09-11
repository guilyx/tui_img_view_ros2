"""Route Python ``logging`` into the UI without touching Textual from other threads.

Transports log from their own threads. A :class:`LogBuffer` handler just
queues formatted lines; the app drains the queue on its own tick.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque


class LogBuffer(logging.Handler):
    def __init__(self, maxlen: int = 2000) -> None:
        super().__init__()
        self._lines: deque[tuple[float, int, str]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001 - never raise from a log handler
            msg = str(record.msg)
        with self._lock:
            self._lines.append((record.created, record.levelno, msg))

    def push(self, message: str, level: int = logging.INFO) -> None:
        """Add a line directly (for UI-originated events)."""
        with self._lock:
            self._lines.append((time.time(), level, message))

    def drain(self) -> list[tuple[float, int, str]]:
        with self._lock:
            lines = list(self._lines)
            self._lines.clear()
        return lines


def attach(buffer: LogBuffer, logger_name: str = "tui_img_view", level: int = logging.INFO) -> None:
    logger = logging.getLogger(logger_name)
    if buffer not in logger.handlers:
        logger.addHandler(buffer)
    if logger.level == logging.NOTSET or logger.level > level:
        logger.setLevel(level)
