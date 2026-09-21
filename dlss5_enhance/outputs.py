"""Watch the output directory to tell a fresh render from a cached one."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

UNSAFE_PREFIX = set('<>:"/\\|?*')

OUTPUT_EXTENSIONS = ("mp4", "mkv", "mov")


def sanitize_prefix(stem: str) -> str:
    """Make a source file stem safe for the node's filename_prefix widget."""
    cleaned = "".join(
        "_" if (char in UNSAFE_PREFIX or ord(char) < 32) else char for char in stem
    ).strip()
    cleaned = cleaned.strip(". ")
    if not cleaned or cleaned.startswith("-"):
        cleaned = f"DLSS5_{cleaned}" if cleaned else "DLSS5"
    return cleaned


def _matches(path: Path, prefix: str, extensions: Iterable[str]) -> bool:
    if not path.name.startswith(f"{prefix}_"):
        return False
    suffix = path.suffix.lstrip(".").lower()
    return suffix in {ext.lstrip(".").lower() for ext in extensions}


def snapshot_outputs(
    directory: Path | None,
    prefix: str,
    extensions: Iterable[str],
) -> dict[str, float]:
    """Map normcased absolute path -> mtime for the files the job could overwrite.

    Callers pass `OUTPUT_EXTENSIONS`: the output container comes from --container,
    not from the source extension list.
    """
    if directory is None or not Path(directory).is_dir():
        return {}
    snapshot: dict[str, float] = {}
    for entry in Path(directory).iterdir():
        if not entry.is_file() or not _matches(entry, prefix, extensions):
            continue
        try:
            snapshot[os.path.normcase(str(entry.resolve()))] = entry.stat().st_mtime
        except OSError:
            continue
    return snapshot


@dataclass(frozen=True)
class OutputProbe:
    path: Path | None = None
    is_new: bool = False
    mtime: float | None = None
    size: int = 0

    @property
    def usable(self) -> bool:
        return self.path is not None and self.size > 0


def probe_output(
    snapshot: Mapping[str, float],
    directory: Path | None,
    prefix: str,
    extensions: Iterable[str],
) -> OutputProbe:
    """Find the job's output: a file that changed since the snapshot, else the newest."""
    if directory is None or not Path(directory).is_dir():
        return OutputProbe()
    candidates: list[tuple[Path, float, int, bool]] = []
    for entry in Path(directory).iterdir():
        if not entry.is_file() or not _matches(entry, prefix, extensions):
            continue
        try:
            stat = entry.stat()
        except OSError:
            continue
        key = os.path.normcase(str(entry.resolve()))
        changed = snapshot.get(key) != stat.st_mtime
        candidates.append((entry, stat.st_mtime, stat.st_size, changed))
    if not candidates:
        return OutputProbe()

    fresh = [item for item in candidates if item[3]]
    pool = fresh or candidates
    path, mtime, size, _ = max(pool, key=lambda item: item[1])
    return OutputProbe(path=path, is_new=bool(fresh), mtime=mtime, size=size)


def classify(
    probe: OutputProbe,
    cached_node_ids: Iterable[str],
    target_node_id: str | None,
) -> str:
    """Return 'new', 'cache' or 'missing'.

    The filesystem is the ground truth: a file that appeared (or changed) since
    the pre-submit snapshot means a real render. The WebSocket `execution_cached`
    signal only corroborates a job that wrote nothing.
    """
    if probe.path is None:
        return "missing"
    if probe.is_new:
        return "new"
    if target_node_id is not None and str(target_node_id) in {str(n) for n in cached_node_ids}:
        return "cache"
    return "cache"
