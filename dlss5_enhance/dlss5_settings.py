"""The DLSS5 node's settings: names, bounds, defaults and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import UsageError
from .i18n import tr

FLOAT = "float"
INT = "int"
BOOL = "bool"
COMBO = "combo"

UPSCALING_MODES: tuple[str, ...] = (
    "1x (DLAA / native)",
    "1.5x (Quality)",
    "1.724x (Balanced)",
    "2x (Performance)",
    "3x (Ultra Performance)",
)


@dataclass(frozen=True)
class Setting:
    name: str
    kind: str
    default: Any
    minimum: float | None = None
    maximum: float | None = None
    options: tuple[str, ...] = ()
    advanced: bool = False

    @property
    def label_key(self) -> str:
        return f"d.set.{self.name}.label"

    @property
    def hint_key(self) -> str:
        return f"d.set.{self.name}.hint"

    def coerce(self, value: Any) -> Any:
        if self.kind == FLOAT:
            return float(value)
        if self.kind == INT:
            return int(value)
        if self.kind == BOOL:
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"true", "yes", "1", "on"}
        return str(value)


SETTINGS: tuple[Setting, ...] = (
    Setting("upscaling_mode", COMBO, UPSCALING_MODES[0], options=UPSCALING_MODES),
    Setting("dlss_model_preset", COMBO, "M", options=("Default", "J", "K", "L", "M")),
    Setting("local_structure_strength", FLOAT, 1.5, 0.0, 2.0),
    Setting("skin_structure_strength", FLOAT, 2.0, -1.0, 2.0),
    Setting("automatic_mask", BOOL, True),
    Setting("nr_intensity", FLOAT, 1.0, 0.0, 2.0),
    Setting("local_tone_strength", FLOAT, 1.0, 0.0, 2.0),
    Setting("nr_style", COMBO, "Default", options=("Default", "Natural", "Cinematic")),
    Setting("motion", COMBO, "auto", options=("auto", "optical_flow", "none"), advanced=True),
    Setting("scene_change_threshold", FLOAT, 0.24, 0.01, 1.0, advanced=True),
    Setting("warmup_frames", INT, 0, 0, 16, advanced=True),
)

BY_NAME: dict[str, Setting] = {setting.name: setting for setting in SETTINGS}

STRONG: dict[str, Any] = {
    "local_structure_strength": 2.0,
    "skin_structure_strength": 2.0,
    "automatic_mask": True,
    "dlss_model_preset": "M",
}


def coerce_all(values: dict[str, Any]) -> dict[str, Any]:
    """Normalise raw values (CLI strings, config, GUI) to the node's types."""
    coerced: dict[str, Any] = {}
    for name, value in values.items():
        setting = BY_NAME.get(name)
        if setting is None:
            continue
        coerced[name] = setting.coerce(value)
    return coerced


def validate(values: dict[str, Any]) -> None:
    """Raise UsageError on an unknown name, an out-of-range value or a bad combo."""
    for name, value in values.items():
        setting = BY_NAME.get(name)
        if setting is None:
            known = ", ".join(BY_NAME)
            raise UsageError(tr("d.set.unknown", name=name, known=known))
        if setting.kind == COMBO and str(value) not in setting.options:
            raise UsageError(
                tr(
                    "d.set.bad_option",
                    name=name,
                    value=value,
                    options=", ".join(setting.options),
                )
            )
        if setting.kind in (FLOAT, INT):
            number = setting.coerce(value)
            if setting.minimum is not None and number < setting.minimum:
                raise UsageError(
                    tr("d.set.too_low", name=name, value=value, minimum=setting.minimum)
                )
            if setting.maximum is not None and number > setting.maximum:
                raise UsageError(
                    tr("d.set.too_high", name=name, value=value, maximum=setting.maximum)
                )
    if values.get("skin_structure_strength") is not None and values.get("automatic_mask") is False:
        raise UsageError(tr("d.set.skin_needs_mask"))
