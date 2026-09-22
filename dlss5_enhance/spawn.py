"""Spawning child processes without ever flashing a console window."""

from __future__ import annotations

import subprocess
from typing import Any

CREATE_NO_WINDOW = 0x08000000
STARTF_USESHOWWINDOW = 0x00000001
SW_HIDE = 0


def hidden_kwargs() -> dict[str, Any]:
    """Windows flags that keep a child process invisible.

    `CREATE_NO_WINDOW` hides the console of a console-subsystem child, and the
    `STARTUPINFO` covers the children that create their own window.
    """
    if not hasattr(subprocess, "STARTUPINFO"):
        return {"creationflags": CREATE_NO_WINDOW}
    info = subprocess.STARTUPINFO()
    info.dwFlags |= STARTF_USESHOWWINDOW
    info.wShowWindow = SW_HIDE
    return {"creationflags": CREATE_NO_WINDOW, "startupinfo": info}


def run_hidden(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """`subprocess.run` with the window hidden and text output captured."""
    options: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    options.update(hidden_kwargs())
    options.update(kwargs)
    return subprocess.run(command, **options)


def popen_hidden(command: list[str], **kwargs: Any) -> subprocess.Popen:
    """`subprocess.Popen` with the window hidden."""
    options: dict[str, Any] = dict(hidden_kwargs())
    options.update(kwargs)
    return subprocess.Popen(command, **options)
