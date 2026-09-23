"""User presets, kept in `presets.yaml` next to the configuration.

The GUI writes them there so `config.yaml` keeps its comments; they are merged
over the built-in presets, and a user preset with the same name wins.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

FILENAME = "presets.yaml"
KIND_LABEL = "user"


def presets_path(config_dir: Path | None = None) -> Path:
    from .app_paths import TOOL_ROOT

    return (Path(config_dir) if config_dir is not None else TOOL_ROOT) / FILENAME


def load_user_presets(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """The raw preset bodies from presets.yaml; a broken file yields {}."""
    target = Path(path) if path is not None else presets_path()
    if not target.is_file():
        return {}
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(raw, Mapping):
        return {}
    presets = raw.get("presets") if "presets" in raw else raw
    if not isinstance(presets, Mapping):
        return {}
    return {
        str(name): dict(body)
        for name, body in presets.items()
        if isinstance(body, Mapping)
    }


def _write(path: Path, presets: Mapping[str, Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"presets": {name: dict(body) for name, body in presets.items()}}
    path.write_text(
        "# Presets saved from the interface. Move a block into config.yaml to share it.\n"
        + yaml.safe_dump(payload, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )


def save_user_preset(
    name: str, body: Mapping[str, Any], path: str | Path | None = None
) -> Path:
    """Add or replace one user preset; returns the file written."""
    target = Path(path) if path is not None else presets_path()
    presets = load_user_presets(target)
    presets[str(name).strip()] = dict(body)
    _write(target, presets)
    return target


def delete_user_preset(name: str, path: str | Path | None = None) -> bool:
    """Remove one user preset; True when it existed."""
    target = Path(path) if path is not None else presets_path()
    presets = load_user_presets(target)
    if str(name) not in presets:
        return False
    del presets[str(name)]
    _write(target, presets)
    return True


def is_user_preset(name: str, path: str | Path | None = None) -> bool:
    return str(name) in load_user_presets(path)
