"""Frozen entry point: no argument means GUI, so hide the console first."""

from __future__ import annotations

import sys


def _hide_console() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetConsoleWindow()
        if handle:
            ctypes.windll.user32.ShowWindow(handle, 0)
    except Exception:
        pass


def main() -> int:
    arguments = sys.argv[1:]
    if not arguments:
        _hide_console()
    from dlss5_enhance.__main__ import main as run

    return run(arguments)


if __name__ == "__main__":
    sys.exit(main())
