"""Installation check and first-run setup."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import installer
from .config import Config, derive_python, load_config
from .i18n import tr
from .settings_store import AppSettings, save_settings, store_path

CREATE_NO_WINDOW = 0x08000000
OK = "ok"
MISSING = "missing"
BROKEN = "broken"
STATUS_KEYS = {OK: "d.status.ok", MISSING: "d.status.missing", BROKEN: "d.status.broken"}
MIN_FREE_GB = 6.0
RUNTIME_FILES = installer.RUNTIME_FILES


@dataclass
class Check:
    key: str
    status: str
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == OK


def check_gpu() -> Check:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return Check("d.gpu", MISSING, tr("d.gpu_missing"))
    line = (result.stdout or "").strip().splitlines()
    if result.returncode != 0 or not line:
        return Check("d.gpu", MISSING, tr("d.gpu_missing"))
    name, _, driver = line[0].partition(",")
    return Check("d.gpu", OK, tr("d.gpu_ok", name=name.strip(), driver=driver.strip()))


def check_comfyui(config: Config) -> Check:
    root = config.comfy.root
    if root is None or not (Path(root) / "ComfyUI" / "main.py").is_file():
        return Check("d.comfyui", MISSING, tr("d.comfy_missing"))
    if config.comfy.python is None:
        return Check("d.comfyui", BROKEN, tr("d.comfy_missing"))
    return Check("d.comfyui", OK, tr("d.comfy_ok", root=root))


def node_dir(config: Config) -> Path | None:
    if config.comfy.root is None:
        return None
    return installer.node_dir(Path(config.comfy.root))


def check_node(config: Config) -> Check:
    node = node_dir(config)
    if node is None or not (node / "nodes" / "enhance_video.py").is_file():
        return Check("d.node", MISSING, tr("d.node_missing"))
    return Check("d.node", OK, tr("d.node_ok", path=node))


def check_runtime(config: Config) -> Check:
    node = node_dir(config)
    if node is None:
        return Check("d.runtime", MISSING, tr("d.runtime_missing"))
    runtime = node / "runtime"
    if not all((runtime / name).is_file() for name in RUNTIME_FILES):
        return Check("d.runtime", MISSING, tr("d.runtime_missing"))
    return Check("d.runtime", OK, tr("d.runtime_ok", path=runtime))


def check_ffmpeg(config: Config) -> Check:
    ffmpeg = config.comfy.ffmpeg
    if ffmpeg is None or not Path(ffmpeg).is_file():
        return Check("d.ffmpeg", MISSING, tr("d.ffmpeg_missing"))
    return Check("d.ffmpeg", OK, tr("d.ffmpeg_ok", path=ffmpeg))


def check_disk(config: Config) -> Check:
    target = config.comfy.root or Path.home()
    try:
        usage = shutil.disk_usage(str(target))
    except OSError:
        return Check("d.disk", MISSING, tr("d.disk_low", free="?", volume=target))
    free = usage.free / (1024**3)
    volume = Path(target).anchor or str(target)
    if free < MIN_FREE_GB:
        return Check("d.disk", BROKEN, tr("d.disk_low", free=f"{free:.1f}", volume=volume))
    return Check("d.disk", OK, tr("d.disk_ok", free=f"{free:.1f}", volume=volume))


def run_checks(config: Config) -> list[Check]:
    return [
        check_gpu(),
        check_comfyui(config),
        check_node(config),
        check_runtime(config),
        check_ffmpeg(config),
        check_disk(config),
    ]


def report(config: Config, sink) -> int:
    """Print the checklist; 0 when everything is in place."""
    checks = run_checks(config)
    sink.line(tr("d.header"))
    for check in checks:
        status = tr(STATUS_KEYS[check.status])
        detail = f" — {check.detail}" if check.detail else ""
        sink.line(tr("d.line", status=status, label=tr(check.key), detail=detail))
    ready = all(check.ok for check in checks)
    sink.line(tr("d.ready") if ready else tr("d.not_ready"))
    return 0 if ready else 1


def _ask(question: str) -> bool:
    if not sys.stdin or not sys.stdin.isatty():
        return False
    try:
        answer = input(question)
    except EOFError:
        return False
    return answer.strip().lower() in {"y", "yes", "o", "oui"}


def _ask_path(question: str) -> str:
    if not sys.stdin or not sys.stdin.isatty():
        return ""
    try:
        return input(question).strip().strip('"')
    except EOFError:
        return ""


def _looks_like_comfy(path: Path) -> bool:
    return (Path(path) / "ComfyUI" / "main.py").is_file()


def resolve_comfyui(
    config: Config,
    logger,
    sink,
    *,
    comfy_root: str | None = None,
    allow_download: bool = False,
) -> Path | None:
    """Point at an existing ComfyUI, or download the portable build."""
    if comfy_root:
        candidate = Path(comfy_root).expanduser()
        if not _looks_like_comfy(candidate):
            raise SystemExit(tr("d.invalid_root", path=candidate))
        return candidate
    if config.installed and _looks_like_comfy(Path(config.comfy.root)):
        return Path(config.comfy.root)

    answer = _ask_path(tr("d.ask_comfy_browse"))
    if answer:
        candidate = Path(answer).expanduser()
        if not _looks_like_comfy(candidate):
            raise SystemExit(tr("d.invalid_root", path=candidate))
        return candidate

    if allow_download or _ask(tr("d.ask_comfy_download")):
        from .app_paths import TOOL_ROOT

        sink.line(tr("d.comfy_downloading"))
        root = installer.install_comfyui(
            TOOL_ROOT, progress=lambda label, done, total: _show(sink, label, done, total)
        )
        logger.info("ComfyUI installed at %s", root)
        return root
    return None


def _show(sink, label: str, done: int, total: int) -> None:
    if total:
        sink.progress(f"{label}  {done * 100 // total}%  {done / 1e6:.1f} / {total / 1e6:.1f} MB")
    else:
        sink.progress(label)


def run_setup(
    config: Config,
    logger,
    sink,
    *,
    settings: AppSettings | None = None,
    state_path: Path | None = None,
    comfy_root: str | None = None,
    allow_download: bool = False,
    accept_runtime: bool = False,
    runtime_dir: str | None = None,
    selftest: bool = True,
) -> int:
    """Check, install what is missing, remember the paths, prove it works."""
    settings = settings or AppSettings()
    logger.info(tr("d.header"))
    root = resolve_comfyui(
        config, logger, sink, comfy_root=comfy_root, allow_download=allow_download
    )
    if root is None:
        report(config, sink)
        return 1

    python = derive_python(root, None)
    if python is None:
        sink.line(tr("d.not_ready"))
        return 1

    settings.comfy_root = store_path(root)
    settings.comfy_python = store_path(python)

    node = installer.node_dir(root)
    if not (node / "nodes" / "enhance_video.py").is_file():
        sink.line(tr("d.node_downloading"))
        try:
            installer.install_node(
            root, progress=lambda label, done, total: _show(sink, label, done, total)
        )
        except installer.InstallError as exc:
            logger.error("%s", exc)
            sink.line(tr("d.node_install_hint"))
            return 1
        sink.line(tr("d.deps_installing"))
        installer.pip_install(python, installer.NODE_REQUIREMENTS, logger)

    runtime = node / "runtime"
    if not all((runtime / name).is_file() for name in RUNTIME_FILES):
        if not runtime_dir and not accept_runtime:
            runtime_dir = _ask_path(tr("d.ask_runtime_dir")) or None
            if not runtime_dir:
                sink.line(tr("d.runtime_notice"))
                if not _ask(tr("d.ask_accept_runtime")):
                    sink.line(tr("d.need_runtime_accept"))
                    return 1
        sink.line(tr("d.runtime_downloading"))
        try:
            installer.install_runtime(
                python,
                node,
                runtime_dir=Path(runtime_dir) if runtime_dir else None,
                progress=lambda label, done, total: _show(sink, label, done, total),
            )
        except installer.InstallError as exc:
            logger.error("%s", exc)
            return 1

    settings.ffmpeg = store_path(node / "ffmpeg" / "bin" / "ffmpeg.exe")
    settings.ffprobe = store_path(node / "ffmpeg" / "bin" / "ffprobe.exe")
    saved = save_settings(settings, path=state_path)
    if saved is not None:
        sink.line(tr("d.saved", path=saved))

    from .app_paths import TOOL_ROOT

    refreshed = load_config(
        path=config.config_path, settings=settings, app_root=TOOL_ROOT
    )
    if selftest:
        code = _self_test(refreshed, logger, sink, settings)
        if code != 0:
            return code
    return report(refreshed, sink)


def _self_test(config: Config, logger, sink, settings: AppSettings | None = None) -> int:
    """Render a one-second synthetic clip, proving the whole chain works."""
    from .app_paths import TOOL_ROOT
    from .runner import Orchestrator
    from .sources import resolve_sources

    sink.line(tr("d.selftest"))
    if config.comfy.ffmpeg is None or not Path(config.comfy.ffmpeg).is_file():
        sink.line(tr("d.selftest_failed", error=tr("d.ffmpeg_missing")))
        return 1
    workspace = installer.temp_workspace()
    try:
        clip = installer.make_test_clip(Path(config.comfy.ffmpeg), workspace / "clip.mp4")
        output = workspace / "out"
        output.mkdir(parents=True, exist_ok=True)
        sources, folder_mode = resolve_sources(
            input_path=str(clip), extensions=config.processing.extensions
        )
        run_config = load_config(
            path=config.config_path,
            overrides={"processing": {"output": str(output)}},
            settings=settings,
            app_root=TOOL_ROOT,
        )
        orchestrator = Orchestrator(config=run_config, logger=logger, sink=sink, force=True)
        code = orchestrator.run(sources, folder_mode)
        produced = sorted(output.glob("clip_*"))
        if code == 0 and produced:
            sink.line(tr("d.selftest_ok", path=produced[-1]))
            return 0
        sink.line(tr("d.selftest_failed", error=f"exit {code}"))
        return 1
    except Exception as exc:
        sink.line(tr("d.selftest_failed", error=exc))
        return 1
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def environment_hint() -> str:
    return os.environ.get("DLSS5_LANG", "")
