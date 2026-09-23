"""The formats ComfyUI's save nodes can write, and the inputs they need.

`SaveImageAdvanced` uses a *dynamic combo*: the chosen format is a plain string,
and its sub-inputs are separate keys named `format.<name>` in the API prompt.
`SaveImage` (the classic node) always writes PNG.
"""

from __future__ import annotations

from typing import Any

FORMATS: dict[str, dict[str, Any]] = {
    "png": {
        "format.bit_depth": "8-bit",
        "format.input_color_space": "sRGB",
    },
    "avif": {
        "format.bit_depth": "auto",
        "format.input_color_space": "sRGB",
        "format.crf": 18,
        "format.save_mode": "still images",
    },
    "exr": {
        "format.bit_depth": "32-bit float",
        "format.input_color_space": "sRGB",
    },
}

EXTENSIONS: dict[str, str] = {"png": ".png", "avif": ".avif", "exr": ".exr"}

NAMES: tuple[str, ...] = tuple(FORMATS)


def normalize(value: object) -> str | None:
    """Accept 'PNG', 'png', '.png' or 'jpeg' (unsupported) and return a known name."""
    if value in (None, ""):
        return None
    text = str(value).strip().lower().lstrip(".")
    if text in {"jpg", "jpeg"}:
        return None
    return text if text in FORMATS else None


def inputs_for(format_name: str, format_input: str = "format") -> dict[str, Any]:
    """The value plus its sub-inputs, ready to write into the save node."""
    name = normalize(format_name)
    if name is None:
        return {}
    values: dict[str, Any] = {format_input: name}
    for key, value in FORMATS[name].items():
        sub = key.partition(".")[2]
        values[f"{format_input}.{sub}"] = value
    return values


def extension(format_name: str | None) -> str:
    return EXTENSIONS.get(normalize(format_name) or "png", ".png")
