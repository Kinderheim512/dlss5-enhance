"""CLI value -> DLSS5 node enum, plus the codec/container compatibility rules."""

from __future__ import annotations

from .errors import MappingError
from .i18n import tr

CODECS = ("H.264", "HEVC", "AV1", "ProRes Proxy")
CONTAINERS = ("MP4", "MKV", "MOV")
QUALITIES = ("Auto", "Good", "Best", "Max")

CODEC_ALIASES = {
    "h264": "H.264",
    "h.264": "H.264",
    "avc": "H.264",
    "h265": "HEVC",
    "h.265": "HEVC",
    "hevc": "HEVC",
    "av1": "AV1",
    "prores": "ProRes Proxy",
    "proresproxy": "ProRes Proxy",
    "prores proxy": "ProRes Proxy",
}

QUALITY_ALIASES = {
    "draft": "Auto",
    "low": "Auto",
    "auto": "Auto",
    "normal": "Good",
    "medium": "Good",
    "good": "Good",
    "high": "Best",
    "best": "Best",
    "max": "Max",
}

CONTAINER_ALIASES = {"mp4": "MP4", "mkv": "MKV", "mov": "MOV"}


def _canonical(value: object, aliases: dict[str, str], canonical: tuple[str, ...]) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    if key in aliases:
        return aliases[key]
    for item in canonical:
        if key == item.lower():
            return item
    return None


def resolve_quality(value: object) -> str:
    """Map --quality onto Auto/Good/Best/Max."""
    resolved = _canonical(value, QUALITY_ALIASES, QUALITIES)
    if resolved is None:
        raise MappingError(tr("m.quality_invalid", value=value))
    return resolved


def resolve_codec(value: object) -> str:
    """Map --codec onto H.264/HEVC/AV1/ProRes Proxy."""
    resolved = _canonical(value, CODEC_ALIASES, CODECS)
    if resolved is None:
        raise MappingError(tr("m.codec_invalid", value=value))
    return resolved


def resolve_container(value: object) -> str:
    """Map --container onto MP4/MKV/MOV."""
    resolved = _canonical(value, CONTAINER_ALIASES, CONTAINERS)
    if resolved is None:
        raise MappingError(tr("m.container_invalid", value=value))
    return resolved


def validate_codec_container(codec: str, container: str) -> None:
    """Mirror the node's own rule: ProRes Proxy has no MP4 variant."""
    if codec not in CODECS:
        raise MappingError(tr("m.codec_unknown", codec=codec, options=", ".join(CODECS)))
    if container not in CONTAINERS:
        raise MappingError(
            tr("m.container_unknown", container=container, options=", ".join(CONTAINERS))
        )
    if codec == "ProRes Proxy" and container == "MP4":
        raise MappingError(tr("m.prores_needs"))

def normalize_extensions(values: object) -> tuple[str, ...]:
    """Normalise 'mp4, .MOV' style input to ('mp4', 'mov')."""
    if values is None:
        return ()
    if isinstance(values, str):
        raw = values.replace(";", ",").split(",")
    else:
        raw = [str(item) for item in values]
    seen: list[str] = []
    for item in raw:
        ext = item.strip().lstrip("*.").lower()
        if ext and ext not in seen:
            seen.append(ext)
    return tuple(seen)
