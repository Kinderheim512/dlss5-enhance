"""Where the app lives: the project folder, or the folder holding the exe."""

from __future__ import annotations

import sys
from pathlib import Path


def tool_root() -> Path:
    """Project root, or the folder holding the exe when frozen."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


TOOL_ROOT = tool_root()

EXAMPLE_WORKFLOW = "workflows/exemple_dlss5_video.json"
DEFAULT_WORKFLOW = EXAMPLE_WORKFLOW
DEFAULT_CONFIG_NAME = "config.yaml"


def downloads_dir() -> Path:
    """The user's Downloads folder, wherever it is."""
    candidate = Path.home() / "Downloads"
    return candidate if candidate.is_dir() else Path.home()
