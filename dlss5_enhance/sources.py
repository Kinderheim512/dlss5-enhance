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
