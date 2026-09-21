# dlss5-enhance

Run **NVIDIA DLSS 5 neural rendering** over your videos, on your own machine,
through ComfyUI — with one click or one command line.

DLSS 5 reconstructs material detail that a renderer or a video generator has to
leave out: skin, hair, fabric structure. This tool drives the
[ComfyUI-DLSS5-Enhancer](https://github.com/Blueforcer/ComfyUI-DLSS5-Enhancer)
node for you: it starts ComfyUI if needed, feeds it your video, follows the
render, writes the result where you asked, and hands the machine back.

It is an **orchestrator**, not a renderer: no NVIDIA, ReShade or RenoDX binary is
bundled or redistributed here.

```
Upscale x2 · 480x270 -> 960x540, audio kept
```

## What you need

- **Windows** with an **NVIDIA RTX 20-series or newer** and a current driver.
  The DLSS 5 worker is a native D3D12 process; it needs an interactive desktop
  session (not a service, not a remote shell).
- **ComfyUI** — if you do not have it, the first-run setup downloads the official
  Windows portable build for you (about 1.8 GB).
- About **6 GB of free disk space** for the whole chain.

Everything else (the node pack, its dependencies, the DLSS 5 runtime) is
downloaded on the first run, from its own project.

## Quick start

1. Download `DLSS5-Enhance-1.1.0.zip` from the
   [latest release](../../releases/latest)
   and unzip it wherever you like (the folder is portable).
2. Run `DLSS5-Enhance.exe` — no argument opens the interface.
3. On the first run, open **Setup…**:
   - it lists what is present and what is missing (GPU, ComfyUI, node pack,
     runtime, ffmpeg, disk space);
   - it points at an existing ComfyUI if it finds one, or lets you browse to it,
     or downloads the portable build;
   - it installs the node pack and its dependencies;
   - it shows the **third-party licence notice** of the DLSS 5 runtime before
     downloading it (about 467 MB) — nothing is downloaded before you accept;
   - it ends with a **self test**: a one-second clip is rendered, which proves
     the whole chain works.
4. Pick a preset, pick your video (or a folder), pick the output folder, press
   **Run**.

The first render starts ComfyUI, which takes about 30 seconds; the next ones
reuse it.

## Presets

| Preset | Upscaling | Notes |
|---|---|---|
| `ameliore` — *Enhance (1x)* | `1x (DLAA / native)` | cleans the render at its own resolution |
| `ameliore_plus` — *Enhance+ (1x)* | `1x (DLAA / native)` | same, with `local_structure_strength: 2.0` |
| `x15` — *Upscale x1.5* | `1.5x (Quality)` | |
| `x2` — *Upscale x2* | `2x (Performance)` | |
| `x3` — *Upscale x3* | `3x (Ultra Performance)` | |

All five encode in HEVC/MKV at quality *Best*, and all of them are just entries
in `config.yaml`:

```yaml
presets:
  x2:
    label: Upscale x2
    upscaling_mode: 2x (Performance)   # or 2, or "2x"
    quality: Best
    codec: h265
    container: mkv
    settings:                          # optional, written into the DLSS5 Settings node
      local_structure_strength: 2.0
```

A preset writes its upscaling mode into the `DLSS5Settings` node of your
workflow and leaves everything else alone: your model preset, style, masking and
strength settings are respected.

**There is no 4x.** The node offers exactly `1x`, `1.5x`, `1.724x`, `2x`, `3x`.
The tool warns you before submitting when the geometry you ask for is beyond the
node's limits (long edge 7680, short edge 4320).

## Command line

The same executable is a scriptable CLI:

```bat
DLSS5-Enhance.exe --cli --preset x2 --folder D:\rushes --output D:\out
DLSS5-Enhance.exe --cli --preset ameliore video.mp4
DLSS5-Enhance.exe --cli --list-presets
DLSS5-Enhance.exe --cli --doctor
DLSS5-Enhance.exe --cli --setup
DLSS5-Enhance.exe --cli --lang fr --preset x3 video.mp4
```

| Option | Effect |
|---|---|
| `<file>` or `--folder <dir>` | exactly one source |
| `--preset <name>` | preset from `config.yaml` |
| `--list-presets` | list the presets and exit |
| `--output <dir>` | output folder (default: your Downloads folder) |
| `--quality` | `draft`\|`low` → Auto, `normal`\|`medium` → Good, `high` → Best, `max` → Max |
| `--codec` | `h264`, `h265`\|`hevc`, `av1`, `prores` |
| `--container` | `mp4`, `mkv`, `mov` (ProRes needs MOV or MKV) |
| `--max-frames <n>` | 0 renders the whole file |
| `--copy-audio` / `--no-copy-audio` | mux the source audio |
| `--verify-neural-rendering` / `--no-...` | fail when feature-18 execution cannot be proven |
| `--workflow <json>` | workflow exported in API format |
| `--extensions mp4,mkv` | extensions picked up in folder mode |
| `--timeout <s>` | per-file timeout (default 1200 s) |
| `--recursive` | walk `--folder` recursively |
| `--autostart` / `--no-autostart` | start ComfyUI when it is not listening |
| `--keep-server` | leave a ComfyUI server we started running |
| `--auto-restart` / `--no-auto-restart` | restart after a crash without asking |
| `--force` | force a fresh render (see *Cache*) |
| `--check` | validate everything, list the files, submit nothing |
| `--doctor` | report what is installed, change nothing |
| `--setup` | install what is missing |
| `--comfy-root <dir>` | point at an existing ComfyUI install |
| `--lang en\|fr` | interface language |
| `--config` / `--state` | alternate configuration / settings file |
| `--gui` / `--cli` | force the interface (default: GUI with no argument, CLI with) |
| `--verbose` / `--quiet` | DEBUG in the log file / errors only on the console |

Exit codes: `0` everything passed (cache hits count as success), `1` at least one
file failed, `2` bad invocation or configuration (nothing was submitted), `3`
infrastructure (server unreachable, port taken, tunnel detected), `130`
cancelled.

## Formats

**Input**: anything the bundled ffmpeg can decode — the source is not filtered by
the node. The extensions picked up in folder mode are configurable
(`processing.extensions`, or `--extensions`) and default to
`mp4, mov, mkv, webm`. A single file is always accepted; the tool only warns if
its extension is not in the list.

**Output**: there is no WebM output — the node writes `MP4`, `MKV` or `MOV`
(`--container`). A `.webm` source therefore comes out as `.mkv` by default.
Audio is stream-copied in MKV (Opus, AAC, Vorbis…) and re-encoded to AAC
192 kbit/s in MP4 and MOV; a source without an audio track stays silent.

WebM/VP8/VP9 sources carry no frame count in their metadata, so the node runs a
full ffprobe counting pass before rendering: the progress bar stays at 0 % a few
seconds longer. HDR sources are converted to 8-bit SDR without tone mapping.

## Cache

ComfyUI caches node results, and this node adds a fingerprint of the source file
(mtime + size): editing the source re-renders it, and an identical re-run may be
served from the cache.

The tool never trusts what ComfyUI says about it: it snapshots the output folder
**before** submitting and compares **after**. A file that appeared or changed
means a real render; otherwise it reports `CACHE-HIT` with the path of the older
file and tells you to use `--force`. A stale path is never presented as a fresh
render. If the cache is served but the file was deleted in the meantime, it says
so explicitly.

`--force` (or the *Force a new render* checkbox) injects a unique `is_changed`
value into the node, which invalidates the cache entry.

## Codecs on Ampere and older

`av1_nvenc` requires an Ada (RTX 40) or newer GPU; on Ampere the probe answers
`No capable devices found`. The DLSS5 node has **no software fallback for AV1**,
and it would only discover that at encoding time — after a full decode and
neural render. The tool therefore probes the encoder at the output size before
submitting and refuses `--codec av1` with exit code 2. H.264 and HEVC have
`libx264` / `libx265` fallbacks: if NVENC is missing (or the requested size
exceeds its maximum), the tool says so and the node encodes in software.

## Runtime notes

- The DLSS5 worker is a native **D3D12 + ReShade + NGX** process: run the tool
  from an **interactive Windows session** with GPU access. A service (session 0)
  or a remote shell has no usable desktop.
- The GPU is given to the worker: do not game or start a second render in
  parallel. A leftover worker (`nvngx.dll`) is reported in the log after a crash.
- If the configured port is held by an **SSH tunnel** to a remote ComfyUI, the
  tool refuses to use it (exit code 3): the node has to run locally. Point
  `comfy.port` at a free port instead.

## Configuration

Two files, next to the executable (or next to `dlss5_entry.py` when run from
source):

- **`config.yaml`** — defaults and presets, versioned, machine independent.
- **`settings.json`** — what was detected and chosen on *this* machine
  (ComfyUI paths, language, output folder, workflow, preset, last source).
  Created on demand; falls back to `%APPDATA%\dlss5-enhance\settings.json` if the
  application folder is read-only.

Precedence: command line > `settings.json` > `config.yaml` > built-in defaults.
Relative paths in `config.yaml` are resolved against the configuration file;
relative values in `settings.json` are resolved against the application folder,
which keeps the folder movable.

## Logs

- `logs/dlss5-enhance-YYYYMMDD.log` — timestamped INFO/ERROR, one line per job
  with its file name and `prompt_id`; the submitted prompt is written at DEBUG
  level (`--verbose`).
- `logs/comfyui-server-YYYYMMDD.log` — stdout/stderr of the ComfyUI server the
  tool started.

## Build from source

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m dlss5_enhance            :: GUI
.venv\Scripts\python.exe -m dlss5_enhance --doctor
build_exe.cmd                                        :: dist\DLSS5-Enhance.exe
```

Tests and lint:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -t .
ruff check .
```

The unit tests (translations, configuration precedence, preset resolution and
workflow injection, cache-hit detection, output probing, settings storage,
installation checks, GUI widgets) run **without a GPU and without ComfyUI**.

## Licence and credits

MIT — see [LICENSE](LICENSE).

This tool orchestrates other people's work and redistributes none of it:

- [ComfyUI](https://github.com/Comfy-Org/ComfyUI) (GPL-3.0) is downloaded by the
  first-run setup, or reused from your own installation.
- [ComfyUI-DLSS5-Enhancer](https://github.com/Blueforcer/ComfyUI-DLSS5-Enhancer)
  drives the renderer; its installer fetches the runtime below.
- The DLSS 5 runtime comes from
  [dlss5-visual-enhancer](https://github.com/Merserk/dlss5-visual-enhancer):
  `nvngx.dll` (upstream project), `nvngx_dlss.dll` and `nvngx_dlssnr.dll`
  (NVIDIA proprietary terms), `dxgi.dll` (ReShade, BSD-3-Clause),
  `renodx-dlss5.addon64` (RenoDX, its own terms), plus ffmpeg.
- The tool is not affiliated with NVIDIA, ReShade, RenoDX or the projects above.
  Install only components you are authorised to use, from sources their licences
  permit.

## Not covered

- No RunPod synchronisation, no folder watching, no scheduled task: the tool is
  started by hand and hands the machine back.
- No image processing: the targeted node handles video files.
- No 4x upscaling (the node stops at 3x).
- Your DLSS5 workflow itself (model preset, style, masking) is left as you
  exported it — only the job inputs and the upscaling mode are written.
