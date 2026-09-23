"""Tkinter front-end: one tab per media kind, presets, DLSS5 sliders, live log."""

from __future__ import annotations

import contextlib
import os
import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__, doctor, installer, presets_store
from .app_paths import TOOL_ROOT, icon_path
from .comfy_client import ComfyError
from .config import Config, load_config
from .dlss5_settings import BY_NAME, SETTINGS, coerce_all, validate
from .errors import ServerError, UsageError, WorkflowError
from .i18n import LANGUAGE_LABELS, LANGUAGES, resolve_language, set_language, tr
from .logging_setup import setup_logging
from .mappings import CODECS, CONTAINERS, resolve_codec, resolve_container
from .media import output_size, probe_video
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
KINDS = ("video", "image")


class MediaTab:
    """Queue, destination and workflow for one media kind (video or images)."""

    def __init__(self, parent: ttk.Frame, app: App, kind: str) -> None:
        self.app = app
        self.kind = kind
        self.frame = parent
        self.queue: list[Path] = []
        self.queue_var = tk.StringVar(value="")
        self.size_var = tk.StringVar(value="")
        self.output_var = tk.StringVar()
        self.workflow_var = tk.StringVar()
        self.container_var = tk.StringVar()
        self.codec_var = tk.StringVar()
        self.dnd_ready = False
        self._build()

    # construction ----------------------------------------------------------
    def _build(self) -> None:
        queue_frame = ttk.LabelFrame(self.frame, padding=8)
        queue_frame.pack(fill="both", expand=True)
        self.app._t(queue_frame, f"u.section.queue.{self.kind}", "text")
        buttons = ttk.Frame(queue_frame)
        buttons.pack(fill="x")
        self.add_files_button = ttk.Button(buttons, command=self._pick_files)
        self.app._t(self.add_files_button, "u.add_files")
        self.add_files_button.pack(side="left")
        self.add_folder_button = ttk.Button(buttons, command=self._pick_folder)
        self.app._t(self.add_folder_button, "u.add_folder")
        self.add_folder_button.pack(side="left", padx=6)
        self.remove_button = ttk.Button(buttons, command=self._remove_selected)
        self.app._t(self.remove_button, "u.remove")
        self.remove_button.pack(side="left")
        self.clear_button = ttk.Button(buttons, command=self._clear_queue)
        self.app._t(self.clear_button, "u.clear")
        self.clear_button.pack(side="left", padx=6)

        list_row = ttk.Frame(queue_frame)
        list_row.pack(fill="both", expand=True, pady=(6, 0))
        self.queue_list = tk.Listbox(list_row, height=5, selectmode="extended")
        scroll = ttk.Scrollbar(list_row, orient="vertical", command=self.queue_list.yview)
        self.queue_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.queue_list.pack(side="left", fill="both", expand=True)
        self.drop_hint = ttk.Label(queue_frame, textvariable=self.queue_var, foreground="#555555")
        self.drop_hint.pack(fill="x", pady=(4, 0))
        if DND_AVAILABLE:
            try:
                self.queue_list.drop_target_register(DND_FILES)
                self.queue_list.dnd_bind("<<Drop>>", self._on_drop)
                self.dnd_ready = True
            except tk.TclError:
                self.dnd_ready = False

        paths = ttk.LabelFrame(self.frame, padding=8)
        paths.pack(fill="x", pady=6)
        self.app._t(paths, "u.section.paths", "text")
        paths.columnconfigure(1, weight=1)
        self.output_label = ttk.Label(paths)
        self.app._t(self.output_label, "u.output_label")
        self.output_label.grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(paths, textvariable=self.output_var).grid(
            row=0, column=1, sticky="ew", padx=6, pady=2
        )
        self.output_button = ttk.Button(paths, command=self._pick_output)
        self.app._t(self.output_button, "u.browse")
        self.output_button.grid(row=0, column=2, pady=2)
        self.workflow_label = ttk.Label(paths)
        self.app._t(self.workflow_label, "u.workflow_label")
        self.workflow_label.grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(paths, textvariable=self.workflow_var).grid(
            row=1, column=1, sticky="ew", padx=6, pady=2
        )
        self.workflow_button = ttk.Button(paths, command=self._pick_workflow)
        self.app._t(self.workflow_button, "u.browse")
        self.workflow_button.grid(row=1, column=2, pady=2)

        if self.kind == "video":
            self._build_video_format(paths)
        else:
            self._build_image_format(paths)

        self.size_label = ttk.Label(self.frame, textvariable=self.size_var, foreground="#333333")
        self.size_label.pack(fill="x", pady=(0, 4))

    def _build_video_format(self, parent: ttk.Frame) -> None:
        """Container and codec on their own line, each with its own label."""
        row = ttk.Frame(parent)
        row.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self.container_label = ttk.Label(row)
        self.app._t(self.container_label, "u.container")
        self.container_label.pack(side="left")
        self.container_box = ttk.Combobox(
            row,
            state="readonly",
            width=8,
            values=list(CONTAINERS),
            textvariable=self.container_var,
        )
        self.container_box.pack(side="left", padx=(6, 18))
        self.codec_label = ttk.Label(row)
        self.app._t(self.codec_label, "u.codec")
        self.codec_label.pack(side="left")
        self.codec_box = ttk.Combobox(
            row,
            state="readonly",
            width=14,
            values=list(CODECS),
            textvariable=self.codec_var,
        )
        self.codec_box.pack(side="left", padx=6)
        self.format_hint = ttk.Label(parent, foreground="#555555", wraplength=780, justify="left")
        self.app._t(self.format_hint, "u.format_hint")
        self.format_hint.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def _build_image_format(self, parent: ttk.Frame) -> None:
        """Images: the format belongs to the workflow, so it is shown, not chosen."""
        row = ttk.Frame(parent)
        row.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self.image_format_label = ttk.Label(row)
        self.app._t(self.image_format_label, "u.image_format")
        self.image_format_label.pack(side="left")
        self.image_format_value = ttk.Label(row, foreground="#333333")
        self.image_format_value.pack(side="left", padx=(6, 18))
        self.format_hint = ttk.Label(parent, foreground="#555555", wraplength=780, justify="left")
        self.app._t(self.format_hint, "u.image_format_hint")
        self.format_hint.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

    # queue -----------------------------------------------------------------
    def _add_paths(self, paths) -> None:
        for raw in paths:
            path = Path(str(raw))
            if not path.exists():
                self.app._append(tr("u.queue_missing", path=path), "WARNING")
                continue
            if any(existing == path for existing in self.queue):
                continue
            self.queue.append(path)
        self.refresh()
        self.app._save_state()

    def _refresh_queue_hint(self) -> None:
        if self.queue:
            self.queue_var.set(tr("u.queue_count", count=len(self.queue)))
        elif self.dnd_ready:
            self.queue_var.set(tr("u.queue_drop"))
        else:
            self.queue_var.set(tr("u.queue_empty"))

    def refresh(self) -> None:
        self.queue_list.delete(0, "end")
        for path in self.queue:
            self.queue_list.insert("end", str(path))
        self._refresh_queue_hint()
        self.refresh_size()

    def refresh_size(self) -> None:
        """Show what the current upscaling will produce for the first queued item."""
        if not self.queue:
            self.size_var.set("")
            return
        factor = self.app.upscaling_factor()
        info = probe_source(self.queue[0], self.app.config)
        if info is None:
            self.size_var.set(tr("u.size_unknown", factor=f"{factor:g}"))
            return
        width, height = output_size(info[0], info[1], factor)
        self.size_var.set(
            tr("u.size_line", src_w=info[0], src_h=info[1], out_w=width, out_h=height)
        )

    def _on_drop(self, event) -> None:
        raw = event.data
        try:
            paths = list(self.app.root.tk.splitlist(raw))
        except tk.TclError:
            paths = []
        if not any(Path(str(item)).exists() for item in paths):
            candidate = Path(str(raw).strip().strip("{}"))
            if candidate.exists():
                paths = [str(candidate)]
        self._add_paths(paths)

    def _remove_selected(self) -> None:
        for index in sorted(self.queue_list.curselection(), reverse=True):
            del self.queue[index]
        self.refresh()
        self.app._save_state()

    def _clear_queue(self) -> None:
        self.queue = []
        self.refresh()
        self.app._save_state()

    # pickers ---------------------------------------------------------------
    def _extensions(self) -> tuple[str, ...]:
        config = self.app.config
        if config is None:
            return ("mp4",)
        return (
            config.processing.extensions
            if self.kind == "video"
            else config.processing.image_extensions
        )

    def _pick_files(self) -> None:
        pattern = " ".join(f"*.{ext}" for ext in self._extensions())
        chosen = filedialog.askopenfilenames(
            title=tr("u.title.pick_file"),
            filetypes=[(tr("u.filetypes.videos"), pattern), (tr("u.filetypes.all"), "*.*")],
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
            self.app._save_state()

    def _pick_workflow(self) -> None:
        chosen = filedialog.askopenfilename(
            title=tr("u.title.pick_workflow"),
            filetypes=[(tr("u.filetypes.workflow"), "*.json"), (tr("u.filetypes.all"), "*.*")],
        )
        if chosen:
            self.workflow_var.set(chosen)
            self.app._reload_settings_from_workflow()
            self.refresh_format()
            self.app._save_state()

    # format ----------------------------------------------------------------
    def apply_preset_format(self, preset) -> None:
        if self.kind == "video":
            if preset.container:
                with contextlib.suppress(UsageError):
                    self.container_var.set(resolve_container(preset.container))
            if preset.codec:
                with contextlib.suppress(UsageError):
                    self.codec_var.set(resolve_codec(preset.codec))
        else:
            self.refresh_format()

    def refresh_format(self) -> None:
        """Read the image format from the workflow (it cannot be switched here)."""
        if self.kind != "image" or self.app.config is None:
            return
        path = self.workflow_var.get().strip()
        name = "png"
        if path and Path(path).is_file():
            with contextlib.suppress(WorkflowError, OSError):
                workflow = load_workflow(path)
                image = self.app.config.workflow.image
                if image is not None:
                    from .workflow import resolve_by_class_types

                    found = resolve_by_class_types(workflow, image.saver_class_types)
                    if found is not None:
                        inputs = (workflow.get(found[0]) or {}).get("inputs") or {}
                        value = inputs.get(image.saver_format_input)
                        if isinstance(value, (list, tuple)) and value:
                            name = str(value[0])
                        elif value:
                            name = str(value)
        self.image_format_value.configure(text=name)


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
        self.setup_dialog: SetupDialog | None = None
        self.setting_vars: dict[str, tk.Variable] = {}
        self.setting_dirty: set[str] = set()
        self.setting_rows: dict[str, list[tk.Widget]] = {}
        self.setting_labels: dict[str, ttk.Label] = {}

        self.settings, self.settings_file = load_settings(path=state_path, app_root=TOOL_ROOT)
        set_language(resolve_language(self.settings.language))

        self.preset_var = tk.StringVar()
        self.status_var = tk.StringVar(value=tr("u.ready"))
        self.mode_var = tk.StringVar(value="")
        self.banner_var = tk.StringVar(value="")
        self.language_var = tk.StringVar(
            value=LANGUAGE_LABELS[resolve_language(self.settings.language)]
        )
        self.force_var = tk.BooleanVar(value=False)
        self.advanced_var = tk.BooleanVar(value=False)
        self._texts: list[tuple[object, str, str]] = []
        self.tabs: dict[str, MediaTab] = {}
        self._after_ids: list[str] = []
        self._closing = False

        self._set_icon()
        self._build()
        self._load_config()
        self._schedule(POLL_MS, self._drain)
        self._schedule(300, self._check_installation)

    # plumbing ---------------------------------------------------------------
    def _schedule(self, delay: int, callback) -> str:
        """One place to register `after` callbacks, so they can be cancelled."""
        if self._closing:
            return ""
        identifier = self.root.after(delay, callback)
        self._after_ids.append(identifier)
        return identifier

    def shutdown(self) -> None:
        """Cancel pending callbacks; call it before destroying the window."""
        self._closing = True
        for identifier in self._after_ids:
            with contextlib.suppress(tk.TclError, ValueError):
                self.root.after_cancel(identifier)
        self._after_ids.clear()

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
        self.root.geometry("1040x940")
        self.root.minsize(900, 720)

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

        self.banner = ttk.Frame(self.root, padding=(10, 6))
        self.banner_label = ttk.Label(self.banner, textvariable=self.banner_var)
        self.banner_label.pack(side="left")
        self.banner_button = ttk.Button(self.banner, command=self._open_setup)
        self._t(self.banner_button, "u.banner_action")
        self.banner_button.pack(side="right")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=8)
        for kind in KINDS:
            frame = ttk.Frame(self.notebook, padding=8)
            self.notebook.add(frame, text=tr(f"u.tab.{kind}"))
            self.tabs[kind] = MediaTab(frame, self, kind)
        settings_frame = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(settings_frame, text=tr("u.tab.settings"))
        self._settings_frame = settings_frame
        self._build_settings_tab(settings_frame)
        self._build_actions()
        self._build_progress_and_log()

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        preset_frame = ttk.LabelFrame(parent, padding=8)
        preset_frame.pack(fill="x")
        self._t(preset_frame, "u.section.preset", "text")
        self.preset_row = ttk.Frame(preset_frame)
        self.preset_row.pack(fill="x")
        actions = ttk.Frame(preset_frame)
        actions.pack(fill="x", pady=(6, 0))
        self.save_preset_button = ttk.Button(actions, command=self._save_preset)
        self._t(self.save_preset_button, "u.save_preset")
        self.save_preset_button.pack(side="left")
        self.delete_preset_button = ttk.Button(actions, command=self._delete_preset)
        self._t(self.delete_preset_button, "u.delete_preset")
        self.delete_preset_button.pack(side="left", padx=6)

        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(6, 0))
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
            self.setting_rows[setting.name] = self._build_setting_row(body, setting, row)
        self._toggle_advanced()

    def _build_setting_row(self, parent: ttk.Frame, setting, row: int) -> list[tk.Widget]:
        widgets: list[tk.Widget] = []
        label = ttk.Label(parent, width=28, anchor="w")
        self._t(label, setting.label_key)
        label.grid(row=row, column=0, sticky="w", pady=3)
        self.setting_labels[setting.name] = label
        widgets.append(label)

        if setting.kind == "bool":
            var = tk.BooleanVar(value=bool(setting.default))
            check = ttk.Checkbutton(
                parent, variable=var, command=lambda name=setting.name: self._mark_dirty(name)
            )
            check.grid(row=row, column=1, sticky="w", pady=3)
            widgets.append(check)
        elif setting.kind == "combo" and setting.name != "upscaling_mode":
            var = tk.StringVar(value=str(setting.default))
            box = ttk.Combobox(parent, state="readonly", values=list(setting.options),
                               textvariable=var, width=24)
            box.grid(row=row, column=1, sticky="w", pady=3)
            box.bind(
                "<<ComboboxSelected>>",
                lambda _event, name=setting.name: self._mark_dirty(name),
            )
            widgets.append(box)
        elif setting.name == "upscaling_mode":
            var = tk.StringVar(value=str(setting.default))
            options = list(setting.options)
            index = tk.IntVar(value=0)
            scale = ttk.Scale(
                parent,
                from_=0,
                to=len(options) - 1,
                variable=index,
                orient="horizontal",
                command=lambda _value, name=setting.name, opts=options, var=var, idx=index: (
                    self._set_upscaling(var, idx, opts),
                    self._mark_dirty(name),
                ),
            )
            scale.grid(row=row, column=1, sticky="ew", pady=3)
            readout = ttk.Label(parent, width=26)
            readout.grid(row=row, column=2, sticky="w", padx=6)
            widgets.extend([scale, readout])
            self._upscaling_readout = readout
            self._upscaling_options = options
            self._upscaling_index = index
            readout.configure(text=options[0])
            self.setting_vars[setting.name] = var
            self._upscaling_var = var
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
                lambda *_args, v=var, widget=value_label: widget.configure(
                    text=f"{v.get():.2f}"
                ),
            )
            value_label.configure(text=f"{var.get():.2f}")

        hint = ttk.Label(parent, foreground="#555555", wraplength=520, justify="left")
        self._t(hint, setting.hint_key)
        hint.grid(row=row, column=3, sticky="w", padx=10, pady=3)
        widgets.append(hint)
        self.setting_vars.setdefault(setting.name, var)
        return widgets

    def _set_upscaling(self, var: tk.StringVar, index: tk.IntVar, options: list[str]) -> None:
        position = int(round(index.get()))
        position = max(0, min(len(options) - 1, position))
        var.set(options[position])
        readout = getattr(self, "_upscaling_readout", None)
        if readout is not None:
            readout.configure(text=options[position])
        for tab in self.tabs.values():
            tab.refresh_size()

    def _toggle_advanced(self) -> None:
        """Show or hide the advanced rows only, never their neighbours."""
        show = bool(self.advanced_var.get())
        for setting in SETTINGS:
            if not setting.advanced:
                continue
            for widget in self.setting_rows.get(setting.name, []):
                if show:
                    widget.grid()
                else:
                    widget.grid_remove()

    def _build_actions(self) -> None:
        actions = ttk.Frame(self.root)
        actions.pack(fill="x", padx=10, pady=(0, 6))
        self.run_button = ttk.Button(actions, command=lambda: self._start(self._current_kind()))
        self._t(self.run_button, "u.run")
        self.run_button.pack(side="left")
        self.check_button = ttk.Button(
            actions, command=lambda: self._start(self._current_kind(), check_only=True)
        )
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
        self.log = tk.Text(log_frame, height=12, wrap="none", state="disabled")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        for level, color in LEVEL_COLORS.items():
            self.log.tag_configure(level, foreground=color)

    def _current_kind(self) -> str:
        index = self.notebook.index(self.notebook.select())
        return KINDS[index] if index < len(KINDS) else "video"

    # configuration ---------------------------------------------------------
    def _load_config(self) -> None:
        try:
            self.config = load_config(path=self.config_path, settings=self.settings)
        except UsageError as exc:
            # a preset that disappeared must not block the window
            if self.settings.preset:
                self._append(tr("u.preset_gone", name=self.settings.preset), "WARNING")
                self.settings.preset = None
                with contextlib.suppress(UsageError):
                    self.config = load_config(
                        path=self.config_path, settings=self.settings
                    )
            if self.config is None:
                messagebox.showerror(tr("u.dlg.config_title"), str(exc))
                return
        self._fill_presets()
        video = self.tabs["video"]
        video.output_var.set(str(self.config.processing.output or ""))
        video.workflow_var.set(str(self.config.workflow.path))
        video.container_var.set(resolve_container(self.settings.container or "MKV"))
        video.codec_var.set(resolve_codec(self.settings.codec or "HEVC"))
        image = self.tabs["image"]
        stored_output = resolve_path(self.settings.image_output_dir, TOOL_ROOT)
        image.output_var.set(
            str(stored_output or self.config.processing.output or "")
        )
        stored_workflow = resolve_path(self.settings.image_workflow, TOOL_ROOT)
        if stored_workflow is not None and not stored_workflow.is_file():
            stored_workflow = None
        image.workflow_var.set(
            str(
                stored_workflow
                or (self.config.workflow.image.path if self.config.workflow.image else "")
            )
        )
        self._load_queues()
        self._reload_settings_from_workflow()

    def _load_queues(self) -> None:
        for kind in KINDS:
            stored = self.settings.sources if kind == "video" else self.settings.image_sources
            restored = [resolve_path(item, TOOL_ROOT) for item in stored]
            tab = self.tabs[kind]
            tab.queue = [path for path in restored if path is not None]
            tab.refresh()

    def _fill_presets(self) -> None:
        for child in self.preset_row.winfo_children():
            child.destroy()
        assert self.config is not None
        presets = self.config.presets
        if not presets:
            ttk.Label(self.preset_row, text=tr("u.preset_none")).pack(anchor="w")
            self.preset_var.set("")
            return
        user = presets_store.load_user_presets(presets_store.presets_path(self._config_dir()))
        wanted = self.settings.preset if self.settings.preset in presets else next(iter(presets))
        self.preset_var.set(wanted)
        for name, preset in presets.items():
            label = f"{preset.label} [custom]" if name in user else preset.label
            ttk.Radiobutton(
                self.preset_row,
                text=label,
                value=name,
                variable=self.preset_var,
                command=self._apply_preset,
            ).pack(side="left", padx=(0, 12))
        self._refresh_mode()

    def _config_dir(self) -> Path:
        if self.config is not None and self.config.config_path is not None:
            return Path(self.config.config_path).parent
        return TOOL_ROOT

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
        if preset.upscaling_mode:
            self._set_upscaling_var(preset.upscaling_mode)
            self._mark_dirty("upscaling_mode")
        for name, value in (preset.settings or {}).items():
            if name in self.setting_vars:
                self.setting_vars[name].set(value)
                self._mark_dirty(name)
        for tab in self.tabs.values():
            tab.apply_preset_format(preset)
        self._refresh_mode()
        self._save_state()

    def _set_upscaling_var(self, label: str) -> None:
        var = getattr(self, "_upscaling_var", None)
        index = getattr(self, "_upscaling_index", None)
        options = getattr(self, "_upscaling_options", None)
        if var is None or options is None:
            return
        if label not in options:
            return
        var.set(label)
        if index is not None:
            index.set(options.index(label))
        readout = getattr(self, "_upscaling_readout", None)
        if readout is not None:
            readout.configure(text=label)
        for tab in self.tabs.values():
            tab.refresh_size()

    def _mark_dirty(self, name: str) -> None:
        if name not in self.setting_vars:
            return
        self.setting_dirty.add(name)
        label = self.setting_labels.get(name)
        if label is not None:
            with contextlib.suppress(tk.TclError):
                label.configure(text=f"• {tr(BY_NAME[name].label_key)}")
        if name == "upscaling_mode":
            for tab in self.tabs.values():
                tab.refresh_size()

    def _reload_settings_from_workflow(self) -> None:
        """Fill the sliders with what the workflow really contains."""
        defaults = {setting.name: setting.default for setting in SETTINGS}
        values: dict = {}
        # the tab in front wins: it is applied last, the other one fills the gaps
        active = self._current_kind()
        order = [*[kind for kind in KINDS if kind != active], active]
        for kind in order:
            tab = self.tabs[kind]
            path = tab.workflow_var.get().strip()
            if not path or not Path(path).is_file():
                continue
            try:
                workflow = load_workflow(path)
                found = read_settings_values(
                    workflow,
                    self.config.workflow.settings_class_type if self.config else "DLSS5Settings",
                    [setting.name for setting in SETTINGS],
                )
            except WorkflowError:
                found = {}
            values.update(found)
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
        for name, label in self.setting_labels.items():
            with contextlib.suppress(tk.TclError):
                label.configure(text=tr(BY_NAME[name].label_key))
        self._sync_upscaling_index()

    def _sync_upscaling_index(self) -> None:
        var = getattr(self, "_upscaling_var", None)
        index = getattr(self, "_upscaling_index", None)
        options = getattr(self, "_upscaling_options", None)
        if var is None or index is None or options is None:
            return
        if var.get() in options:
            index.set(options.index(var.get()))
        readout = getattr(self, "_upscaling_readout", None)
        if readout is not None:
            readout.configure(text=var.get())
        for tab in self.tabs.values():
            tab.refresh_size()

    def upscaling_factor(self) -> float:
        from .presets import FACTORS

        name = getattr(self, "_upscaling_var", None)
        label = name.get() if name is not None else ""
        return FACTORS.get(label, 1.0)

    def _settings_overrides(self) -> dict:
        return coerce_all(
            {
                name: self.setting_vars[name].get()
                for name in self.setting_dirty
                if name in self.setting_vars
            }
        )

    # presets ---------------------------------------------------------------
    def _save_preset(self) -> None:
        name = simpledialog.askstring(tr("u.save_preset"), tr("u.preset_name"), parent=self.root)
        if not name or not name.strip():
            return
        self._save_preset_named(name)

    def _save_preset_named(self, name: str) -> None:
        """Store the current settings as a user preset (dialog-free core)."""
        key = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip().lower()).strip("_")
        if not key:
            messagebox.showwarning(tr("u.save_preset"), tr("u.preset_name_invalid"))
            return
        body: dict = {
            "label": name.strip(),
            "upscaling_mode": self.setting_vars["upscaling_mode"].get(),
        }
        for setting_name, value in self._settings_overrides().items():
            if setting_name == "upscaling_mode":
                continue
            body.setdefault("settings", {})[setting_name] = value
        video = self.tabs["video"]
        body["container"] = video.container_var.get()
        body["codec"] = video.codec_var.get()
        try:
            target = presets_store.save_user_preset(
                key, body, presets_store.presets_path(self._config_dir())
            )
        except OSError as exc:
            messagebox.showerror(tr("u.save_preset"), str(exc))
            return
        self._append(tr("u.preset_saved", name=key, path=target))
        self.settings.preset = key
        self._load_config()

    def _delete_preset(self) -> None:
        name = self.preset_var.get()
        if not presets_store.is_user_preset(
            name, presets_store.presets_path(self._config_dir())
        ):
            messagebox.showinfo(tr("u.delete_preset"), tr("u.preset_builtin"))
            return
        if not messagebox.askyesno(tr("u.delete_preset"), tr("u.preset_confirm", name=name)):
            return
        self._delete_preset_confirmed()

    def _delete_preset_confirmed(self) -> None:
        """Remove the selected user preset (dialog-free core)."""
        name = self.preset_var.get()
        presets_store.delete_user_preset(
            name, presets_store.presets_path(self._config_dir())
        )
        if self.settings.preset == name:
            self.settings.preset = None
        self._load_config()

    # state -----------------------------------------------------------------
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
        for index, kind in enumerate(KINDS):
            self.notebook.tab(index, text=tr(f"u.tab.{kind}"))
        self.notebook.tab(len(KINDS), text=tr("u.tab.settings"))
        self._fill_presets()
        for tab in self.tabs.values():
            tab.refresh()
        if self.config is not None:
            self.status_var.set(tr("u.ready"))

    def _save_state(self) -> None:
        self.settings.language = resolve_language(self.settings.language)
        video = self.tabs["video"]
        image = self.tabs["image"]
        self.settings.output_dir = store_path(video.output_var.get().strip(), TOOL_ROOT) or None
        self.settings.workflow = store_path(video.workflow_var.get().strip(), TOOL_ROOT) or None
        self.settings.image_output_dir = (
            store_path(image.output_var.get().strip(), TOOL_ROOT) or None
        )
        self.settings.image_workflow = (
            store_path(image.workflow_var.get().strip(), TOOL_ROOT) or None
        )
        self.settings.container = video.container_var.get() or None
        self.settings.codec = video.codec_var.get() or None
        self.settings.preset = self.preset_var.get() or None
        self.settings.sources = [
            store_path(str(path), TOOL_ROOT) or str(path) for path in video.queue
        ]
        self.settings.image_sources = [
            store_path(str(path), TOOL_ROOT) or str(path) for path in image.queue
        ]
        self.settings.settings = dict(self._settings_overrides())
        saved = save_settings(self.settings, path=self.state_path, app_root=TOOL_ROOT)
        if saved is not None:
            self.settings_file = saved

    def _open_output(self) -> None:
        tab = self.tabs[self._current_kind()]
        target = tab.output_var.get().strip()
        if target and Path(target).is_dir():
            os.startfile(target)

    # installation ----------------------------------------------------------
    def _check_installation(self) -> None:
        """Look for what is missing without blocking the interface."""
        if self.config is None:
            return
        threading.Thread(target=self._run_checks, name="dlss5-checks", daemon=True).start()

    def _run_checks(self) -> None:
        checks = doctor.run_checks(self.config) if self.config else []
        # never touch Tk from this thread: the main loop drains the queue
        self.messages.put(("checks", checks))

    def _on_checks(self, checks) -> None:
        self._show_banner([check for check in checks if not check.ok])
        if self.setup_dialog is not None:
            self.setup_dialog.show(checks)

    def _show_banner(self, missing: list) -> None:
        if not missing:
            self.banner.pack_forget()
            return
        self.banner_var.set(tr("u.banner", count=len(missing)))
        self.banner.configure(style="Banner.TFrame")
        self.banner.pack(fill="x", padx=10, pady=(8, 0), before=self.notebook)

    def _open_setup(self) -> None:
        if self.setup_dialog is not None:
            self.setup_dialog.window.lift()
            return
        self.setup_dialog = SetupDialog(self.root, self)

    # running ---------------------------------------------------------------
    def _start(self, kind: str, check_only: bool = False) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        tab = self.tabs[kind]
        if not tab.queue:
            messagebox.showwarning(tr("u.dlg.source_title"), tr("u.dlg.source_msg"))
            return
        output = tab.output_var.get().strip()
        if not output:
            messagebox.showwarning(tr("u.dlg.output_title"), tr("u.dlg.output_msg"))
            return
        workflow = tab.workflow_var.get().strip()
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
        if kind == "video":
            from .mappings import validate_codec_container

            try:
                validate_codec_container(tab.codec_var.get(), tab.container_var.get())
            except UsageError as exc:
                messagebox.showerror(tr("u.dlg.format_title"), str(exc))
                return

        self._save_state()
        self._set_running(True)
        self._clear_log()
        self.status_var.set(tr("u.verifying"))
        self.bar.configure(value=0)
        job = self._build_job(kind, check_only)
        self.worker = threading.Thread(
            target=self._work, args=(job,), name="dlss5-gui", daemon=True
        )
        self.worker.start()

    def _build_job(self, kind: str, check_only: bool = False) -> dict:
        """Snapshot the widgets into plain values: the worker must never read Tk."""
        tab = self.tabs[kind]
        return {
            "mode": kind,
            "paths": list(tab.queue),
            "output": tab.output_var.get().strip(),
            "workflow": tab.workflow_var.get().strip(),
            "container": tab.container_var.get(),
            "codec": tab.codec_var.get(),
            "preset": self.preset_var.get(),
            "settings": self._settings_overrides(),
            "check_only": bool(check_only),
            "force": bool(self.force_var.get()),
        }

    def _work(self, job: dict) -> None:
        """Runs off the main thread: only plain values, never a Tk widget."""
        sink = self.sink
        mode = str(job["mode"])
        check_only = bool(job["check_only"])
        try:
            processing: dict = {"output": job["output"]}
            if mode == "video":
                processing["container"] = job["container"]
                processing["codec"] = job["codec"]
            overrides: dict = {
                "processing": processing,
                "run": {"preset": job["preset"] or None},
            }
            if mode == "image":
                overrides["workflow"] = {"image": {"path": job["workflow"]}}
            elif job["workflow"]:
                overrides["workflow"] = {"path": job["workflow"]}
            if job["settings"]:
                overrides["dlss5_settings"] = dict(job["settings"])
            config = load_config(path=self.config_path, overrides=overrides, settings=self.settings)
            extensions = (
                config.processing.extensions
                if mode == "video"
                else config.processing.image_extensions
            )
            sources, problems = resolve_many(job["paths"], extensions)
            for problem in problems:
                sink.line(problem)
            if not sources:
                raise UsageError(tr("u.dlg.source_msg"))
            logger, log_path = setup_logging(
                config.log_dir, level=config.log_level, queue=self.messages
            )
            logger.info(tr("j.journal", path=log_path))
            logger.info(
                tr("j.mode_line", mode=tr(f"u.tab.{mode}"), count=len(sources))
            )
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
                force=bool(job["force"]),
                check_only=check_only,
                mode=mode,
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
                elif kind == "checks":
                    self._on_checks(payload)
        except queue.Empty:
            pass
        self._schedule(POLL_MS, self._drain)

    def _finish(self, code: int) -> None:
        self._set_running(False)
        if code == 0:
            self.bar.configure(value=100)
            self.status_var.set(tr("u.finished"))
        elif code == 130:
            self.status_var.set(tr("u.cancelled"))
        else:
            self.status_var.set(tr("u.finished_errors", code=code))
        self.open_button.configure(state="normal")

    def _on_close(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            if not messagebox.askyesno(tr("u.dlg.quit_title"), tr("u.dlg.quit_msg")):
                return
            self._cancel()
            self.worker.join(timeout=30)
        self._save_state()
        self.shutdown()
        self.root.destroy()


def probe_source(path: Path, config: Config | None) -> tuple[int, int] | None:
    """Width and height of a source file, using the node's ffprobe when available."""
    if config is None or config.comfy.ffprobe is None:
        return None
    ffprobe = Path(config.comfy.ffprobe)
    if not ffprobe.is_file() or not Path(path).is_file():
        return None
    try:
        info = probe_video(ffprobe, Path(path))
    except UsageError:
        return None
    return (info.width or 0, info.height or 0) if info.width else None


class SetupDialog:
    """Installation checklist plus the actions that fill the gaps."""

    def __init__(self, parent: tk.Tk, app: App) -> None:
        self.app = app
        self.window = tk.Toplevel(parent)
        self.window.title(tr("u.setup_button"))
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.geometry("880x640")
        self.window.transient(parent)
        self.accept_var = tk.BooleanVar(value=False)
        self.download_var = tk.BooleanVar(value=False)
        self.comfy_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="")
        self._build()
        self.refresh()

    def _build(self) -> None:
        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=tr("d.header")).pack(anchor="w")
        self.text = tk.Text(frame, height=9, wrap="word", state="disabled")
        self.text.pack(fill="x", pady=6)

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=tr("d.comfyui")).pack(side="left")
        ttk.Entry(row, textvariable=self.comfy_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text=tr("u.browse"), command=self._browse).pack(side="left")

        ttk.Checkbutton(
            frame, text=tr("d.allow_download"), variable=self.download_var
        ).pack(anchor="w", pady=(6, 0))
        ttk.Label(frame, text=tr("d.runtime_notice"), justify="left").pack(anchor="w", pady=(8, 2))
        ttk.Checkbutton(
            frame, text=tr("d.ask_accept_runtime").strip(), variable=self.accept_var
        ).pack(anchor="w")

        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=8)
        ttk.Button(actions, text=tr("u.check"), command=self.refresh).pack(side="left")
        ttk.Button(actions, text=tr("d.install"), command=self._install).pack(side="left", padx=6)
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
        if self.app.config is None:
            return
        self.status_var.set(tr("d.checking"))
        threading.Thread(target=self._checks, name="dlss5-setup-checks", daemon=True).start()

    def _checks(self) -> None:
        checks = doctor.run_checks(self.app.config) if self.app.config else []
        self.app.messages.put(("checks", checks))

    def show(self, checks) -> None:
        self._show_checks(checks)
        self.status_var.set("")

    def _install(self) -> None:
        if self.app.worker is not None and self.app.worker.is_alive():
            return
        app = self.app
        comfy_root = self.comfy_var.get().strip() or None
        accept = self.accept_var.get()
        download = self.download_var.get() or accept
        self.status_var.set(tr("d.installing"))

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
                    allow_download=download,
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
        self.app._check_installation()
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

