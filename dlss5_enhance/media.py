"""Source probing and encoder capability checks, using the node's own ffmpeg."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .errors import UsageError

CREATE_NO_WINDOW = 0x08000000
MAX_LONG_EDGE = 7680
MAX_SHORT_EDGE = 4320

CODEC_ENCODERS = {
    "H.264": "h264_nvenc",
    "HEVC": "hevc_nvenc",
    "AV1": "av1_nvenc",
    "ProRes Proxy": "prores_ks",
}

HARDWARE_CODECS = ("H.264", "HEVC", "AV1")


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    frames: int | None = None
    duration: float | None = None


def _run(command: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )


def probe_video(ffprobe: Path, source: Path, timeout: float = 60.0) -> VideoInfo:
    """Read the first video stream's geometry, frame count and duration."""
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,nb_frames,duration",
        "-of",
        "json",
        str(source),
    ]
    try:
        result = _run(command, timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UsageError(f"ffprobe could not read {source}: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or "").strip().splitlines()
        raise UsageError(
            f"ffprobe failed on {source}: {detail[-1] if detail else 'unknown error'}"
        )
    try:
        streams = json.loads(result.stdout).get("streams") or []
    except json.JSONDecodeError as exc:
        raise UsageError(f"ffprobe returned invalid JSON for {source}.") from exc
    if not streams:
        raise UsageError(f"{source} has no video stream.")
    stream = streams[0]
    frames = stream.get("nb_frames")
    duration = stream.get("duration")
    return VideoInfo(
        width=int(stream.get("width") or 0),
        height=int(stream.get("height") or 0),
        frames=int(frames) if str(frames).isdigit() else None,
        duration=float(duration) if _is_number(duration) else None,
    )


def _is_number(value: object) -> bool:
    try:
        float(value)  # type: ignore[arg-type]
        return True
    except (TypeError, ValueError):
        return False


def raw_scaled_size(width: int, height: int, factor: float) -> tuple[int, int]:
    """Scaled geometry before any clamping."""
    return max(2, int(round(width * factor))), max(2, int(round(height * factor)))


def exceeds_limits(width: int, height: int, factor: float) -> tuple[int, int] | None:
    """The requested size when it is beyond the node's caps, else None."""
    scaled = raw_scaled_size(width, height, factor)
    if max(scaled) > MAX_LONG_EDGE or min(scaled) > MAX_SHORT_EDGE:
        return scaled
    return None


def output_size(
    width: int,
    height: int,
    factor: float,
    max_long_edge: int = MAX_LONG_EDGE,
    max_short_edge: int = MAX_SHORT_EDGE,
) -> tuple[int, int]:
    """Scaled output geometry, clamped to the node's own limits."""
    scaled_w = max(2, int(round(width * factor)))
    scaled_h = max(2, int(round(height * factor)))
    long_edge, short_edge = max(scaled_w, scaled_h), min(scaled_w, scaled_h)
    if long_edge > max_long_edge:
        ratio = max_long_edge / long_edge
        scaled_w, scaled_h = int(scaled_w * ratio), int(scaled_h * ratio)
        long_edge, short_edge = max(scaled_w, scaled_h), min(scaled_w, scaled_h)
    if short_edge > max_short_edge:
        ratio = max_short_edge / short_edge
        scaled_w, scaled_h = int(scaled_w * ratio), int(scaled_h * ratio)
    return max(2, scaled_w - scaled_w % 2), max(2, scaled_h - scaled_h % 2)


def probe_encoder(
    ffmpeg: Path,
    encoder: str,
    width: int,
    height: int,
    timeout: float = 120.0,
) -> tuple[bool, str]:
    """Encode one synthetic frame with *encoder*; the process exit code decides."""
    command = [
        str(ffmpeg),
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=size={width}x{height}:rate=1",
        "-frames:v",
        "1",
        "-c:v",
        encoder,
        "-f",
        "null",
        "-",
    ]
    try:
        result = _run(command, timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{encoder} probe failed to run: {exc}"
    if result.returncode == 0:
        return True, f"{encoder} available at {width}x{height}"
    lines = [line.strip() for line in (result.stderr or "").splitlines() if line.strip()]
    reason = next(
        (line for line in lines if encoder in line),
        lines[-1] if lines else f"{encoder} exited with code {result.returncode}",
    )
    return False, reason


def codec_encoder(codec: str) -> str:
    return CODEC_ENCODERS.get(codec, codec)


def capability_table(
    ffmpeg: Path,
    codecs: Iterable[str],
    width: int,
    height: int,
    timeout: float = 120.0,
) -> dict[str, tuple[bool, str]]:
    """Probe each codec's encoder once, at the size the job will actually use."""
    table: dict[str, tuple[bool, str]] = {}
    for codec in codecs:
        encoder = codec_encoder(codec)
        table[codec] = probe_encoder(ffmpeg, encoder, width, height, timeout)
    return table
