"""Tkinter front-end: pick a preset, run the batch, watch it live."""

from __future__ import annotations

import contextlib
import os
import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__, doctor, installer
from .app_paths import TOOL_ROOT
from .comfy_client import ComfyError
from .config import Config, load_config
from .errors import ServerError, UsageError, WorkflowError
from .i18n import LANGUAGE_LABELS, LANGUAGES, resolve_language, set_language, tr
from .logging_setup import setup_logging
from .runner import Orchestrator
from .settings_store import load_settings, save_settings, store_path
from .sink import CLEAR, DONE, LINE, LOG, PROGRESS, STATUS, QueueSink
from .sources import resolve_sources
from .workflow import missing_workflow_message

POLL_MS = 100
PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
LEVEL_COLORS = {"ERROR": "#b00020", "WARNING": "#a05a00", "DEBUG": "#666666"}


class App:
    def __init__(
        self,
        root: tk.Tk,
        config_path: str | Path | None = None,
        state_path: str | Path | None = None,
    ) -> None:
        self.root = root
        self.config_path = config_path
        self.state_path = state_path
        self.messages: queue.Queue = queue.Queue()
        self.sink = QueueSink(self.messages)
        self.orchestrator: Orchestrator | None = None
        self.worker: threading.Thread | None = None
        self.config: Config | None = None
        self.output_dir: Path | None = None
        self.setup_dialog: SetupDialog | None = None
        self.settings, self.settings_file = load_settings(path=state_path, app_root=TOOL_ROOT)
        set_language(resolve_language(self.settings.language))

        self.preset_var = tk.StringVar()
        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.workflow_var = tk.StringVar()
        self.status_var = tk.StringVar(value=tr("u.ready"))
        self.mode_var = tk.StringVar(value="")
        self.language_var = tk.StringVar(
            value=LANGUAGE_LABELS[resolve_language(self.settings.language)]
        )
        self.force_var = tk.BooleanVar(value=False)
        self._texts: list[tuple[object, str, str]] = []

        self._build()
        self._load_config()
        self.root.after(POLL_MS, self._drain)
        self.root.after(400, self._maybe_first_run_setup)

    def _t(self, widget, key: str, attr: str = "text") -> None:
        self._texts.append((widget, key, attr))
        if attr == "text":
            widget.configure(text=tr(key))
        else:
            widget.configure(**{attr: tr(key)})

    def _build(self) -> None:
        self.root.title(tr("u.title", version=__version__))
        self.root.geometry("980x760")
        self.root.minsize(860, 640)

        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=(10, 0))
        self.setup_button = ttk.Button(top, command=self._open_setup)
        self._t(self.setup_button, "u.setup_button")
        self.setup_button.pack(side="left")
        self.language_label = ttk.Label(top)
        self._t(self.language_label, "u.language")
        self.language_label.pack(side="right", padx=(0, 6))
        self.language_box = ttk.Combobox(
            top,
            state="readonly",
            width=10,
            values=[LANGUAGE_LABELS[code] for code in LANGUAGES],
            textvariable=self.language_var,
        )
        self.language_box.pack(side="right")
        self.language_box.bind("<<ComboboxSelected>>", self._on_language)

        self.preset_frame = ttk.LabelFrame(self.root, padding=8)
        self.preset_frame.pack(fill="x", padx=10, pady=(8, 6))
        self._t(self.preset_frame, "u.section.preset", "text")
        self.preset_row = ttk.Frame(self.preset_frame)
        self.preset_row.pack(fill="x")

        self.source_frame = ttk.LabelFrame(self.root, padding=8)
        self.source_frame.pack(fill="x", padx=10, pady=6)
        self._t(self.source_frame, "u.section.source", "text")
        row = ttk.Frame(self.source_frame)
        row.pack(fill="x")
        self.file_button = ttk.Button(row, command=self._pick_file)
        self._t(self.file_button, "u.pick_file")
        self.file_button.pack(side="left")
        self.folder_button = ttk.Button(row, command=self._pick_folder)
        self._t(self.folder_button, "u.pick_folder")
        self.folder_button.pack(side="left", padx=6)
        self.source_label = ttk.Label(self.source_frame, textvariable=self.source_var)
        self.source_label.pack(fill="x", pady=(6, 0))

        self.paths_frame = ttk.LabelFrame(self.root, padding=8)
        self.paths_frame.pack(fill="x", padx=10, pady=6)
        self._t(self.paths_frame, "u.section.paths", "text")
        self.paths_frame.columnconfigure(1, weight=1)
        self.output_label = ttk.Label(self.paths_frame)
        self._t(self.output_label, "u.output_label")
        self.output_label.grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(self.paths_frame, textvariable=self.output_var).grid(
            row=0, column=1, sticky="ew", padx=6, pady=2
        )
        self.output_button = ttk.Button(self.paths_frame, command=self._pick_output)
        self._t(self.output_button, "u.browse")
        self.output_button.grid(row=0, column=2, pady=2)
        self.workflow_label = ttk.Label(self.paths_frame)
        self._t(self.workflow_label, "u.workflow_label")
        self.workflow_label.grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(self.paths_frame, textvariable=self.workflow_var).grid(
            row=1, column=1, sticky="ew", padx=6, pady=2
        )
        self.workflow_button = ttk.Button(self.paths_frame, command=self._pick_workflow)
        self._t(self.workflow_button, "u.browse")
        self.workflow_button.grid(row=1, column=2, pady=2)

        actions = ttk.Frame(self.root)
        actions.pack(fill="x", padx=10, pady=6)
        self.run_button = ttk.Button(actions, command=self._start)
        self._t(self.run_button, "u.run")
        self.run_button.pack(side="left")
        self.check_button = ttk.Button(actions, command=self._check)
        self._t(self.check_button, "u.check")
        self.check_button.pack(side="left", padx=6)
        self.cancel_button = ttk.Button(actions, command=self._cancel, state="disabled")
        self._t(self.cancel_button, "u.cancel")
        self.cancel_button.pack(side="left")
        self.force_button = ttk.Checkbutton(actions, variable=self.force_var)
        self._t(self.force_button, "u.force")
        self.force_button.pack(side="left", padx=12)
        self.open_button = ttk.Button(actions, command=self._open_output, state="disabled")
        self._t(self.open_button, "u.open_output")
        self.open_button.pack(side="right")

        progress = ttk.LabelFrame(self.root, padding=8)
        progress.pack(fill="x", padx=10, pady=6)
        self._t(progress, "u.section.progress", "text")
        self.bar = ttk.Progressbar(progress, mode="determinate", maximum=100)
        self.bar.pack(fill="x")
        ttk.Label(progress, textvariable=self.mode_var).pack(fill="x", pady=(6, 0))
        ttk.Label(progress, textvariable=self.status_var).pack(fill="x", pady=(2, 0))

        log_frame = ttk.LabelFrame(self.root, padding=8)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        self._t(log_frame, "u.section.log", "text")
        self.log = tk.Text(log_frame, height=18, wrap="none", state="disabled")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        for level, color in LEVEL_COLORS.items():
            self.log.tag_configure(level, foreground=color)

    def _load_config(self) -> None:
        try:
            self.config = load_config(path=self.config_path, settings=self.settings)
        except UsageError as exc:
            messagebox.showerror(tr("u.dlg.config_title"), str(exc))
            return
        self._fill_presets()
        self.output_var.set(str(self.config.processing.output or ""))
        self.workflow_var.set(str(self.config.workflow.path))
        if self.settings.source:
            self.source_var.set(self.settings.source)

    def _fill_presets(self) -> None:
        for child in self.preset_row.winfo_children():
            child.destroy()
        assert self.config is not None
        presets = self.config.presets
        if not presets:
            ttk.Label(self.preset_row, text=tr("u.preset_none")).pack(anchor="w")
            self.preset_var.set("")
            return
        wanted = self.settings.preset if self.settings.preset in presets else next(iter(presets))
        self.preset_var.set(wanted)
        for name, preset in presets.items():
            ttk.Radiobutton(
                self.preset_row,
                text=preset.label,
                value=name,
                variable=self.preset_var,
                command=self._refresh_mode,
            ).pack(side="left", padx=(0, 12))
        self._refresh_mode()

    def _refresh_mode(self) -> None:
        if self.config is None:
            return
        preset = self.config.presets.get(self.preset_var.get())
        if preset is None:
            self.mode_var.set("")
            return
        detail = preset.upscaling_mode or tr("j.workflow_mode")
        if preset.settings:
            detail += " — " + ", ".join(f"{k}={v}" for k, v in sorted(preset.settings.items()))
        self.mode_var.set(tr("u.upscaling", mode=detail))

    def _on_language(self, _event=None) -> None:
        label = self.language_var.get()
        code = next((key for key, value in LANGUAGE_LABELS.items() if value == label), "en")
        set_language(code)
        self.settings.language = code
        self._retranslate()
        self._save_state()

    def _retranslate(self) -> None:
        self.root.title(tr("u.title", version=__version__))
        for widget, key, attr in self._texts:
            with contextlib.suppress(tk.TclError):
                if attr == "text":
                    widget.configure(text=tr(key))
                else:
                    widget.configure(**{attr: tr(key)})
        self._fill_presets()
        if self.config is not None:
            self.status_var.set(tr("u.ready"))

    def _save_state(self) -> None:
        self.settings.language = resolve_language(self.settings.language)
        self.settings.output_dir = store_path(self.output_var.get().strip(), TOOL_ROOT) or None
        self.settings.workflow = store_path(self.workflow_var.get().strip(), TOOL_ROOT) or None
        self.settings.preset = self.preset_var.get() or None
        source = self.source_var.get().strip()
        self.settings.source = source or None
        saved = save_settings(self.settings, path=self.state_path, app_root=TOOL_ROOT)
        if saved is not None:
            self.settings_file = saved

    def _pick_file(self) -> None:
        extensions = self.config.processing.extensions if self.config else ("mp4",)
        pattern = " ".join(f"*.{ext}" for ext in extensions)
        chosen = filedialog.askopenfilename(
            title=tr("u.title.pick_file"),
            filetypes=[
                (tr("u.filetypes.videos"), pattern),
                (tr("u.filetypes.all"), "*.*"),
            ],
        )
        if chosen:
            self.source_var.set(chosen)

    def _pick_folder(self) -> None:
        chosen = filedialog.askdirectory(title=tr("u.title.pick_folder"))
        if chosen:
            self.source_var.set(chosen)

    def _pick_output(self) -> None:
        chosen = filedialog.askdirectory(title=tr("u.title.pick_output"))
        if chosen:
            self.output_var.set(chosen)

    def _pick_workflow(self) -> None:
        chosen = filedialog.askopenfilename(
            title=tr("u.title.pick_workflow"),
            filetypes=[(tr("u.filetypes.workflow"), "*.json"), (tr("u.filetypes.all"), "*.*")],
        )
        if chosen:
            self.workflow_var.set(chosen)

    def _open_output(self) -> None:
        if self.output_dir and Path(self.output_dir).is_dir():
            os.startfile(str(self.output_dir))

    def _check(self) -> None:
        self._start(check_only=True)

    def _start(self, check_only: bool = False) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        source = self.source_var.get().strip()
        if not source:
            messagebox.showwarning(tr("u.dlg.source_title"), tr("u.dlg.source_msg"))
            return
        output = self.output_var.get().strip()
        if not output:
            messagebox.showwarning(tr("u.dlg.output_title"), tr("u.dlg.output_msg"))
            return
        workflow = self.workflow_var.get().strip()
        if not workflow:
            messagebox.showwarning(tr("u.dlg.workflow_title"), tr("u.dlg.workflow_msg"))
            return
        if not Path(workflow).is_file():
            messagebox.showerror(tr("u.dlg.workflow_title"), missing_workflow_message(workflow))
            return

        self._save_state()
        self._set_running(True)
        self._clear_log()
        self.status_var.set(tr("u.verifying"))
        self.bar.configure(value=0)
        self.output_dir = Path(output)
        self.worker = threading.Thread(
            target=self._work,
            args=(
                source,
                output,
                workflow,
                self.preset_var.get(),
                check_only,
                self.force_var.get(),
            ),
            name="dlss5-gui",
            daemon=True,
        )
        self.worker.start()

    def _work(
        self,
        source: str,
        output: str,
        workflow: str,
        preset: str,
        check_only: bool,
        force: bool,
    ) -> None:
        sink = self.sink
        try:
            overrides: dict = {
                "processing": {"output": output},
                "run": {"preset": preset or None},
            }
            if workflow:
                overrides["workflow"] = {"path": workflow}
            config = load_config(
                path=self.config_path,
                overrides=overrides,
                settings=self.settings,
            )
            is_folder = Path(source).is_dir()
            sources, folder_mode = resolve_sources(
                input_path=None if is_folder else source,
                folder=source if is_folder else None,
                extensions=config.processing.extensions,
                warn=lambda message: sink.line(message),
            )
            logger, log_path = setup_logging(
                config.log_dir, level=config.log_level, queue=self.messages
            )
            logger.info(tr("j.journal", path=log_path))
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
                config=config, logger=logger, sink=sink, force=force, check_only=check_only
            )
            self.orchestrator = orchestrator
            code = orchestrator.run(sources, folder_mode)
        except (UsageError, WorkflowError) as exc:
            self.messages.put((LOG, ("ERROR", tr("u.error", error=exc))))
            code = 2
        except (ServerError, ComfyError) as exc:
            self.messages.put((LOG, ("ERROR", tr("u.infra", error=exc))))
            code = 3
        except Exception as exc:
            self.messages.put((LOG, ("ERROR", tr("u.unexpected", error=repr(exc)))))
            code = 1
        finally:
            self.orchestrator = None
        self.sink.finished(code)

    def _cancel(self) -> None:
        orchestrator = self.orchestrator
        if orchestrator is not None:
            self.status_var.set(tr("u.cancelling"))
            orchestrator.cancel()
        else:
            self.status_var.set(tr("u.nothing_to_cancel"))

    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.run_button.configure(state=state)
        self.check_button.configure(state=state)
        self.cancel_button.configure(state="normal" if running else "disabled")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _append(self, text: str, level: str = "") -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", level if level in LEVEL_COLORS else "")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drain(self) -> None:
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == LINE:
                    self._append(str(payload))
                elif kind == LOG:
                    level, text = payload
                    self._append(f"{level:<7} {text}", level)
                elif kind == PROGRESS:
                    self.status_var.set(str(payload))
                    match = PERCENT.search(str(payload))
                    if match:
                        self.bar.configure(value=float(match.group(1).replace(",", ".")))
                elif kind == CLEAR:
                    pass
                elif kind == STATUS:
                    self.status_var.set(str(payload))
                elif kind == DONE:
                    self._finish(int(payload))
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self._drain)

    def _finish(self, code: int) -> None:
        self._set_running(False)
        if code == 0:
            self.bar.configure(value=100)
            self.status_var.set(tr("u.finished"))
        elif code == 130:
            self.status_var.set(tr("u.cancelled"))
        else:
            self.status_var.set(tr("u.finished_errors", code=code))
        if self.output_dir is not None:
            self.open_button.configure(state="normal")

    def _maybe_first_run_setup(self) -> None:
        """Open the setup screen when something is missing on this machine."""
        if self.config is None:
            return
        checks = doctor.run_checks(self.config)
        if not all(check.ok for check in checks):
            self._open_setup()

    def _open_setup(self) -> None:
        if self.setup_dialog is not None:
            self.setup_dialog.window.lift()
            return
        self.setup_dialog = SetupDialog(self.root, self)

    def _on_close(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            if not messagebox.askyesno(tr("u.dlg.quit_title"), tr("u.dlg.quit_msg")):
                return
            self._cancel()
            self.worker.join(timeout=30)
        self._save_state()
        self.root.destroy()


class SetupDialog:
    """Installation checklist plus the actions that fill the gaps."""

    def __init__(self, parent: tk.Tk, app: App) -> None:
        self.app = app
        self.window = tk.Toplevel(parent)
        self.window.title(tr("u.setup_button"))
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.geometry("820x560")
        self.window.transient(parent)
        self.accept_var = tk.BooleanVar(value=False)
        self.comfy_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="")
        self._build()
        self.refresh()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=tr("d.header")).pack(anchor="w")
        self.text = tk.Text(frame, height=10, wrap="word", state="disabled")
        self.text.pack(fill="x", pady=6)

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=tr("d.comfyui")).pack(side="left")
        ttk.Entry(row, textvariable=self.comfy_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text=tr("u.browse"), command=self._browse).pack(side="left")

        ttk.Label(frame, text=tr("d.runtime_notice"), justify="left").pack(anchor="w", pady=(8, 2))
        ttk.Checkbutton(
            frame,
            text=tr("d.ask_accept_runtime").strip(),
            variable=self.accept_var,
        ).pack(anchor="w")

        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=8)
        ttk.Button(actions, text=tr("u.check"), command=self.refresh).pack(side="left")
        ttk.Button(actions, text=tr("u.run"), command=self._install).pack(side="left", padx=6)
        ttk.Button(actions, text=tr("u.cancel"), command=self.close).pack(side="right")
        ttk.Label(frame, textvariable=self.status_var, justify="left").pack(anchor="w")

    def close(self) -> None:
        app = getattr(self, "app", None)
        if app is not None:
            app.setup_dialog = None
        self.window.destroy()

    def _browse(self) -> None:
        chosen = filedialog.askdirectory(title=tr("d.comfyui"))
        if chosen:
            self.comfy_var.set(chosen)

    def _show_checks(self, checks) -> None:
        lines = []
        for check in checks:
            status = tr(doctor.STATUS_KEYS[check.status])
            detail = f" — {check.detail}" if check.detail else ""
            lines.append(f"[{status}] {tr(check.key)}{detail}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "\n".join(lines))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        config = self.app.config
        if config is None:
            return
        self._show_checks(doctor.run_checks(config))

    def _install(self) -> None:
        if self.app.worker is not None and self.app.worker.is_alive():
            return
        app = self.app
        comfy_root = self.comfy_var.get().strip() or None
        accept = self.accept_var.get()
        self.status_var.set(tr("d.header"))
        app._set_running(True)

        def work() -> None:
            sink = app.sink
            try:
                settings = app.settings
                config = load_config(path=app.config_path, settings=settings)
                logger, log_path = setup_logging(
                    config.log_dir, level=config.log_level, queue=app.messages
                )
                logger.info(tr("j.journal", path=log_path))
                code = doctor.run_setup(
                    config,
                    logger,
                    sink,
                    settings=settings,
                    state_path=app.state_path,
                    comfy_root=comfy_root,
                    allow_download=accept,
                    accept_runtime=accept,
                )
            except Exception as exc:
                app.messages.put((LOG, ("ERROR", tr("u.unexpected", error=repr(exc)))))
                code = 1
            app.sink.finished(code)

        app.worker = threading.Thread(target=work, name="dlss5-setup", daemon=True)
        app.worker.start()
        self.window.after(500, self._poll)

    def _poll(self) -> None:
        if self.app.worker is not None and self.app.worker.is_alive():
            self.window.after(500, self._poll)
            return
        self.status_var.set(self.app.status_var.get())
        self.app._load_config()
        self.refresh()


def launch(config_path: str | Path | None = None, state_path: str | Path | None = None) -> int:
    root = tk.Tk()
    with contextlib.suppress(tk.TclError):
        root.call("tk", "scaling", 1.25)
    app = App(root, config_path, state_path)
    root.protocol("WM_DELETE_WINDOW", app._on_close)
    root.mainloop()
    return 0


def install_everything(app_dir: Path, progress=None) -> Path:
    """Convenience for tests and scripts: fetch ComfyUI without the GUI."""
    return installer.install_comfyui(app_dir, progress)
