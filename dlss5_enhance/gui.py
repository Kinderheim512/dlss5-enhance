"""Tkinter front-end: a queue of files, presets, DLSS5 sliders, live log."""

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
from .app_paths import TOOL_ROOT, icon_path
from .comfy_client import ComfyError
from .config import Config, load_config
from .dlss5_settings import SETTINGS, coerce_all, validate
from .errors import ServerError, UsageError, WorkflowError
from .i18n import LANGUAGE_LABELS, LANGUAGES, resolve_language, set_language, tr
from .logging_setup import setup_logging
from .mappings import CODECS, CONTAINERS, resolve_codec, resolve_container
from .runner import Orchestrator
from .settings_store import load_settings, resolve_path, save_settings, store_path
from .sink import CLEAR, DONE, LINE, LOG, PROGRESS, STATUS, QueueSink
from .sources import resolve_many
from .workflow import load_workflow, missing_workflow_message, read_settings_values

try:  # native drag and drop; the window still works without it
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False
    DND_FILES = None
    TkinterDnD = None

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
        self.queue: list[Path] = []
        self.setting_vars: dict[str, tk.Variable] = {}
        self.setting_dirty: set[str] = set()
        self.setting_widgets: list[tk.Widget] = []

        self.settings, self.settings_file = load_settings(path=state_path, app_root=TOOL_ROOT)
        set_language(resolve_language(self.settings.language))

        self.preset_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.workflow_var = tk.StringVar()
        self.container_var = tk.StringVar(value=self.settings.container or "MKV")
        self.codec_var = tk.StringVar(value=self.settings.codec or "HEVC")
        self.status_var = tk.StringVar(value=tr("u.ready"))
        self.mode_var = tk.StringVar(value="")
        self.queue_var = tk.StringVar(value="")
        self.language_var = tk.StringVar(
            value=LANGUAGE_LABELS[resolve_language(self.settings.language)]
        )
        self.force_var = tk.BooleanVar(value=False)
        self.advanced_var = tk.BooleanVar(value=False)
        self._texts: list[tuple[object, str, str]] = []

        self._set_icon()
        self._build()
        self._load_config()
        self.root.after(POLL_MS, self._drain)
        self.root.after(400, self._maybe_first_run_setup)

    def _set_icon(self) -> None:
        icon = icon_path()
        if icon is None:
            return
        with contextlib.suppress(tk.TclError):
            self.root.iconbitmap(default=str(icon))

    def _t(self, widget, key: str, attr: str = "text") -> None:
        self._texts.append((widget, key, attr))
        if attr == "text":
            widget.configure(text=tr(key))
        else:
            widget.configure(**{attr: tr(key)})

    def _build(self) -> None:
        self.root.title(tr("u.title", version=__version__))
        self.root.geometry("1020x900")
        self.root.minsize(880, 700)

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

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=False, padx=10, pady=8)
        files_tab = ttk.Frame(self.tabs, padding=8)
        settings_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(files_tab, text=tr("u.tab.files"))
        self.tabs.add(settings_tab, text=tr("u.tab.settings"))
        self._files_tab = files_tab
        self._settings_tab = settings_tab
        self._build_files_tab(files_tab)
        self._build_settings_tab(settings_tab)
        self._build_actions()
        self._build_progress_and_log()

    def _build_files_tab(self, parent: ttk.Frame) -> None:
        self.preset_frame = ttk.LabelFrame(parent, padding=8)
        self.preset_frame.pack(fill="x")
        self._t(self.preset_frame, "u.section.preset", "text")
        self.preset_row = ttk.Frame(self.preset_frame)
        self.preset_row.pack(fill="x")

        queue_frame = ttk.LabelFrame(parent, padding=8)
        queue_frame.pack(fill="both", expand=True, pady=6)
        self._t(queue_frame, "u.section.queue", "text")
        buttons = ttk.Frame(queue_frame)
        buttons.pack(fill="x")
        self.add_files_button = ttk.Button(buttons, command=self._pick_files)
        self._t(self.add_files_button, "u.add_files")
        self.add_files_button.pack(side="left")
        self.add_folder_button = ttk.Button(buttons, command=self._pick_folder)
        self._t(self.add_folder_button, "u.add_folder")
        self.add_folder_button.pack(side="left", padx=6)
        self.remove_button = ttk.Button(buttons, command=self._remove_selected)
        self._t(self.remove_button, "u.remove")
        self.remove_button.pack(side="left")
        self.clear_button = ttk.Button(buttons, command=self._clear_queue)
        self._t(self.clear_button, "u.clear")
        self.clear_button.pack(side="left", padx=6)

        list_row = ttk.Frame(queue_frame)
        list_row.pack(fill="both", expand=True, pady=(6, 0))
        self.queue_list = tk.Listbox(list_row, height=6, selectmode="extended")
        queue_scroll = ttk.Scrollbar(list_row, orient="vertical", command=self.queue_list.yview)
        self.queue_list.configure(yscrollcommand=queue_scroll.set)
        queue_scroll.pack(side="right", fill="y")
        self.queue_list.pack(side="left", fill="both", expand=True)
        self.drop_hint = ttk.Label(queue_frame, textvariable=self.queue_var, foreground="#555555")
        self.drop_hint.pack(fill="x", pady=(4, 0))
        self.dnd_ready = False
        if DND_AVAILABLE:
            try:
                self.queue_list.drop_target_register(DND_FILES)
                self.queue_list.dnd_bind("<<Drop>>", self._on_drop)
                self.dnd_ready = True
            except tk.TclError:
                self.dnd_ready = False

        paths = ttk.LabelFrame(parent, padding=8)
        paths.pack(fill="x")
        self._t(paths, "u.section.paths", "text")
        paths.columnconfigure(1, weight=1)
        self.output_label = ttk.Label(paths)
        self._t(self.output_label, "u.output_label")
        self.output_label.grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(paths, textvariable=self.output_var).grid(
            row=0, column=1, sticky="ew", padx=6, pady=2
        )
        self.output_button = ttk.Button(paths, command=self._pick_output)
        self._t(self.output_button, "u.browse")
        self.output_button.grid(row=0, column=2, pady=2)
        self.workflow_label = ttk.Label(paths)
        self._t(self.workflow_label, "u.workflow_label")
        self.workflow_label.grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(paths, textvariable=self.workflow_var).grid(
            row=1, column=1, sticky="ew", padx=6, pady=2
        )
        self.workflow_button = ttk.Button(paths, command=self._pick_workflow)
        self._t(self.workflow_button, "u.browse")
        self.workflow_button.grid(row=1, column=2, pady=2)

        self.container_label = ttk.Label(paths)
        self._t(self.container_label, "u.container")
        self.container_label.grid(row=2, column=0, sticky="w", pady=2)
        self.container_box = ttk.Combobox(
            paths, state="readonly", width=10, values=list(CONTAINERS),
            textvariable=self.container_var,
        )
        self.container_box.grid(row=2, column=1, sticky="w", padx=6, pady=2)
        self.codec_box = ttk.Combobox(
            paths, state="readonly", width=16, values=list(CODECS), textvariable=self.codec_var
        )
        self.codec_box.grid(row=2, column=1, sticky="w", padx=(120, 0), pady=2)
        self.codec_label = ttk.Label(paths)
        self._t(self.codec_label, "u.codec")
        self.codec_label.grid(row=2, column=1, sticky="w", padx=(90, 0), pady=2)
        self.format_hint = ttk.Label(paths, foreground="#555555")
        self._t(self.format_hint, "u.format_hint")
        self.format_hint.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill="x")
        self.reload_button = ttk.Button(header, command=self._reload_settings_from_workflow)
        self._t(self.reload_button, "u.reload_settings")
        self.reload_button.pack(side="left")
        self.advanced_check = ttk.Checkbutton(
            header, variable=self.advanced_var, command=self._toggle_advanced
        )
        self._t(self.advanced_check, "u.advanced")
        self.advanced_check.pack(side="left", padx=12)
        self.settings_hint = ttk.Label(header, foreground="#555555")
        self._t(self.settings_hint, "u.settings_hint")
        self.settings_hint.pack(side="left")

        body = ttk.Frame(parent)
        body.pack(fill="both", expand=True, pady=6)
        body.columnconfigure(1, weight=1)
        for row, setting in enumerate(SETTINGS):
            self.setting_widgets.extend(self._build_setting_row(body, setting, row))
        self._toggle_advanced()

    def _build_setting_row(self, parent: ttk.Frame, setting, row: int) -> list[tk.Widget]:
        widgets: list[tk.Widget] = []
        label = ttk.Label(parent, width=26, anchor="w")
        self._t(label, setting.label_key)
        label.grid(row=row, column=0, sticky="w", pady=3)
        widgets.append(label)

        if setting.kind == "bool":
            var = tk.BooleanVar(value=bool(setting.default))
            check = ttk.Checkbutton(
                parent, variable=var, command=lambda name=setting.name: self._mark_dirty(name)
            )
            check.grid(row=row, column=1, sticky="w", pady=3)
            widgets.append(check)
        elif setting.kind == "combo":
            options = list(setting.options)
            var = tk.StringVar(value=str(setting.default))
            box = ttk.Combobox(parent, state="readonly", values=options, textvariable=var, width=24)
            box.grid(row=row, column=1, sticky="w", pady=3)
            box.bind(
                "<<ComboboxSelected>>",
                lambda _event, name=setting.name: self._mark_dirty(name),
            )
            widgets.append(box)
        else:
            var = tk.DoubleVar(value=float(setting.default))
            scale = ttk.Scale(
                parent,
                from_=float(setting.minimum or 0),
                to=float(setting.maximum or 1),
                variable=var,
                orient="horizontal",
                command=lambda _value, name=setting.name: self._mark_dirty(name),
            )
            scale.grid(row=row, column=1, sticky="ew", pady=3)
            value_label = ttk.Label(parent, width=6)
            value_label.grid(row=row, column=2, sticky="w", padx=6)
            widgets.extend([scale, value_label])
            var.trace_add(
                "write",
                lambda *_args, v=var, label=value_label: label.configure(
                    text=f"{v.get():.2f}"
                ),
            )
            value_label.configure(text=f"{var.get():.2f}")

        hint = ttk.Label(parent, foreground="#555555")
        self._t(hint, setting.hint_key)
        hint.grid(row=row, column=3, sticky="w", padx=10, pady=3)
        widgets.append(hint)
        self.setting_vars[setting.name] = var
        return widgets

    def _toggle_advanced(self) -> None:
        show = bool(self.advanced_var.get())
        for setting in SETTINGS:
            if not setting.advanced:
                continue
            for widget in self.setting_widgets:
                if widget in self._advanced_widgets(setting):
                    widget.grid() if show else widget.grid_remove()

    def _advanced_widgets(self, setting) -> list[tk.Widget]:
        found: list[tk.Widget] = []
        for widget in self.setting_widgets:
            with contextlib.suppress(tk.TclError):
                if tr(setting.label_key) in str(widget.cget("text") or ""):
                    found.append(widget)
        return found

    def _build_actions(self) -> None:
        actions = ttk.Frame(self.root)
        actions.pack(fill="x", padx=10, pady=(0, 6))
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

    def _build_progress_and_log(self) -> None:
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
        self.log = tk.Text(log_frame, height=14, wrap="none", state="disabled")
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
        self._load_queue()
        self._reload_settings_from_workflow()

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
                command=self._apply_preset,
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

    def _apply_preset(self) -> None:
        """A preset is a recipe: it moves the sliders and the format boxes."""
        preset = self.config.presets.get(self.preset_var.get()) if self.config else None
        if preset is None:
            return
        if preset.upscaling_mode and "upscaling_mode" in self.setting_vars:
            self.setting_vars["upscaling_mode"].set(preset.upscaling_mode)
            self._mark_dirty("upscaling_mode")
        for name, value in (preset.settings or {}).items():
            if name in self.setting_vars:
                self.setting_vars[name].set(value)
                self._mark_dirty(name)
        self._apply_preset_format(preset)
        self._refresh_mode()

    def _apply_preset_format(self, preset) -> None:
        """The format boxes show canonical values, never the preset's raw YAML."""
        if preset.container:
            with contextlib.suppress(UsageError):
                self.container_var.set(resolve_container(preset.container))
        if preset.codec:
            with contextlib.suppress(UsageError):
                self.codec_var.set(resolve_codec(preset.codec))

    def _mark_dirty(self, name: str) -> None:
        if name not in self.setting_vars:
            return
        self.setting_dirty.add(name)

    def _reload_settings_from_workflow(self) -> None:
        """Fill the sliders with what the workflow really contains."""
        defaults = {setting.name: setting.default for setting in SETTINGS}
        values: dict = {}
        path = self.workflow_var.get().strip()
        if path and Path(path).is_file():
            try:
                workflow = load_workflow(path)
                values = read_settings_values(
                    workflow,
                    self.config.workflow.settings_class_type if self.config else "DLSS5Settings",
                    [setting.name for setting in SETTINGS],
                )
            except WorkflowError:
                values = {}
        for setting in SETTINGS:
            var = self.setting_vars.get(setting.name)
            if var is None:
                continue
            raw = values.get(setting.name, defaults[setting.name])
            with contextlib.suppress(tk.TclError, ValueError):
                if setting.kind == "bool":
                    var.set(bool(raw))
                elif setting.kind == "combo":
                    var.set(str(raw))
                else:
                    var.set(float(raw))
        self.setting_dirty.clear()

    def _settings_overrides(self) -> dict:
        return coerce_all(
            {
                name: self.setting_vars[name].get()
                for name in self.setting_dirty
                if name in self.setting_vars
            }
        )

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
        self.tabs.tab(self._files_tab, text=tr("u.tab.files"))
        self.tabs.tab(self._settings_tab, text=tr("u.tab.settings"))
        self._fill_presets()
        self._refresh_queue_hint()
        if self.config is not None:
            self.status_var.set(tr("u.ready"))

    def _save_state(self) -> None:
        self.settings.language = resolve_language(self.settings.language)
        self.settings.output_dir = store_path(self.output_var.get().strip(), TOOL_ROOT) or None
        self.settings.workflow = store_path(self.workflow_var.get().strip(), TOOL_ROOT) or None
        self.settings.preset = self.preset_var.get() or None
        self.settings.container = self.container_var.get() or None
        self.settings.codec = self.codec_var.get() or None
        self.settings.sources = [
            store_path(str(path), TOOL_ROOT) or str(path) for path in self.queue
        ]
        self.settings.settings = dict(self._settings_overrides())
        saved = save_settings(self.settings, path=self.state_path, app_root=TOOL_ROOT)
        if saved is not None:
            self.settings_file = saved

    # queue -----------------------------------------------------------------
    def _load_queue(self) -> None:
        restored = [resolve_path(item, TOOL_ROOT) for item in self.settings.sources]
        self.queue = [path for path in restored if path is not None]
        self._refresh_queue()

    def _add_paths(self, paths) -> None:
        added = 0
        for raw in paths:
            path = Path(str(raw))
            if not path.exists():
                self._append(tr("u.queue_missing", path=path), "WARNING")
                continue
            if any(existing == path for existing in self.queue):
                continue
            self.queue.append(path)
            added += 1
        if added:
            self._refresh_queue()
            self._save_state()

    def _refresh_queue(self) -> None:
        self.queue_list.delete(0, "end")
        for path in self.queue:
            self.queue_list.insert("end", str(path))
        self._refresh_queue_hint()

    def _refresh_queue_hint(self) -> None:
        if self.queue:
            self.queue_var.set(tr("u.queue_count", count=len(self.queue)))
        elif self.dnd_ready:
            self.queue_var.set(tr("u.queue_drop"))
        else:
            self.queue_var.set(tr("u.queue_empty"))

    def _on_drop(self, event) -> None:
        """tkdnd hands over a Tcl list; a plain path is accepted too."""
        raw = event.data
        try:
            paths = list(self.root.tk.splitlist(raw))
        except tk.TclError:
            paths = []
        if not any(Path(str(item)).exists() for item in paths):
            candidate = Path(str(raw).strip().strip('{}'))
            if candidate.exists():
                paths = [str(candidate)]
        self._add_paths(paths)

    def _remove_selected(self) -> None:
        for index in sorted(self.queue_list.curselection(), reverse=True):
            del self.queue[index]
        self._refresh_queue()
        self._save_state()

    def _clear_queue(self) -> None:
        self.queue = []
        self._refresh_queue()
        self._save_state()

    # pickers ---------------------------------------------------------------
    def _pick_files(self) -> None:
        extensions = self.config.processing.extensions if self.config else ("mp4",)
        pattern = " ".join(f"*.{ext}" for ext in extensions)
        chosen = filedialog.askopenfilenames(
            title=tr("u.title.pick_file"),
            filetypes=[
                (tr("u.filetypes.videos"), pattern),
                (tr("u.filetypes.all"), "*.*"),
            ],
        )
        if chosen:
            self._add_paths(chosen)

    def _pick_folder(self) -> None:
        chosen = filedialog.askdirectory(title=tr("u.title.pick_folder"))
        if chosen:
            self._add_paths([chosen])

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
            self._reload_settings_from_workflow()

    def _open_output(self) -> None:
        if self.output_dir and Path(self.output_dir).is_dir():
            os.startfile(str(self.output_dir))

    # running ---------------------------------------------------------------
    def _check(self) -> None:
        self._start(check_only=True)

    def _start(self, check_only: bool = False) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        if not self.queue:
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
        try:
            validate(self._settings_overrides())
        except UsageError as exc:
            messagebox.showerror(tr("u.dlg.settings_title"), str(exc))
            return
        try:
            from .mappings import validate_codec_container

            validate_codec_container(self.codec_var.get(), self.container_var.get())
        except UsageError as exc:
            messagebox.showerror(tr("u.dlg.format_title"), str(exc))
            return

        self._save_state()
        self._set_running(True)
        self._clear_log()
        self.status_var.set(tr("u.verifying"))
        self.bar.configure(value=0)
        self.output_dir = Path(output)
        job = {
            "paths": list(self.queue),
            "output": output,
            "workflow": workflow,
            "container": self.container_var.get(),
            "codec": self.codec_var.get(),
            "preset": self.preset_var.get(),
            "settings": self._settings_overrides(),
            "check_only": check_only,
        }
        self.worker = threading.Thread(
            target=self._work,
            args=(job,),
            name="dlss5-gui",
            daemon=True,
        )
        self.worker.start()

    def _work(self, job: dict) -> None:
        """Runs off the main thread: only plain values, never a Tk widget."""
        sink = self.sink
        check_only = bool(job["check_only"])
        try:
            overrides: dict = {
                "processing": {
                    "output": job["output"],
                    "container": job["container"],
                    "codec": job["codec"],
                },
                "run": {"preset": job["preset"] or None},
            }
            if job["workflow"]:
                overrides["workflow"] = {"path": job["workflow"]}
            if job["settings"]:
                overrides["dlss5_settings"] = dict(job["settings"])
            config = load_config(
                path=self.config_path, overrides=overrides, settings=self.settings
            )
            sources, problems = resolve_many(job["paths"], config.processing.extensions)
            for problem in problems:
                sink.line(problem)
            if not sources:
                raise UsageError(tr("u.dlg.source_msg"))
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
                config=config, logger=logger, sink=sink, check_only=check_only
            )
            self.orchestrator = orchestrator
            code = orchestrator.run(sources, folder_mode=len(sources) > 1)
            if getattr(orchestrator.server, "port", None) not in (None, config.comfy.port):
                self.settings.comfy_port = int(orchestrator.server.port)
                save_settings(self.settings, path=self.state_path, app_root=TOOL_ROOT)
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

    def _open_setup(self) -> None:
        if self.setup_dialog is not None:
            self.setup_dialog.window.lift()
            return
        self.setup_dialog = SetupDialog(self.root, self)

    def _maybe_first_run_setup(self) -> None:
        """Open the setup screen when something is missing on this machine."""
        if self.config is None:
            return
        checks = doctor.run_checks(self.config)
        if not all(check.ok for check in checks):
            self._open_setup()

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
        self.window.geometry("860x600")
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


def make_root() -> tk.Tk:
    """A Tk root that knows about drag and drop when the module is present."""
    if DND_AVAILABLE:
        with contextlib.suppress(tk.TclError):
            return TkinterDnD.Tk()
    return tk.Tk()


def launch(config_path: str | Path | None = None, state_path: str | Path | None = None) -> int:
    root = make_root()
    with contextlib.suppress(tk.TclError):
        root.call("tk", "scaling", 1.25)
    app = App(root, config_path, state_path)
    root.protocol("WM_DELETE_WINDOW", app._on_close)
    root.mainloop()
    return 0


def install_everything(app_dir: Path, progress=None) -> Path:
    """Convenience for tests and scripts: fetch ComfyUI without the GUI."""
    return installer.install_comfyui(app_dir, progress)
