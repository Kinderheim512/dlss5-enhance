"""Entry point: GUI when called with no argument, CLI otherwise."""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .app_paths import TOOL_ROOT
from .comfy_client import ComfyError
from .config import Config, load_config
from .errors import ServerError, UsageError, WorkflowError
from .i18n import LANGUAGES, resolve_language, set_language, tr
from .logging_setup import ProgressLine, setup_logging
from .mappings import normalize_extensions
from .presets import describe_presets
from .runner import Orchestrator
from .settings_store import load_settings
from .sink import ConsoleSink
from .sources import resolve_sources

EXIT_USAGE = 2
EXIT_INFRA = 3
EXIT_INTERRUPTED = 130

EPILOG = (
    "examples:\n"
    "  dlss5-enhance --preset x2 --folder D:\\rushes --output D:\\out\n"
    "  dlss5-enhance --preset ameliore video.mp4\n"
    "  dlss5-enhance --list-presets\n"
    "  dlss5-enhance --doctor\n"
    "\n"
    "Run with no argument to open the graphical interface."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dlss5-enhance",
        description=(
            "Enhance a video (or a folder of videos) through the ComfyUI DLSS5 node. "
            "ComfyUI is started on demand and stopped afterwards."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument("input", nargs="?", help="a single source video file")
    parser.add_argument("--folder", help="process every matching video in this folder")
    parser.add_argument("--preset", help="named preset from config.yaml (see --list-presets)")
    parser.add_argument(
        "--list-presets",
        action="store_true",
        dest="list_presets",
        help="list the presets declared in config.yaml and exit",
    )
    parser.add_argument("--output", help="output folder (default: your Downloads folder)")
    parser.add_argument("--quality", help="draft|low, normal|medium, high, max")
    parser.add_argument("--codec", help="h264, h265|hevc, av1, prores")
    parser.add_argument("--container", help="mp4, mkv, mov")
    parser.add_argument(
        "--max-frames", type=int, dest="max_frames", help="0 renders the whole file"
    )
    parser.add_argument(
        "--copy-audio",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="mux the source audio into the result",
    )
    parser.add_argument(
        "--verify-neural-rendering",
        action=argparse.BooleanOptionalAction,
        default=None,
        dest="verify_neural_rendering",
        help="fail the run when feature-18 execution cannot be proven",
    )
    parser.add_argument("--workflow", help="path to the API-format workflow JSON")
    parser.add_argument("--extensions", help="comma-separated list, default mp4,mov,mkv,webm")
    parser.add_argument("--timeout", type=float, help="per-file timeout in seconds")
    parser.add_argument("--recursive", action="store_true", help="walk --folder recursively")
    parser.add_argument(
        "--autostart",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="start ComfyUI when it is not already listening",
    )
    parser.add_argument(
        "--keep-server",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="leave a ComfyUI server we started running at the end",
    )
    parser.add_argument(
        "--auto-restart",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="restart ComfyUI after a crash without asking",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="force a fresh render (bypasses the node's source-fingerprint cache)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate everything and list the files, without submitting anything",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="report what is installed and what is missing, then exit",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="check the installation and download what is missing, then exit",
    )
    parser.add_argument("--comfy-root", dest="comfy_root", help="path to an existing ComfyUI")
    parser.add_argument(
        "--download-comfyui",
        action="store_true",
        dest="download_comfyui",
        help="allow --setup to download ComfyUI (about 1.8 GB) without asking",
    )
    parser.add_argument(
        "--accept-runtime",
        action="store_true",
        dest="accept_runtime",
        help="accept the DLSS5 runtime notice and download it during --setup",
    )
    parser.add_argument(
        "--runtime-dir",
        dest="runtime_dir",
        help="use an existing 'DLSS 5 Visual Enhancer' runtime folder",
    )
    parser.add_argument("--lang", choices=list(LANGUAGES), help="interface language (en, fr)")
    parser.add_argument("--config", help="config YAML path (default: config.yaml next to the tool)")
    parser.add_argument("--state", help="settings JSON path (default: next to the tool)")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="force the command-line interface (default with arguments)",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="open the graphical interface (default with no argument)",
    )
    parser.add_argument("--verbose", action="store_true", help="DEBUG level in the log file")
    parser.add_argument("--quiet", action="store_true", help="console shows errors only")
    parser.add_argument("--version", action="version", version=f"dlss5-enhance {__version__}")
    return parser


def overrides_from_args(args: argparse.Namespace) -> dict[str, Any]:
    output = str(Path(args.output).expanduser().resolve()) if args.output else None
    workflow = str(Path(args.workflow).expanduser().resolve()) if args.workflow else None
    processing = {
        "quality": args.quality,
        "codec": args.codec,
        "container": args.container,
        "max_frames": args.max_frames,
        "copy_audio": args.copy_audio,
        "verify_neural_rendering": args.verify_neural_rendering,
        "output": output,
        "extensions": list(normalize_extensions(args.extensions)) or None,
        "timeout": args.timeout,
    }
    run = {
        "autostart": args.autostart,
        "keep_server": args.keep_server,
        "auto_restart": args.auto_restart,
        "preset": args.preset,
    }
    overrides: dict[str, Any] = {
        "processing": {key: value for key, value in processing.items() if value is not None},
        "run": {key: value for key, value in run.items() if value is not None},
    }
    if workflow:
        overrides["workflow"] = {"path": workflow}
    if args.lang:
        overrides["language"] = args.lang
    return overrides


def resolve_sources_from_args(
    args: argparse.Namespace, config: Config
) -> tuple[list[Path], bool]:
    return resolve_sources(
        input_path=args.input,
        folder=args.folder,
        extensions=config.processing.extensions,
        recursive=args.recursive,
        warn=lambda message: print(message, file=sys.stderr),
    )


def _configure_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")


def run_cli(argv: Sequence[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings, settings_path = load_settings(path=args.state, app_root=TOOL_ROOT)
    set_language(resolve_language(args.lang, settings.language))

    try:
        config = load_config(
            path=args.config,
            overrides=overrides_from_args(args),
            settings=settings,
            app_root=TOOL_ROOT,
        )
    except UsageError as exc:
        print(tr("n.error", message=exc), file=sys.stderr)
        return EXIT_USAGE

    if not args.lang and not settings.language and config.language:
        set_language(config.language)

    progress = ProgressLine(enabled=not args.quiet)
    sink = ConsoleSink(progress)
    level = "DEBUG" if args.verbose else config.log_level
    logger, log_path = setup_logging(
        config.log_dir, level=level, progress=progress, quiet=args.quiet
    )

    if args.doctor or args.setup:
        from .doctor import report, run_setup

        if args.setup:
            return run_setup(
                config,
                logger,
                sink,
                settings=settings,
                state_path=settings_path,
                comfy_root=args.comfy_root,
                allow_download=args.download_comfyui,
                accept_runtime=args.accept_runtime,
                runtime_dir=args.runtime_dir,
            )
        return report(config, sink)

    if args.list_presets:
        for line in describe_presets(config.presets):
            sink.line(line)
        return 0

    try:
        sources, folder_mode = resolve_sources_from_args(args, config)
    except UsageError as exc:
        sink.clear()
        print(tr("n.error", message=exc), file=sys.stderr)
        return EXIT_USAGE

    logger.info(tr("j.journal", path=log_path))
    if config.config_path:
        logger.info(tr("j.configuration", path=config.config_path))
    if config.preset is not None:
        logger.info(
            tr(
                "j.preset_line",
                label=config.preset.label,
                name=config.preset.name,
                mode=config.preset.upscaling_mode or tr("j.workflow_mode"),
            )
        )

    orchestrator = Orchestrator(
        config=config,
        logger=logger,
        sink=sink,
        force=args.force,
        check_only=args.check,
    )
    try:
        return orchestrator.run(sources, folder_mode)
    except UsageError as exc:
        sink.clear()
        logger.error("%s", exc)
        return EXIT_USAGE
    except WorkflowError as exc:
        sink.clear()
        logger.error("%s", exc)
        return EXIT_USAGE
    except (ServerError, ComfyError) as exc:
        sink.clear()
        logger.error("%s", exc)
        return EXIT_INFRA
    except KeyboardInterrupt:
        sink.clear()
        logger.warning(tr("n.interrupted"))
        return EXIT_INTERRUPTED


def run_gui(config_path: str | None = None, state_path: str | None = None) -> int:
    from .gui import launch

    return launch(config_path, state_path)


def main(argv: Sequence[str] | None = None) -> int:
    _configure_streams()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or "--gui" in arguments:
        args, _ = build_parser().parse_known_args(arguments)
        return run_gui(args.config, args.state)
    return run_cli(arguments)


if __name__ == "__main__":
    sys.exit(main())
