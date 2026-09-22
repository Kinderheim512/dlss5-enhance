"""Turning the chosen file/folder into the ordered list of sources to process."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from .errors import UsageError
from .i18n import tr


def resolve_sources(
    *,
    input_path: str | None = None,
    folder: str | None = None,
    extensions: Iterable[str],
    recursive: bool = False,
    warn: Callable[[str], None] | None = None,
) -> tuple[list[Path], bool]:
    """Return (sources, folder_mode); exactly one of input_path/folder is required."""
    wanted = tuple(extensions)
    if bool(input_path) == bool(folder):
        raise UsageError(tr("s.one_source"))

    if input_path:
        source = Path(input_path).expanduser()
        if not source.is_file():
            raise UsageError(tr("s.file_missing", path=source))
        if source.suffix.lstrip(".").lower() not in wanted and warn is not None:
            warn(
                tr(
                    "s.extension_warning",
                    name=source.name,
                    extensions=", ".join(wanted),
                )
            )
        return [source], False

    directory = Path(str(folder)).expanduser()
    if not directory.is_dir():
        raise UsageError(tr("s.folder_missing", path=directory))
    walker = directory.rglob("*") if recursive else directory.glob("*")
    sources = sorted(
        path
        for path in walker
        if path.is_file() and path.suffix.lstrip(".").lower() in wanted
    )
    if not sources:
        suffix = tr("s.recursive_suffix") if recursive else ""
        raise UsageError(
            tr(
                "s.no_files",
                extensions=", ".join(wanted),
                folder=directory,
                recursive=suffix,
            )
        )
    return sources, True


def resolve_many(
    paths: Iterable[str | Path],
    extensions: Iterable[str],
    recursive: bool = False,
) -> tuple[list[Path], list[str]]:
    """Expand a mixed list of files and folders into ordered, unique sources.

    Returns (sources, problems): a problem is a human-readable line for an entry
    that could not contribute anything (missing path, folder with no video).
    """
    wanted = tuple(extensions)
    sources: list[Path] = []
    problems: list[str] = []
    seen: set[str] = set()

    for raw in paths:
        entry = Path(str(raw)).expanduser()
        if entry.is_dir():
            walker = entry.rglob("*") if recursive else entry.glob("*")
            found = sorted(
                path
                for path in walker
                if path.is_file() and path.suffix.lstrip(".").lower() in wanted
            )
            if not found:
                problems.append(
                    tr(
                        "s.no_files",
                        extensions=", ".join(wanted),
                        folder=entry,
                        recursive=tr("s.recursive_suffix") if recursive else "",
                    )
                )
                continue
            for path in found:
                _add(path, sources, seen)
            continue
        if not entry.is_file():
            problems.append(tr("s.file_missing", path=entry))
            continue
        _add(entry, sources, seen)
    return sources, problems


def _add(path: Path, sources: list[Path], seen: set[str]) -> None:
    key = str(path.resolve()).lower()
    if key in seen:
        return
    seen.add(key)
    sources.append(path)
