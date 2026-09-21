"""Per-job outcomes and the end-of-batch summary."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .i18n import tr

STATUS_NEW = "new"
STATUS_CACHE = "cache"
STATUS_FAILED = "failed"
STATUS_TIMEOUT = "timeout"
STATUS_CRASHED = "crashed"
STATUS_CANCELLED = "cancelled"

FAILURE_STATUSES = (STATUS_FAILED, STATUS_TIMEOUT, STATUS_CRASHED, STATUS_CANCELLED)

LABEL_KEYS = {
    STATUS_NEW: "t.status.new",
    STATUS_CACHE: "t.status.cache",
    STATUS_FAILED: "t.status.failed",
    STATUS_TIMEOUT: "t.status.timeout",
    STATUS_CRASHED: "t.status.crashed",
    STATUS_CANCELLED: "t.status.cancelled",
}


@dataclass
class JobResult:
    source: Path
    status: str
    output: Path | None = None
    reason: str = ""
    seconds: float = 0.0
    cached_signal: bool = False
    details: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in (STATUS_NEW, STATUS_CACHE)

    @property
    def failed(self) -> bool:
        return self.status in FAILURE_STATUSES


def label(status: str) -> str:
    key = LABEL_KEYS.get(status)
    return tr(key) if key else status


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    if total < 60:
        return tr("t.duration_s", seconds=total)
    minutes, rest = divmod(total, 60)
    if minutes < 60:
        return tr("t.duration_min", minutes=minutes, seconds=rest)
    hours, minutes = divmod(minutes, 60)
    return tr("t.duration_h", hours=hours, minutes=minutes)


def format_result_line(result: JobResult) -> str:
    if result.status == STATUS_NEW and result.output is not None:
        body = tr("t.new_render", path=result.output)
    elif result.status == STATUS_CACHE:
        if result.output is not None:
            body = tr("t.cache_hit", path=result.output)
        else:
            body = tr("t.cache_hit_nofile")
        if result.cached_signal:
            body += tr("t.ws_confirmed")
    else:
        text = label(result.status).upper()
        body = f"{text} — {result.reason}" if result.reason else text
    return tr(
        "t.line",
        name=result.source.name,
        body=body,
        duration=format_duration(result.seconds),
    )


def counts(results: Sequence[JobResult]) -> dict[str, int]:
    return {
        "total": len(results),
        "new": sum(1 for r in results if r.status == STATUS_NEW),
        "cache": sum(1 for r in results if r.status == STATUS_CACHE),
        "failed": sum(1 for r in results if r.failed),
    }


def format_summary(results: Sequence[JobResult]) -> list[str]:
    """End-of-batch summary: three counters, then the failure list."""
    stats = counts(results)
    lines = [
        tr("t.summary_header"),
        tr(
            "t.summary_counts",
            total=stats["total"],
            new=stats["new"],
            cache=stats["cache"],
            failed=stats["failed"],
        ),
    ]
    failures = [result for result in results if result.failed]
    if failures:
        lines.append(tr("t.summary_failures"))
        for result in failures:
            reason = result.reason or label(result.status)
            lines.append(tr("t.summary_failure_line", name=result.source.name, reason=reason))
    return lines


def exit_code(results: Sequence[JobResult]) -> int:
    if any(result.status == STATUS_CANCELLED for result in results):
        return 130
    return 1 if any(result.failed for result in results) else 0
