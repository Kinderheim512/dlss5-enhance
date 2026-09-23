"""Per-machine state that survives between runs (settings.json)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .app_paths import TOOL_ROOT

FILENAME = "settings.json"
APP_DIR_NAME = "dlss5-enhance"


@dataclass
class AppSettings:
    language: str | None = None
    comfy_root: str | None = None
    comfy_python: str | None = None
    comfy_port: int | None = None
    ffmpeg: str | None = None
    ffprobe: str | None = None
    output_dir: str | None = None
    image_output_dir: str | None = None
    workflow: str | None = None
    image_workflow: str | None = None
    preset: str | None = None
    source: str | None = None
    sources: list[str] = field(default_factory=list)
    image_sources: list[str] = field(default_factory=list)
    container: str | None = None
    codec: str | None = None
    settings: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            key: value
            for key, value in asdict(self).items()
            if value not in (None, [], {})
        }

    @classmethod
    def from_dict(cls, raw: object) -> AppSettings:
        if not isinstance(raw, dict):
            return cls()
        known = {item.name for item in fields(cls)}
        clean: dict[str, object] = {}
        for key, value in raw.items():
            if key not in known:
                continue
            if key == "comfy_port" and isinstance(value, (int, float, str)):
                clean[key] = int(value)
            elif key in ("sources", "image_sources") and isinstance(value, list):
                clean[key] = [str(item) for item in value]
            elif key == "settings" and isinstance(value, dict):
                clean[key] = {
                    str(name): item
                    for name, item in value.items()
                    if isinstance(item, (str, int, float, bool))
                }
            elif isinstance(value, (str, int, float)):
                clean[key] = str(value)
        return cls(**clean)


def _appdata_path() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home()
    return root / APP_DIR_NAME / FILENAME


def state_paths(app_root: Path | None = None) -> list[Path]:
    """Candidate files, most specific first."""
    root = Path(app_root) if app_root is not None else TOOL_ROOT
    return [root / FILENAME, _appdata_path()]


def load_settings(
    path: str | Path | None = None, app_root: Path | None = None
) -> tuple[AppSettings, Path | None]:
    """Read the state file; a missing or broken file simply yields defaults."""
    candidates = [Path(path)] if path else state_paths(app_root)
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppSettings(), candidate
        return AppSettings.from_dict(raw), candidate
    return AppSettings(), None


def save_settings(
    settings: AppSettings,
    path: str | Path | None = None,
    app_root: Path | None = None,
) -> Path | None:
    """Write the state next to the app, falling back to %APPDATA% when read-only."""
    candidates = [Path(path)] if path else state_paths(app_root)
    payload = json.dumps(settings.to_dict(), indent=2, ensure_ascii=False) + "\n"
    for candidate in candidates:
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(payload, encoding="utf-8")
        except OSError:
            continue
        return candidate
    return None


def store_path(value: str | Path | None, app_root: Path | None = None) -> str | None:
    """Relative when the path lives inside the app folder, absolute otherwise."""
    if value in (None, ""):
        return None
    path = Path(value)
    root = Path(app_root) if app_root is not None else TOOL_ROOT
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


def resolve_path(value: str | Path | None, app_root: Path | None = None) -> Path | None:
    """Inverse of store_path: a relative value is anchored on the app folder."""
    if value in (None, ""):
        return None
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    root = Path(app_root) if app_root is not None else TOOL_ROOT
    return root / path
