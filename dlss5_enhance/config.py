"""Configuration: defaults < config.yaml < settings.json < command line."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from .app_paths import DEFAULT_CONFIG_NAME, DEFAULT_WORKFLOW, TOOL_ROOT, downloads_dir
from .errors import UsageError
from .i18n import tr
from .mappings import normalize_extensions
from .presets import Preset, load_presets, resolve_preset

DEFAULT_EXTENSIONS = ("mp4", "mov", "mkv", "webm")

PRESET_JOB_VALUES: dict[str, Any] = {
    "quality": "Best",
    "codec": "h265",
    "container": "mkv",
}

#: What 'upscale + enhance' presets add on top of the upscaling mode.
STRONG_PRESET_SETTINGS: dict[str, Any] = {
    "local_structure_strength": 2.0,
    "skin_structure_strength": 2.0,
    "automatic_mask": True,
    "dlss_model_preset": "M",
}


def default_presets() -> dict[str, Any]:
    """The five shipped presets; `upscaling_mode` is what actually changes."""
    return {
        "ameliore": {
            "label": "Enhance (1x)",
            "upscaling_mode": "1x (DLAA / native)",
            **PRESET_JOB_VALUES,
        },
        "ameliore_plus": {
            "label": "Enhance+ (1x)",
            "upscaling_mode": "1x (DLAA / native)",
            "settings": {"local_structure_strength": 2.0},
            **PRESET_JOB_VALUES,
        },
        "x15": {
            "label": "Upscale x1.5",
            "upscaling_mode": "1.5x (Quality)",
            **PRESET_JOB_VALUES,
        },
        "x2": {
            "label": "Upscale x2",
            "upscaling_mode": "2x (Performance)",
            **PRESET_JOB_VALUES,
        },
        "x3": {
            "label": "Upscale x3",
            "upscaling_mode": "3x (Ultra Performance)",
            **PRESET_JOB_VALUES,
        },
            "x2_plus": {
            "label": "Upscale x2 + Enhance",
            "upscaling_mode": "2x (Performance)",
            "settings": dict(STRONG_PRESET_SETTINGS),
            **PRESET_JOB_VALUES,
        },
        "x3_plus": {
            "label": "Upscale x3 + Enhance",
            "upscaling_mode": "3x (Ultra Performance)",
            "settings": dict(STRONG_PRESET_SETTINGS),
            **PRESET_JOB_VALUES,
        },
    }


@dataclass(frozen=True)
class ComfyConfig:
    root: Path | None = None
    python: Path | None = None
    server_module: str = "ComfyUI/main.py"
    host: str = "127.0.0.1"
    port: int = 8188
    startup_timeout: float = 240.0
    extra_model_paths_config: Path | None = None
    ffmpeg: Path | None = None
    ffprobe: Path | None = None
    server_log_dir: Path | None = None
    extra_args: tuple[str, ...] = ()
    port_fallback: tuple[int, ...] = (8189, 8199, 8200)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}/ws"

    def server_command(self, port: int | None = None) -> list[str]:
        command = [
            str(self.python),
            "-s",
            self.server_module,
            "--listen",
            self.host,
            "--port",
            str(self.port if port is None else port),
        ]
        if self.extra_model_paths_config is not None:
            command += ["--extra-model-paths-config", str(self.extra_model_paths_config)]
        command += list(self.extra_args)
        return command


@dataclass(frozen=True)
class TargetSelector:
    class_type: str | None = "DLSS5EnhanceVideoFile"
    title: str | None = None
    id: str | None = None


@dataclass(frozen=True)
class WorkflowConfig:
    path: Path
    target: TargetSelector = field(default_factory=TargetSelector)
    settings_class_type: str = "DLSS5Settings"
    settings_upscaling_input: str = "upscaling_mode"


@dataclass(frozen=True)
class ProcessingConfig:
    quality: str = "Auto"
    codec: str = "HEVC"
    container: str = "MKV"
    max_frames: int = 0
    copy_audio: bool = True
    verify_neural_rendering: bool = True
    output: Path | None = None
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS
    timeout: float = 1200.0
    max_restarts: int = 3


@dataclass(frozen=True)
class RunConfig:
    autostart: bool = True
    keep_server: bool = False
    auto_restart: bool | None = None
    preset_name: str | None = None


@dataclass(frozen=True)
class Config:
    comfy: ComfyConfig
    workflow: WorkflowConfig
    processing: ProcessingConfig
    run: RunConfig
    log_dir: Path
    log_level: str
    language: str
    config_path: Path | None = None
    settings_path: Path | None = None
    presets: Mapping[str, Preset] = field(default_factory=dict)
    preset: Preset | None = None
    settings_overrides: Mapping[str, Any] = field(default_factory=dict)

    @property
    def installed(self) -> bool:
        """True when ComfyUI and its interpreter were resolved."""
        return self.comfy.root is not None and self.comfy.python is not None


def _defaults(base_dir: Path) -> dict[str, Any]:
    return {
        "comfy": {
            "root": None,
            "python": None,
            "server_module": "ComfyUI/main.py",
            "host": "127.0.0.1",
            "port": 8188,
            "startup_timeout": 240,
            "extra_model_paths_config": None,
            "ffmpeg": None,
            "ffprobe": None,
            "server_log_dir": "logs",
            "extra_args": [],
            "port_fallback": [8189, 8199, 8200],
        },
        "workflow": {
            "path": DEFAULT_WORKFLOW,
            "target": {"class_type": "DLSS5EnhanceVideoFile", "title": None, "id": None},
            "settings": {
                "class_type": "DLSS5Settings",
                "upscaling_input": "upscaling_mode",
            },
        },
        "processing": {
            "quality": "Auto",
            "codec": "HEVC",
            "container": "MKV",
            "max_frames": 0,
            "copy_audio": True,
            "verify_neural_rendering": True,
            "output": None,
            "extensions": list(DEFAULT_EXTENSIONS),
            "timeout": 1200,
            "max_restarts": 3,
        },
        "logging": {"dir": "logs", "level": "INFO"},
        "language": None,
        "dlss5_settings": {},
        "run": {"autostart": True, "keep_server": False, "auto_restart": None, "preset": None},
        "presets": default_presets(),
    }


def _deep_merge(base: dict[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if value is None:
            continue
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def _resolve_path(value: Any, base_dir: Path) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return Path(path)


def _as_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "yes", "1", "on"}:
        return True
    if isinstance(value, str) and value.strip().lower() in {"false", "no", "0", "off"}:
        return False
    raise UsageError(tr("g.bool_expected", key=key, value=value))


def _as_float(value: Any, key: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise UsageError(tr("g.number_expected", key=key, value=value)) from exc


def _as_int(value: Any, key: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise UsageError(tr("g.int_expected", key=key, value=value)) from exc


def _optional_bool(value: Any, key: str) -> bool | None:
    if value is None:
        return None
    return _as_bool(value, key)


def derive_python(root: Path | None, explicit: Any) -> Path | None:
    """Find ComfyUI's interpreter under *root* when it was not given."""
    if explicit not in (None, ""):
        return Path(str(explicit)).expanduser()
    if root is None:
        return None
    candidates = (
        root / "python_embeded" / "python.exe",
        root / "ComfyUI" / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python.exe",
        root / "venv" / "Scripts" / "python.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def settings_overrides(settings: Any, app_root: Path | None = None) -> dict[str, Any]:
    """Turn a settings.json record into a config layer (paths resolved)."""
    if settings is None:
        return {}
    from .settings_store import resolve_path

    root = app_root if app_root is not None else TOOL_ROOT
    comfy = {
        "root": None if not settings.comfy_root else str(resolve_path(settings.comfy_root, root)),
        "python": (
            None if not settings.comfy_python else str(resolve_path(settings.comfy_python, root))
        ),
        "ffmpeg": None if not settings.ffmpeg else str(resolve_path(settings.ffmpeg, root)),
        "ffprobe": None if not settings.ffprobe else str(resolve_path(settings.ffprobe, root)),
        "port": getattr(settings, "comfy_port", None),
    }
    processing = {
        "output": None if not settings.output_dir else str(resolve_path(settings.output_dir, root))
    }
    overrides: dict[str, Any] = {
        "comfy": {key: value for key, value in comfy.items() if value is not None},
        "processing": {key: value for key, value in processing.items() if value is not None},
        "language": settings.language,
        "run": {"preset": settings.preset},
    }
    if settings.workflow:
        overrides["workflow"] = {"path": str(resolve_path(settings.workflow, root))}
    return overrides


def load_config(
    path: str | Path | None = None,
    overrides: Mapping[str, Any] | None = None,
    base_dir: Path | None = None,
    settings: Any = None,
    app_root: Path | None = None,
) -> Config:
    """Load config.yaml, layer settings.json then the CLI overrides, resolve paths."""
    root = app_root if app_root is not None else TOOL_ROOT
    config_path = Path(path) if path else root / DEFAULT_CONFIG_NAME
    config_path = Path(config_path).expanduser()
    origin = base_dir if base_dir is not None else config_path.resolve().parent

    raw = _defaults(origin)
    if config_path.is_file():
        try:
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise UsageError(tr("g.yaml_invalid", path=config_path, error=exc)) from exc
        if not isinstance(loaded, Mapping):
            raise UsageError(tr("g.mapping_expected", path=config_path))
        raw = _deep_merge(raw, loaded)

    raw = _deep_merge(raw, settings_overrides(settings, root))

    presets = load_presets(raw.get("presets"))
    preset_name = None
    if overrides:
        preset_name = (overrides.get("run") or {}).get("preset")
    if preset_name is None:
        preset_name = (raw.get("run") or {}).get("preset")
    preset = resolve_preset(preset_name, presets)
    if preset is not None:
        raw = _deep_merge(raw, {"processing": preset.job_values()})

    if overrides:
        raw = _deep_merge(raw, overrides)

    comfy = raw["comfy"]
    workflow = raw["workflow"]
    processing = raw["processing"]
    logging_cfg = raw.get("logging", {})
    run_cfg = raw.get("run", {})

    extensions = normalize_extensions(processing.get("extensions")) or DEFAULT_EXTENSIONS
    timeout = _as_float(processing.get("timeout", 1200), "processing.timeout")
    if timeout <= 0:
        raise UsageError(tr("g.timeout_positive"))

    comfy_root = _resolve_path(comfy.get("root"), origin)
    comfy_python = derive_python(comfy_root, comfy.get("python"))
    if comfy_python is not None and not Path(comfy_python).is_absolute():
        comfy_python = origin / Path(comfy_python)
    output = _resolve_path(processing.get("output"), origin) or downloads_dir()

    target = workflow.get("target") or {}
    settings_cfg = workflow.get("settings") or {}
    from .dlss5_settings import coerce_all, validate

    node_settings = coerce_all(dict(raw.get("dlss5_settings") or {}))
    validate(node_settings)
    comfy_cfg = ComfyConfig(
        root=comfy_root,
        python=None if comfy_python is None else Path(comfy_python),
        server_module=str(comfy.get("server_module", "ComfyUI/main.py")),
        host=str(comfy.get("host", "127.0.0.1")),
        port=_as_int(comfy.get("port", 8188), "comfy.port"),
        startup_timeout=_as_float(comfy.get("startup_timeout", 240), "comfy.startup_timeout"),
        extra_model_paths_config=_resolve_path(comfy.get("extra_model_paths_config"), origin),
        ffmpeg=_resolve_path(comfy.get("ffmpeg"), origin),
        ffprobe=_resolve_path(comfy.get("ffprobe"), origin),
        server_log_dir=_resolve_path(comfy.get("server_log_dir"), origin),
        extra_args=tuple(str(item) for item in (comfy.get("extra_args") or [])),
        port_fallback=tuple(
            _as_int(item, "comfy.port_fallback")
            for item in (comfy.get("port_fallback") or [8189, 8199, 8200])
        ),
    )

    return Config(
        comfy=comfy_cfg,
        workflow=WorkflowConfig(
            path=Path(_resolve_path(workflow.get("path"), origin) or (origin / DEFAULT_WORKFLOW)),
            target=TargetSelector(
                class_type=target.get("class_type", "DLSS5EnhanceVideoFile"),
                title=target.get("title"),
                id=None if target.get("id") in (None, "") else str(target.get("id")),
            ),
            settings_class_type=str(settings_cfg.get("class_type", "DLSS5Settings")),
            settings_upscaling_input=str(settings_cfg.get("upscaling_input", "upscaling_mode")),
        ),
        processing=ProcessingConfig(
            quality=str(processing.get("quality", "Auto")),
            codec=str(processing.get("codec", "HEVC")),
            container=str(processing.get("container", "MKV")),
            max_frames=_as_int(processing.get("max_frames", 0), "processing.max_frames"),
            copy_audio=_as_bool(processing.get("copy_audio", True), "processing.copy_audio"),
            verify_neural_rendering=_as_bool(
                processing.get("verify_neural_rendering", True),
                "processing.verify_neural_rendering",
            ),
            output=output,
            extensions=extensions,
            timeout=timeout,
            max_restarts=_as_int(processing.get("max_restarts", 3), "processing.max_restarts"),
        ),
        run=RunConfig(
            autostart=_as_bool(run_cfg.get("autostart", True), "run.autostart"),
            keep_server=_as_bool(run_cfg.get("keep_server", False), "run.keep_server"),
            auto_restart=_optional_bool(run_cfg.get("auto_restart"), "run.auto_restart"),
            preset_name=preset.name if preset is not None else None,
        ),
        log_dir=Path(_resolve_path(logging_cfg.get("dir", "logs"), origin) or (origin / "logs")),
        log_level=str(logging_cfg.get("level", "INFO")).upper(),
        language=str(raw.get("language") or ""),
        config_path=config_path if config_path.is_file() else None,
        presets=presets,
        preset=preset,
        settings_overrides=node_settings,
    )


def with_processing(config: Config, **changes: Any) -> Config:
    """Return a copy of *config* with processing fields replaced."""
    return replace(config, processing=replace(config.processing, **changes))


def with_run(config: Config, **changes: Any) -> Config:
    """Return a copy of *config* with run fields replaced."""
    return replace(config, run=replace(config.run, **changes))
