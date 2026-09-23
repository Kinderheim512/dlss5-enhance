"""Images in and out through ComfyUI's own API.

The image node takes an `IMAGE` batch, so the workflow starts with a `LoadImage`,
which only accepts a name **inside ComfyUI's input folder**, and the save node
writes **inside ComfyUI's output folder**. Neither folder is published by the API
(``/internal/folder_paths`` only lists model folders), so nothing here touches the
filesystem on the server side: the source is uploaded with ``POST /upload/image``
and the results come back through ``GET /view``. That works whatever the install
layout - portable, flat, or ComfyUI Desktop with its shared folders.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from .errors import ComfyError
from .outputs import sanitize_prefix

UPLOAD_SUBFOLDER = "dlss5-enhance"
RESULT_SUBFOLDER = ""


class UploadClient(Protocol):
    def upload_image(self, path: Path, subfolder: str = "", type_: str = "input") -> str: ...

    def output_files(self, subfolder: str = "") -> list[str]: ...

    def view(self, filename: str, subfolder: str = "", type_: str = "output") -> bytes: ...


def upload_source(client: UploadClient, source: Path) -> str:
    """Upload the image; return the value `LoadImage` expects."""
    try:
        return client.upload_image(Path(source), subfolder=UPLOAD_SUBFOLDER, type_="input")
    except ComfyError:
        raise


def result_prefix(stem: str, token: str) -> str:
    """The `filename_prefix` of this job: unique, so the results are unambiguous."""
    return f"{sanitize_prefix(stem)}_{token}"


def _matches(name: str, prefix: str, extensions: Iterable[str]) -> bool:
    if not name.startswith(f"{prefix}_"):
        return False
    wanted = tuple(extensions)
    if not wanted:
        return True
    suffix = Path(name).suffix.lstrip(".").lower()
    return suffix in {ext.lstrip(".").lower() for ext in wanted}


def fetch_results(
    client: UploadClient,
    prefix: str,
    target_dir: Path,
    stem: str,
    extensions: Iterable[str] = (),
    subfolder: str = RESULT_SUBFOLDER,
    timeout: float = 20.0,
) -> list[Path]:
    """Download every file this job produced into *target_dir*.

    ComfyUI writes the file before the history entry closes, but the listing can
    lag by a moment, so a short retry loop is used.
    """
    deadline = time.monotonic() + timeout
    names: list[str] = []
    while True:
        names = [
            name for name in client.output_files(subfolder) if _matches(name, prefix, extensions)
        ]
        if names or time.monotonic() >= deadline:
            break
        time.sleep(0.5)
    if not names:
        return []

    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    written: list[Path] = []
    for index, name in enumerate(sorted(names)):
        payload = client.view(name, subfolder=subfolder, type_="output")
        if not payload:
            continue
        suffix = Path(name).suffix.lower() or ".png"
        extra = "" if index == 0 else f"_{index:03d}"
        destination = target / f"{sanitize_prefix(stem)}_{stamp}{extra}{suffix}"
        counter = 1
        while destination.exists():
            destination = target / f"{sanitize_prefix(stem)}_{stamp}{extra}_{counter:03d}{suffix}"
            counter += 1
        destination.write_bytes(payload)
        written.append(destination)
    return written


def newest_local(target_dir: Path, stem: str) -> Path | None:
    """Newest collected result for that source (a cache hit produces no new one)."""
    directory = Path(target_dir)
    if not directory.is_dir():
        return None
    candidates = sorted(
        (path for path in directory.glob(f"{sanitize_prefix(stem)}_*") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
    )
    return candidates[-1] if candidates else None
