# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [1.3.1] - 2026-09-23

### Changed

- **The preset selector lives with the media.** Each of the *Video* and *Images*
  tabs now opens on a *Preset* block: the shipped presets as buttons, and
  *My presets*, a dropdown holding only the presets you created. The selection is
  shared, so picking one in a tab shows it in the other.
- **The *DLSS5 settings* tab keeps no preset list.** It holds only *Save as
  preset…* and *Delete preset*; the block is titled *Custom presets*.
- The `[custom]` suffix is gone: your presets are the dropdown's contents, so the
  buttons no longer need to mark them.
- Creating or deleting a preset is written to `settings.json` straight away, so
  the choice survives a restart.

### Fixed

- *Delete preset* is disabled while no preset of your own exists, and reports
  that only your own presets can be deleted when a shipped one is selected.

## [1.3.0] - 2026-09-23

### Added

- **Image support.** A second tab drives the `DLSS5EnhanceImages` node: its own
  queue, its own workflow, its own output folder. The source images are uploaded
  to ComfyUI's input folder, the results are fetched back and renamed
  `stem_YYYYMMDD-HHMMSS.ext`. The output format belongs to the workflow
  (`SaveImageAdvanced`: PNG, AVIF or EXR) and is shown, not chosen. Command line:
  `--images`, `--image-workflow`, `--image-format`, `--image-extensions`.
- **Create your own presets.** In the *DLSS5 settings* tab, *Save as preset…*
  stores the current sliders under a name of your choice; your presets live in
  `presets.yaml` next to the application and can be deleted from the interface.
- **ComfyUI is detected automatically.** No popup on the first run: the tool
  looks for an installed ComfyUI (portable build, desktop app, source checkout)
  and takes ffmpeg/ffprobe from the node pack it finds, so an installation that
  already works is reported as ready. *Setup…* is offered only when something
  really is missing.

### Changed

- The interface is now **tabbed**: *Video*, *Images*, *DLSS5 settings*. The
  settings tab is shared by both modes.
- The upscaling mode is a slider with a live readout of the resulting size, and
  every setting you change by hand is marked with a bullet so you can see what
  will be written into the workflow.

### Fixed

- The container/codec row was drawn on top of the other fields: each now has its
  own labelled line, and the *Advanced* toggle only hides and shows its own rows
  instead of overlapping the controls that were already there.
- The upscaling control now really moves the preset's slider (and the size
  readout) instead of leaving it untouched.
- The GUI worker thread no longer reads any Tk variable — including the *Force a
  new render* checkbox — which crashed a run with
  `main thread is not in main loop`.
- Deleting the preset that was currently selected no longer opens a blocking
  dialog: the run falls back to the workflow's own values and says so.

## [1.2.0] - 2026-09-23

### Added

- **Queue and drag & drop.** The GUI takes a list of files *and* folders:
  add them with the buttons or drop them from Explorer, remove what you do not
  want, and the list is remembered between sessions.
- **DLSS5 sliders.** Every meaningful setting of the node is now exposed —
  upscaling mode, DLSS model preset, local structure, skin detail, automatic
  mask, neural intensity, local tone, look, plus motion, scene-cut threshold and
  warm-up frames behind an *Advanced* toggle — with the same values available as
  command-line flags. Only the controls you touch are written into the workflow;
  *Read the workflow again* puts them back on your JSON's values.
- **Output format in the GUI**: container (MKV/MP4/MOV) and codec
(H.264/HEVC/AV1/ProRes Proxy), remembered like the rest.
- Presets `x2_plus` and `x3_plus`: upscaling **and** a stronger enhancement pass.
  `--enhance-strong` applies the same reinforcement to any preset.
- An application icon.

### Changed

- A port held by an SSH tunnel (or by any non-ComfyUI process) no longer stops
  the run: the tool looks for a local ComfyUI with the DLSS5 node on the fallback
  ports, otherwise it starts its own on the first free port, and remembers it.
  An already-open ComfyUI is still reused as before.
- Every child process (pip, 7zr, the node installer, ComfyUI, ffmpeg, nvidia-smi)
  is now started with its window hidden, and `dlss5-enhance.cmd` launches the
  interface through `pythonw.exe`: no console window at all.

### Fixed

- The GUI worker thread no longer touches Tk variables, which crashed any run
  with `main thread is not in main loop`.
- A preset's raw codec/container values (`h265`, `mkv`) are normalised before
  reaching the GUI's format boxes.

## [1.1.0] - 2026-09-21

### Added

- **First-run setup.** `--setup` (and the *Setup…* button in the GUI) checks the
  installation and installs what is missing: ComfyUI itself (official Windows
  portable build, SHA-256 verified), the DLSS5 node pack (fetched as a source
  archive, no git required), its Python dependencies, and the DLSS5 native
  runtime. `--doctor` reports the same checklist read-only.
- **Presets.** `--preset` and clickable presets in the GUI: `ameliore`,
  `ameliore_plus`, `x15`, `x2`, `x3`. They are declared in `config.yaml`, so
  adding one is a few lines of YAML.
- **Interface language.** English by default, French available (`--lang fr`, the
  GUI language selector, or `language:` in `config.yaml`). Every message comes
  from a translation catalogue.
- **Remembered settings.** `settings.json` keeps the language, the output
  folder, the workflow, the preset and the last source between runs. Paths
  inside the app folder are stored relative, so the folder can be moved.
- **WebM input** (`webm` is in the default watched extensions).

### Changed

- The output folder defaults to your **Downloads** folder instead of a path in
  the configuration file.
- The default workflow is the shipped example
  (`workflows/exemple_dlss5_video.json`), resolved relative to the application
  folder — so the tool works wherever it is unzipped.
- `config.yaml` is now a neutral template: no machine-specific path. What is
  detected on your machine lives in `settings.json`.
- The DLSS5 node pack, the DLSS5 runtime and ComfyUI are **not** bundled: they
  are downloaded on demand, from their own projects, under their own licences.

### Fixed

- The output probe now looks for the container's extensions (`mp4`, `mkv`,
  `mov`) instead of the watched source extensions, so a `.webm` source producing
  an `.mkv` is no longer reported as a failure.
- A port held by an SSH tunnel is reported as such instead of being mistaken for
  a local ComfyUI.
- `netstat` `TIME_WAIT` rows (PID 0) are no longer read as a process holding the
  port.
- The ComfyUI child process is started with `PYTHONIOENCODING=utf-8`: without it,
  one accented log line from a custom node killed the server on startup.

## [1.0.0] - 2026-09-20

### Added

- On-demand ComfyUI lifecycle: reuse a running server, start one if needed,
  stop the one it started.
- Sequential job processing, one prompt at a time, with WebSocket progress
  (`% frames`, ETA) and a `/history` polling fallback.
- Encoder capability probe before submitting, so an unsupported codec fails in
  a second instead of after a full render.
- Per-file timeout, crash detection with automatic restart, end-of-batch
  summary, timestamped log files.
- Cache-hit detection based on the output folder (a stale path is never
  reported as a fresh render), and `--force` to bypass the node's cache.
- Graphical interface: presets, file/folder picker, progress, live log, cancel,
  force checkbox.
- `dlss5-enhance.spec` and `build_exe.cmd` to build a single-file executable
  with PyInstaller.

[1.3.1]: ../../releases/tag/v1.3.1
[1.3.0]: ../../releases/tag/v1.3.0
[1.2.0]: ../../releases/tag/v1.2.0
[1.1.0]: ../../releases/tag/v1.1.0
[1.0.0]: ../../releases/tag/v1.0.0
