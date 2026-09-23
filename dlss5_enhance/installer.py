"""Downloads and installs what the tool needs, on demand."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Iterable
from pathlib import Path

from .i18n import tr
from .spawn import run_hidden

COMFY_RELEASES_API = "https://api.github.com/repos/Comfy-Org/ComfyUI/releases/latest"
COMFY_ASSET = "ComfyUI_windows_portable_nvidia.7z"
NODE_ZIP = "https://github.com/Blueforcer/ComfyUI-DLSS5-Enhancer/archive/refs/heads/main.zip"
NODE_DIR_NAME = "ComfyUI-DLSS5-Enhancer"
NODE_REQUIREMENTS = ("numpy", "av")
SEVEN_ZIP_URL = "https://www.7-zip.org/a/7zr.exe"
SEVEN_ZIP_NAME = "7zr.exe"
RUNTIME_SCRIPT = "install_runtime.py"
RUNTIME_FILES = (
    "nvngx.dll",
    "dxgi.dll",
    "renodx-dlss5.addon64",
    "nvngx_dlss.dll",
    "nvngx_dlssnr.dll",
)

CHUNK = 1024 * 1024

ProgressFn = Callable[[str, int, int], None]


class InstallError(RuntimeError):
    """A download or an install step failed."""


def _progress(progress: ProgressFn | None, label: str, done: int, total: int) -> None:
    if progress is not None:
        progress(label, done, total)


def _fetch_json(url: str, timeout: float = 30.0) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "dlss5-enhance"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise InstallError(f"{url}: {exc}") from exc


def latest_comfyui_archive() -> tuple[str, str | None]:
    """Newest Windows portable NVIDIA archive, with the digest GitHub publishes."""
    release = _fetch_json(COMFY_RELEASES_API)
    for asset in release.get("assets") or []:
        if asset.get("name") != COMFY_ASSET:
            continue
        digest = str(asset.get("digest") or "")
        sha256 = digest.split("sha256:", 1)[1] if digest.startswith("sha256:") else None
        return str(asset.get("browser_download_url")), sha256
    raise InstallError(f"asset {COMFY_ASSET} not found in the latest ComfyUI release")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def download(
    url: str,
    dest: Path,
    *,
    sha256: str | None = None,
    progress: ProgressFn | None = None,
    label: str = "",
) -> Path:
    """Download to <dest>.part, verify the digest, then rename into place."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    if dest.is_file() and (sha256 is None or sha256_of(dest) == sha256):
        return dest
    request = urllib.request.Request(url, headers={"User-Agent": "dlss5-enhance"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or 0)
            received = 0
            with part.open("wb") as sink:
                while True:
                    block = response.read(CHUNK)
                    if not block:
                        break
                    sink.write(block)
                    received += len(block)
                    _progress(progress, label or url, received, total)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise InstallError(f"{url}: {exc}") from exc
    if sha256 is not None:
        actual = sha256_of(part)
        if actual != sha256:
            part.unlink(missing_ok=True)
            raise InstallError(f"checksum mismatch for {url} (got {actual})")
    part.replace(dest)
    return dest


def ensure_7zr(app_dir: Path, progress: ProgressFn | None = None) -> Path:
    """The official standalone 7-Zip extractor, downloaded on demand."""
    target = Path(app_dir) / "tools" / SEVEN_ZIP_NAME
    if target.is_file():
        return target
    return download(SEVEN_ZIP_URL, target, progress=progress, label=SEVEN_ZIP_NAME)


def extract_7z(archive: Path, dest: Path, seven_zip: Path) -> None:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    result = run_hidden([str(seven_zip), "x", str(archive), f"-o{dest}", "-y"])
    if result.returncode != 0:
        tail = (result.stdout or result.stderr or "").strip().splitlines()
        raise InstallError(tail[-1] if tail else "7zr failed")


def extract_zip(archive: Path, dest: Path) -> None:
    """Extract a GitHub zipball, dropping its top-level folder."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            parts = Path(member.filename).parts[1:]
            if not parts:
                continue
            target = dest.joinpath(*parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)


def find_comfy_root(base: Path) -> Path | None:
    """The folder holding ComfyUI and its interpreter, under *base*."""
    base = Path(base)
    candidates = [base, *(path for path in base.glob("*") if path.is_dir())]
    for candidate in candidates:
        if (candidate / "ComfyUI" / "main.py").is_file() or (
            candidate / "python_embeded" / "python.exe"
        ).is_file():
            return candidate
        if (candidate / "main.py").is_file() and (candidate / "comfy").is_dir():
            return candidate.parent
    return None


def _looks_like_comfy(path: Path) -> bool:
    """True when that folder holds a ComfyUI server."""
    return (Path(path) / "ComfyUI" / "main.py").is_file() or (
        (Path(path) / "main.py").is_file() and (Path(path) / "comfy").is_dir()
    )


def _desktop_log_roots() -> list[Path]:
    """ComfyUI Desktop logs its own command line: that names the install."""
    import os
    import re

    appdata = os.environ.get("APPDATA")
    if not appdata:
        return []
    log_dir = Path(appdata) / "Comfy Desktop" / "logs"
    if not log_dir.is_dir():
        return []
    pattern = re.compile(r">\s*(\S*python\.exe)\s+-s\s+ComfyUI[\\/]main\.py")
    found: list[Path] = []
    logs = sorted(log_dir.glob("app.log*"), key=lambda item: item.stat().st_mtime, reverse=True)
    for log in logs[:5]:
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        match = pattern.search(text)
        if match is None:
            continue
        # the outermost valid folder is the one the rest of the tool expects
        valid = [parent for parent in Path(match.group(1)).parents if _looks_like_comfy(parent)]
        if valid:
            found.append(valid[-1])
    return found


def _desktop_config_roots() -> list[Path]:
    """`config.json` of ComfyUI Desktop carries its basePath."""
    import json
    import os

    appdata = os.environ.get("APPDATA")
    if not appdata:
        return []
    found: list[Path] = []
    for name in ("ComfyUI", "Comfy Desktop", "ComfyUI-Desktop"):
        config = Path(appdata) / name / "config.json"
        if not config.is_file():
            continue
        try:
            payload = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        base = payload.get("basePath") if isinstance(payload, dict) else None
        if base and _looks_like_comfy(Path(base)):
            found.append(Path(base))
    return found


def looks_like_comfy(path: str | Path) -> bool:
    """Public test: does that folder hold a ComfyUI server?"""
    return _looks_like_comfy(Path(path))


def candidate_comfy_roots() -> list[Path]:
    """Every plausible ComfyUI install on this machine, best guess first."""
    import os

    from .app_paths import TOOL_ROOT

    roots: list[Path] = []
    roots.extend(_desktop_log_roots())
    roots.extend(_desktop_config_roots())
    home = Path.home()
    roots.append(TOOL_ROOT / "comfyui")
    roots.append(home / "comfy" / "ComfyUI")
    roots.append(home / "ComfyUI")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(
            Path(local) / "Programs" / "@comfyorgcomfyui-electron" / "resources" / "ComfyUI"
        )
    roots.append(TOOL_ROOT)
    seen: list[Path] = []
    for root in roots:
        if root not in seen:
            seen.append(root)
    return seen


def find_installed_comfyui() -> Path | None:
    """The best ComfyUI install found on disk, preferring one with the node."""
    from .config import derive_python

    usable: list[Path] = []
    for root in candidate_comfy_roots():
        if not _looks_like_comfy(root):
            continue
        if derive_python(root, None) is None:
            continue
        usable.append(root)
    if not usable:
        return None
    for root in usable:
        node = node_dir(root) / "nodes" / "enhance_video.py"
        if node.is_file():
            return root
    return usable[0]


def install_comfyui(app_dir: Path, progress: ProgressFn | None = None) -> Path:
    """Download and unpack the official Windows portable build; return its root."""
    app_dir = Path(app_dir)
    url, sha256 = latest_comfyui_archive()
    archive = app_dir / "downloads" / COMFY_ASSET
    download(url, archive, sha256=sha256, progress=progress, label=COMFY_ASSET)
    seven_zip = ensure_7zr(app_dir, progress)
    target = app_dir / "comfyui"
    _progress(progress, "extract", 0, 0)
    extract_7z(archive, target, seven_zip)
    root = find_comfy_root(target)
    if root is None:
        raise InstallError(f"no ComfyUI found under {target} after extraction")
    return root


def app_dir(comfy_root: Path) -> Path:
    """The folder that holds `main.py` and `custom_nodes` (layouts differ)."""
    root = Path(comfy_root)
    if (root / "ComfyUI" / "main.py").is_file():
        return root / "ComfyUI"
    if (root / "main.py").is_file():
        return root
    return root


def node_dir(comfy_root: Path) -> Path:
    return app_dir(comfy_root) / "custom_nodes" / NODE_DIR_NAME


def install_node(comfy_root: Path, progress: ProgressFn | None = None) -> Path:
    """Fetch the node pack from its repository archive (no git needed)."""
    comfy_root = Path(comfy_root)
    target = node_dir(comfy_root)
    if (target / "nodes" / "enhance_video.py").is_file():
        return target
    archive = comfy_root / "downloads" / "ComfyUI-DLSS5-Enhancer.zip"
    download(NODE_ZIP, archive, progress=progress, label=NODE_DIR_NAME)
    if target.is_dir():
        shutil.rmtree(target)
    extract_zip(archive, target)
    return target


def pip_install(python: Path, packages: Iterable[str], logger=None) -> None:
    """Install the node's requirements into ComfyUI's interpreter."""
    command = [str(python), "-m", "pip", "install", "--quiet", *packages]
    result = run_hidden(command)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        raise InstallError(detail[-1] if detail else "pip install failed")
    if logger is not None:
        logger.info("pip install ok: %s", ", ".join(packages))


def install_runtime(
    python: Path,
    node: Path,
    *,
    runtime_dir: Path | None = None,
    progress: ProgressFn | None = None,
) -> None:
    """Run the node's own installer (it fetches the third-party runtime)."""
    script = Path(node) / RUNTIME_SCRIPT
    if not script.is_file():
        raise InstallError(f"{script} not found")
    command = [str(python), str(script)]
    if runtime_dir is not None:
        command += ["--runtime-dir", str(runtime_dir)]
    else:
        command += ["--yes"]
        _progress(progress, "runtime", 0, 0)
    result = run_hidden(command, cwd=str(node))
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        raise InstallError(detail[-1] if detail else "install_runtime.py failed")


def runtime_notice() -> str:
    """The node's own licensing notice, shown before the 467 MB download."""
    return tr("d.runtime_notice")


def make_test_clip(ffmpeg: Path, dest: Path, seconds: float = 1.0) -> Path:
    """A tiny synthetic clip, used by the end-of-setup self test."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(ffmpeg),
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=size=320x180:rate=24:duration={seconds}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={seconds}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(dest),
    ]
    result = run_hidden(command)
    if result.returncode != 0:
        raise InstallError("could not build the test clip")
    return dest


def temp_workspace() -> Path:
    return Path(tempfile.mkdtemp(prefix="dlss5-setup-"))
