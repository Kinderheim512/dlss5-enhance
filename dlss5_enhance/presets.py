"""Presets: named bundles of job settings, declared in config.yaml."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .errors import UsageError
from .i18n import tr

UPSCALING_MODES: tuple[str, ...] = (
    "1x (DLAA / native)",
    "1.5x (Quality)",
    "1.724x (Balanced)",
    "2x (Performance)",
    "3x (Ultra Performance)",
)

FACTORS: dict[str, float] = {
    "1x (DLAA / native)": 1.0,
    "1.5x (Quality)": 1.5,
    "1.724x (Balanced)": 1.724,
    "2x (Performance)": 2.0,
    "3x (Ultra Performance)": 3.0,
}

JOB_KEYS = (
    "quality",
    "codec",
    "container",
    "max_frames",
    "copy_audio",
    "verify_neural_rendering",
)

KNOWN_KEYS = ("label", "upscaling_mode", "settings", *JOB_KEYS)


@dataclass(frozen=True)
class Preset:
    name: str
    label: str
    upscaling_mode: str | None = None
    quality: str | None = None
    codec: str | None = None
    container: str | None = None
    max_frames: int | None = None
    copy_audio: bool | None = None
    verify_neural_rendering: bool | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)

    @property
    def factor(self) -> float:
        return FACTORS.get(self.upscaling_mode or "", 1.0)

    def job_values(self) -> dict[str, Any]:
        """Video-node inputs this preset overrides (None entries dropped)."""
        values = {key: getattr(self, key) for key in JOB_KEYS}
        return {key: value for key, value in values.items() if value is not None}

    def settings_values(self, upscaling_input: str = "upscaling_mode") -> dict[str, Any]:
        """DLSS5 Settings inputs this preset overrides: upscaling plus extras."""
        values: dict[str, Any] = dict(self.settings)
        if self.upscaling_mode:
            values[upscaling_input] = self.upscaling_mode
        return values


def normalize_upscaling(value: Any) -> str:
    """Accept the node's label ('2x (Performance)') or a bare factor ('2x', 2)."""
    if value is None:
        raise UsageError(tr("p.upscaling_required"))
    text = str(value).strip()
    if text in FACTORS:
        return text
    lowered = text.lower().rstrip("x").strip()
    try:
        factor = float(lowered)
    except ValueError:
        factor = None
    if factor is not None:
        for label, known in FACTORS.items():
            if abs(known - factor) < 1e-9:
                return label
    raise UsageError(
        tr("p.upscaling_unknown", value=value, modes=", ".join(UPSCALING_MODES))
    )


def load_presets(raw: Mapping[str, Any] | None) -> dict[str, Preset]:
    """Build the presets declared under `presets:` in config.yaml."""
    if not raw:
        return {}
    if not isinstance(raw, Mapping):
        raise UsageError(tr("p.section_mapping"))
    presets: dict[str, Preset] = {}
    for name, body in raw.items():
        key = str(name).strip()
        if not key:
            raise UsageError(tr("p.empty_name"))
        if not isinstance(body, Mapping):
            raise UsageError(tr("p.body_mapping", key=key))
        unknown = sorted(set(body) - set(KNOWN_KEYS))
        if unknown:
            raise UsageError(
                tr(
                    "p.unknown_keys",
                    key=key,
                    unknown=", ".join(unknown),
                    known=", ".join(KNOWN_KEYS),
                )
            )
        settings = body.get("settings") or {}
        if not isinstance(settings, Mapping):
            raise UsageError(tr("p.settings_mapping", key=key))
        presets[key] = Preset(
            name=key,
            label=str(body.get("label") or key),
            upscaling_mode=(
                normalize_upscaling(body["upscaling_mode"])
                if body.get("upscaling_mode") is not None
                else None
            ),
            quality=body.get("quality"),
            codec=body.get("codec"),
            container=body.get("container"),
            max_frames=body.get("max_frames"),
            copy_audio=body.get("copy_audio"),
            verify_neural_rendering=body.get("verify_neural_rendering"),
            settings=dict(settings),
        )
    return presets


def resolve_preset(name: str | None, presets: Mapping[str, Preset]) -> Preset | None:
    """Look a preset up by name; an unknown name lists what exists."""
    if name is None:
        return None
    key = str(name).strip()
    if key in presets:
        return presets[key]
    known = ", ".join(sorted(presets)) or tr("p.none_configured")
    raise UsageError(tr("p.unknown_name", name=name, known=known))


def describe_presets(presets: Mapping[str, Preset]) -> list[str]:
    """One line per preset, for --list-presets and the GUI."""
    lines = []
    for name in sorted(presets):
        preset = presets[name]
        mode = preset.upscaling_mode or "mode du workflow"
        detail = f"{name}: {preset.label} — {mode}"
        if preset.settings:
            detail += " | " + ", ".join(f"{k}={v}" for k, v in sorted(preset.settings.items()))
        lines.append(detail)
    return lines
