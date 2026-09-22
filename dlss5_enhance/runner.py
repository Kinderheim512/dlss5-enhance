"""Orchestration: resolve sources, validate, submit one job at a time, report."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .comfy_client import ComfyClient
from .comfy_server import ComfyServer, ServerHandle
from .config import Config, TargetSelector
from .errors import ServerError, UsageError, WorkflowError
from .i18n import tr
from .mappings import (
    resolve_codec,
    resolve_container,
    resolve_quality,
    validate_codec_container,
)
from .media import (
    HARDWARE_CODECS,
    VideoInfo,
    codec_encoder,
    exceeds_limits,
    output_size,
    probe_encoder,
    probe_video,
)
from .outputs import (
    OUTPUT_EXTENSIONS,
    classify,
    probe_output,
    sanitize_prefix,
    snapshot_outputs,
)
from .presets import Preset
from .progress import (
    STATUS_CANCELLED,
    STATUS_CRASHED,
    STATUS_ERROR,
    STATUS_TIMEOUT,
    JobMonitor,
)
from .report import (
    STATUS_CACHE,
    STATUS_FAILED,
    STATUS_NEW,
    JobResult,
    exit_code,
    format_result_line,
    format_summary,
)
from .report import (
    STATUS_CANCELLED as REPORT_CANCELLED,
)
from .report import (
    STATUS_CRASHED as REPORT_CRASHED,
)
from .report import (
    STATUS_TIMEOUT as REPORT_TIMEOUT,
)
from .sink import Sink
from .workflow import (
    REQUIRED_INPUTS,
    build_prompt,
    load_workflow,
    missing_workflow_message,
    read_upscaling_mode,
    resolve_target,
)


def av1_message(reason: str) -> str:
    return tr("j.av1_unavailable", reason=reason)


@dataclass
class SourceItem:
    path: Path
    info: VideoInfo | None = None


class Orchestrator:
    def __init__(
        self,
        config: Config,
        logger,
        sink: Sink,
        force: bool = False,
        check_only: bool = False,
    ) -> None:
        self.config = config
        self.logger = logger
        self.sink = sink
        self.force = force
        self.check_only = check_only
        self.preset: Preset | None = config.preset
        self.client = ComfyClient(config.comfy.base_url)
        self.server = ComfyServer(config.comfy, self.client, logger)
        self.workflow: dict = {}
        self.target_id: str = ""
        self.output_dir: Path | None = None
        self._last_milestone = -1
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Ask the running batch to stop after interrupting the current job."""
        self._cancel.set()

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def run(self, sources: list[Path], folder_mode: bool) -> int:
        self._validate_environment()
        handle: ServerHandle | None = None
        started_by_us = False
        try:
            handle = self.server.ensure(self.config.run.autostart)
            started_by_us = handle.started_by_us
            self._validate_against_server()
            self._check_encoders(sources)
            self._warn_geometry_limits(sources)
            if self.check_only:
                self._print_plan(sources)
                return 0
            try:
                results = self._process_all(sources, handle, folder_mode)
            except KeyboardInterrupt:
                self.sink.clear()
                self.logger.warning(tr("j.interrupted"))
                self.client.interrupt()
                self.server.wait_queue_empty(timeout=30.0)
                raise
        finally:
            if started_by_us and not self.config.run.keep_server:
                self.server.stop(handle)
        for line in format_summary(results):
            self.logger.info("%s", line)
        return exit_code(results)

    def _validate_environment(self) -> None:
        processing = self.config.processing
        if not self.config.workflow.path.is_file():
            raise UsageError(missing_workflow_message(self.config.workflow.path))
        self.workflow = load_workflow(self.config.workflow.path)
        self.target_id = resolve_target(self.workflow, self.config.workflow.target)
        target = self.workflow[self.target_id]
        inputs = target.get("inputs") or {}
        missing = [key for key in REQUIRED_INPUTS if key not in inputs]
        if missing:
            raise WorkflowError(
                tr(
                    "j.target_inputs_missing",
                    node=self.target_id,
                    class_type=target.get("class_type"),
                    keys=", ".join(missing),
                    available=", ".join(sorted(inputs)),
                )
            )
        self.output_dir = processing.output or self.config.comfy.output_directory
        if self.output_dir is None:
            raise UsageError(tr("j.no_output_dir"))
        processing_resolved = (
            resolve_quality(processing.quality),
            resolve_codec(processing.codec),
            resolve_container(processing.container),
        )
        validate_codec_container(processing_resolved[1], processing_resolved[2])
        self._validate_preset()

    def _validate_preset(self) -> None:
        """Fail early when a preset targets a settings node the workflow lacks."""
        preset = self.preset
        if preset is None:
            return
        values = self._settings_values()
        if not values:
            return
        class_type = self.config.workflow.settings_class_type
        settings_id = resolve_target(self.workflow, TargetSelector(class_type=class_type))
        inputs = self.workflow[settings_id].get("inputs") or {}
        unknown = sorted(set(values) - set(inputs))
        if unknown:
            raise WorkflowError(
                tr(
                    "j.preset_unknown_input",
                    name=preset.name,
                    keys=", ".join(unknown),
                    class_type=class_type,
                    node=settings_id,
                    available=", ".join(sorted(inputs)),
                )
            )

    def _settings_values(self) -> dict | None:
        """The DLSS5 Settings inputs this run must override.

        Preset first, then the explicit settings (CLI or config), which win.
        """
        values: dict = {}
        if self.preset is not None:
            values.update(
                self.preset.settings_values(self.config.workflow.settings_upscaling_input)
            )
        values.update(self.config.settings_overrides)
        return values or None

    def _effective_factor(self) -> float:
        """Upscaling factor the job will really use: the preset wins over the workflow."""
        if self.preset is not None and self.preset.upscaling_mode:
            return self.preset.factor
        return read_upscaling_mode(
            self.workflow,
            self.config.workflow.settings_class_type,
            self.config.workflow.settings_upscaling_input,
        )

    def _validate_against_server(self) -> None:
        class_type = str(self.workflow[self.target_id].get("class_type") or "")
        if not class_type:
            return
        info = self.client.object_info(class_type)
        if info is None:
            raise ServerError(tr("j.node_not_loaded", class_type=class_type))

    def _check_encoders(self, sources: list[Path]) -> None:
        processing = self.config.processing
        codec = resolve_codec(processing.codec)
        ffmpeg = self.config.comfy.ffmpeg
        if ffmpeg is None or not Path(ffmpeg).is_file():
            self.logger.warning(tr("j.ffmpeg_missing"))
            return
        width, height = self._target_geometry(sources)
        available, reason = probe_encoder(Path(ffmpeg), codec_encoder(codec), width, height)
        if available:
            self.logger.info(
                tr(
                    "j.encoder_probe_ok",
                    encoder=codec_encoder(codec),
                    width=width,
                    height=height,
                )
            )
            return
        if codec == "AV1":
            raise UsageError(av1_message(reason))
        self.logger.warning(
            tr("j.encoder_fallback", encoder=codec_encoder(codec), reason=reason)
        )

    def _target_geometry(self, sources: list[Path]) -> tuple[int, int]:
        factor = self._effective_factor()
        width, height = self._source_geometry(sources)
        return output_size(width, height, factor)

    def _source_geometry(self, sources: list[Path]) -> tuple[int, int]:
        ffprobe = self.config.comfy.ffprobe
        if ffprobe is None or not Path(ffprobe).is_file() or not sources:
            return (1920, 1080)
        try:
            info = probe_video(Path(ffprobe), sources[0])
        except UsageError as exc:
            self.logger.warning(
                tr("j.ffprobe_unavailable", name=sources[0].name, error=exc)
            )
            return (1920, 1080)
        return (info.width or 1920, info.height or 1080)

    def _warn_geometry_limits(self, sources: list[Path]) -> None:
        """Tell the user when a preset asks for more pixels than the node accepts."""
        factor = self._effective_factor()
        width, height = self._source_geometry(sources)
        overflow = exceeds_limits(width, height, factor)
        if overflow is None:
            return
        message = tr(
            "j.geometry_overflow",
            factor=factor,
            width=width,
            height=height,
            target_w=overflow[0],
            target_h=overflow[1],
        )
        self.logger.warning("%s", message)
        self.sink.line(message)

    def _print_plan(self, sources: list[Path]) -> None:
        processing = self.config.processing
        codec = resolve_codec(processing.codec)
        container = resolve_container(processing.container)
        quality = resolve_quality(processing.quality)
        factor = self._effective_factor()
        width, height = self._target_geometry(sources)
        preset = self.preset
        self.sink.line(tr("j.plan_header"))
        self.sink.line(tr("j.plan_server", url=self.config.comfy.base_url))
        self.sink.line(
            tr(
                "j.plan_target",
                class_type=self.workflow[self.target_id].get("class_type"),
                node=self.target_id,
            )
        )
        self.sink.line(tr("j.plan_workflow", path=self.config.workflow.path))
        self.sink.line(
            tr(
                "j.plan_preset",
                label=(
                    f"{preset.label} ({preset.name})"
                    if preset is not None
                    else tr("j.plan_no_preset")
                ),
            )
        )
        if preset is not None and preset.settings:
            self.sink.line(
                tr(
                    "j.plan_settings",
                    settings=", ".join(
                        f"{k}={v}" for k, v in sorted(preset.settings.items())
                    ),
                )
            )
        self.sink.line(
            tr("j.plan_codec", codec=codec, container=container, quality=quality)
        )
        self.sink.line(
            tr("j.plan_upscaling", factor=factor, width=width, height=height)
        )
        self.sink.line(tr("j.plan_output", path=self.output_dir))
        self.sink.line(tr("j.plan_encoders", table=self._encoder_report(width, height)))
        applied = self._settings_values() or {}
        self.sink.line(
            tr(
                "j.plan_settings_applied",
                settings=(
                    ", ".join(f"{k}={v}" for k, v in sorted(applied.items()))
                    if applied
                    else tr("j.plan_settings_none")
                ),
            )
        )
        self.sink.line(tr("j.plan_files", count=len(sources)))
        ffprobe = self.config.comfy.ffprobe
        for source in sources:
            detail = ""
            if ffprobe is not None and Path(ffprobe).is_file():
                try:
                    info = probe_video(Path(ffprobe), source)
                    frames = f", {info.frames} frames" if info.frames else ""
                    detail = f" ({info.width}x{info.height}{frames})"
                except UsageError as exc:
                    detail = f"  [ffprobe: {exc}]"
            self.sink.line(tr("j.plan_file_line", name=source.name, detail=detail))

    def _encoder_report(self, width: int, height: int) -> str:
        ffmpeg = self.config.comfy.ffmpeg
        if ffmpeg is None or not Path(ffmpeg).is_file():
            return tr("j.encoder_probe_impossible")
        parts = []
        for codec in ("H.264", "HEVC", "AV1", "ProRes Proxy"):
            encoder = codec_encoder(codec)
            if codec in HARDWARE_CODECS:
                ok, reason = probe_encoder(Path(ffmpeg), encoder, width, height)
            else:
                ok, reason = True, tr("j.encoder_software")
            state = tr("j.encoder_ok") if ok else tr("j.encoder_unavailable")
            parts.append(f"{encoder} {state} ({reason})")
        return " | ".join(parts)

    def _process_all(
        self, sources: list[Path], handle: ServerHandle, folder_mode: bool
    ) -> list[JobResult]:
        results: list[JobResult] = []
        restarts = 0
        total = len(sources)
        for index, source in enumerate(sources, start=1):
            if self.cancelled():
                results.extend(self._abandon(sources[index - 1 :], tr("j.abandoned_cancelled")))
                break
            result = self._process_one(source, index, total, handle)
            results.append(result)
            if result.status == REPORT_CANCELLED:
                self.logger.warning(tr("j.cancel_batch", index=index, total=total))
                results.extend(self._abandon(sources[index:], tr("j.abandoned_cancelled")))
                break
            if result.status == REPORT_CRASHED:
                if not folder_mode or index == total:
                    self.logger.error(tr("j.server_gone_stop", index=index, total=total))
                    results.extend(self._abandon(sources[index:], tr("j.abandoned_server")))
                    break
                restarts += 1
                if restarts > self.config.processing.max_restarts:
                    self.logger.error(
                        tr("j.max_restarts", max=self.config.processing.max_restarts)
                    )
                    results.extend(self._abandon(sources[index:], tr("j.abandoned_restarts")))
                    break
                if not self._confirm_restart(index, total):
                    self.logger.error(tr("j.restart_refused"))
                    results.extend(self._abandon(sources[index:], tr("j.abandoned_refused")))
                    break
                handle = self._restart_server(handle)
            else:
                restarts = 0
        return results

    def _abandon(self, remaining: list[Path], reason: str) -> list[JobResult]:
        return [
            JobResult(source=source, status=STATUS_FAILED, reason=tr("j.abandoned", reason=reason))
            for source in remaining
        ]

    def _confirm_restart(self, index: int, total: int) -> bool:
        decision = self.config.run.auto_restart
        if decision is not None:
            self.logger.info(
                tr(
                    "j.restart_decision",
                    flag="--auto-restart" if decision else "--no-auto-restart",
                    remaining=total - index,
                )
            )
            return decision
        import sys

        if not sys.stdin or not sys.stdin.isatty():
            self.logger.warning(tr("j.restart_noninteractive"))
            return True
        try:
            answer = input(tr("j.restart_ask", remaining=total - index))
        except EOFError:
            return True
        return answer.strip().lower() not in {"n", "no", "non"}

    def _restart_server(self, handle: ServerHandle) -> ServerHandle:
        strays = self.server.stray_workers()
        if strays:
            self.logger.warning(tr("j.stray_workers", workers=", ".join(strays)))
        self.logger.info(tr("j.restarting"))
        self.server.stop(handle)
        time.sleep(1.0)
        return self.server.ensure(True)

    def _process_one(
        self, source: Path, index: int, total: int, handle: ServerHandle
    ) -> JobResult:
        processing = self.config.processing
        prefix = sanitize_prefix(source.stem)
        started = time.monotonic()
        self._last_milestone = -1
        self.logger.info(
            tr(
                "j.job_header",
                index=index,
                total=total,
                name=source.name,
                codec=resolve_codec(processing.codec),
                container=resolve_container(processing.container),
                quality=resolve_quality(processing.quality),
            )
        )

        snapshot = snapshot_outputs(self.output_dir, prefix, OUTPUT_EXTENSIONS)
        values = {
            "video_path": str(source.resolve()),
            "filename_prefix": prefix,
            "output_directory": str(Path(self.output_dir).resolve()),
            "codec": resolve_codec(processing.codec),
            "container": resolve_container(processing.container),
            "quality": resolve_quality(processing.quality),
            "max_frames": int(processing.max_frames),
            "copy_audio": bool(processing.copy_audio),
            "verify_neural_rendering": bool(processing.verify_neural_rendering),
        }
        token = uuid.uuid4().hex
        try:
            prompt = build_prompt(
                self.workflow,
                self.target_id,
                values,
                force=self.force,
                is_changed_token=token,
                settings_class_type=self.config.workflow.settings_class_type,
                settings_values=self._settings_values(),
            )
        except WorkflowError as exc:
            self.sink.clear()
            self.logger.error("%s : %s", source.name, exc)
            return JobResult(source=source, status=STATUS_FAILED, reason=str(exc))

        client_id = uuid.uuid4().hex
        self.logger.debug("Submitted prompt: %s", _dump(prompt))
        try:
            prompt_id = self.client.submit(prompt, client_id)
        except Exception as exc:
            self.sink.clear()
            self.logger.error(tr("j.submit_refused", name=source.name, error=exc))
            return JobResult(
                source=source,
                status=STATUS_FAILED,
                reason=tr("j.submit_refused_reason", error=exc),
                seconds=time.monotonic() - started,
            )
        self.logger.info(tr("j.prompt_submitted", name=source.name, prompt=prompt_id))

        monitor = JobMonitor(
            self.client,
            self.server.ws_url,
            prompt_id,
            client_id,
            self.target_id,
            self.logger,
        )
        outcome = monitor.run(
            timeout=processing.timeout,
            server_alive=self.server.is_process_alive,
            interrupt=self.client.interrupt,
            on_tick=self._tick(index, total, source.name),
            cancelled=self.cancelled,
        )
        self.sink.clear()
        elapsed = time.monotonic() - started

        if outcome.status == STATUS_CANCELLED:
            self.server.wait_queue_empty(timeout=30.0)
            self.logger.warning(tr("j.job_cancelled", name=source.name))
            return JobResult(
                source=source,
                status=REPORT_CANCELLED,
                reason=tr("t.status.cancelled"),
                seconds=elapsed,
            )
        if outcome.status == STATUS_CRASHED:
            tail = self.server.tail_log(30)
            self.logger.error(tr("j.server_disappeared", name=source.name))
            for line in tail:
                self.logger.error(tr("j.server_line", line=line))
            return JobResult(
                source=source,
                status=REPORT_CRASHED,
                reason=outcome.error,
                seconds=elapsed,
                details=tail,
            )
        if outcome.status == STATUS_TIMEOUT:
            self.server.wait_queue_empty(timeout=30.0)
            self.logger.error("%s : %s", source.name, outcome.error)
            return JobResult(
                source=source,
                status=REPORT_TIMEOUT,
                reason=outcome.error,
                seconds=elapsed,
            )
        if outcome.status == STATUS_ERROR:
            self.logger.error(tr("j.render_failed", name=source.name, error=outcome.error))
            return JobResult(
                source=source,
                status=STATUS_FAILED,
                reason=outcome.error,
                seconds=elapsed,
            )

        probe = probe_output(snapshot, self.output_dir, prefix, OUTPUT_EXTENSIONS)
        kind = classify(probe, outcome.cached_nodes, self.target_id)
        if kind == "missing":
            cached_signal = bool(
                self.target_id is not None and str(self.target_id) in outcome.cached_nodes
            )
            if cached_signal:
                reason = tr("j.no_output_cached", path=self.output_dir)
            else:
                reason = tr("j.no_output", path=self.output_dir)
            self.logger.error("%s : %s", source.name, reason)
            return JobResult(
                source=source,
                status=STATUS_FAILED,
                reason=reason,
                seconds=elapsed,
                details=[tr("j.ws_state", state=outcome.ws_connected)],
            )

        cached_signal = bool(
            self.target_id is not None and str(self.target_id) in outcome.cached_nodes
        )
        result = JobResult(
            source=source,
            status=STATUS_NEW if kind == "new" else STATUS_CACHE,
            output=probe.path,
            seconds=elapsed,
            cached_signal=cached_signal,
        )
        self.logger.info("%s", format_result_line(result))
        return result

    def _tick(self, index: int, total: int, name: str):
        def render(elapsed: float, done: int, frames_total: int, cached: bool) -> None:
            if frames_total:
                ratio = min(1.0, done / frames_total)
                remaining = (elapsed / done) * (frames_total - done) if done else 0.0
                text = (
                    f"[{index}/{total}] {name}  {ratio * 100:5.1f}%  "
                    f"{done}/{frames_total} frames  ETA {_clock(remaining)}"
                )
                milestone = int(ratio * 10)
                if self.sink.interactive:
                    self.sink.progress(text)
                elif milestone > self._last_milestone:
                    self._last_milestone = milestone
                    self.logger.info("%s", text)
                return
            if elapsed >= 5 and self.sink.interactive:
                self.sink.progress(
                    f"[{index}/{total}] {name}  {tr('j.tick_init')} {_clock(elapsed)}"
                )

        return render


def _clock(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    return f"{total // 60:02d}:{total % 60:02d}"


def _dump(prompt: dict) -> str:
    import json

    return json.dumps(prompt, ensure_ascii=False)
