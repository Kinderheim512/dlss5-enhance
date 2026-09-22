# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

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

[1.2.0]: ../../releases/tag/v1.2.0
[1.1.0]: ../../releases/tag/v1.1.0
[1.0.0]: ../../releases/tag/v1.0.0
