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
EXAMPLE_IMAGE_WORKFLOW = "workflows/exemple_dlss5_image.json"
DEFAULT_IMAGE_WORKFLOW = EXAMPLE_IMAGE_WORKFLOW
DEFAULT_CONFIG_NAME = "config.yaml"


ICON_NAME = "dlss5-enhance.ico"


def icon_path() -> Path | None:
    """The window/exe icon: next to the app, or inside the frozen bundle."""
    candidates = [TOOL_ROOT / ICON_NAME]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidates.append(Path(bundle) / ICON_NAME)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def downloads_dir() -> Path:
    """The user's Downloads folder, wherever it is."""
    candidate = Path.home() / "Downloads"
    return candidate if candidate.is_dir() else Path.home()
