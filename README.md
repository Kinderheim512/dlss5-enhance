# dlss5-enhance

Run **NVIDIA DLSS 5 neural rendering** over your videos *and your images*, on
your own machine, through ComfyUI — with one click or one command line.

DLSS 5 reconstructs material detail that a renderer or a video generator has to
leave out: skin, hair, fabric structure. This tool drives the
[ComfyUI-DLSS5-Enhancer](https://github.com/Blueforcer/ComfyUI-DLSS5-Enhancer)
nodes for you: it starts ComfyUI if needed, feeds it your files, follows the
render, writes the results where you asked, and hands the machine back.

It is an **orchestrator**, not a renderer: no NVIDIA, ReShade or RenoDX binary is
bundled or redistributed here.

```
Video  · Upscale x2 · 480x270 -> 960x540, audio kept
Image  · Upscale x2 · 480x270 -> 960x540, written back as PNG
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

1. Download `DLSS5-Enhance-1.3.0.zip` from the
   [latest release](../../releases/latest)
   and unzip it wherever you like (the folder is portable).
2. Run `DLSS5-Enhance.exe` — no argument opens the interface.
3. ComfyUI is looked for **automatically** at startup, and its ffmpeg/ffprobe
   are taken from the node pack — an existing installation is recognised as
   ready, with no popup. If something really is missing, a banner appears: open
   **Setup…** and it
   - lists what is present and what is missing (GPU, ComfyUI, node pack,
     runtime, ffmpeg, disk space);
   - points at an existing ComfyUI if it finds one, or lets you browse to it,
     or downloads the portable build;
   - installs the node pack and its dependencies;
   - shows the **third-party licence notice** of the DLSS 5 runtime before
     downloading it (about 467 MB) — nothing is downloaded before you accept;
   - ends with a **self test**: a one-second clip is rendered, which proves the
     whole chain works.
4. Pick the **Video** or the **Images** tab, add your files to the **queue** (the
   *Add files…* / *Add a folder…* buttons, or just **drag and drop** them on the
   list), pick a preset, pick the output folder, press **Run**. Each tab keeps
   its own queue, and both are remembered between sessions.

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
| `x2_plus` — *Upscale x2 + Enhance* | `2x (Performance)` | upscaling **and** a stronger enhancement pass |
| `x3_plus` — *Upscale x3 + Enhance* | `3x (Ultra Performance)` | same, at 3x |

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

A preset is only a recipe: picking one **moves the sliders and the format boxes**
of the *DLSS5 settings* tab, and you can then adjust everything by hand.
**Only what you touch is written** into the workflow — the rest of your JSON is
left exactly as you exported it. The *Read the workflow again* button puts the
controls back on the values your workflow really contains.

**Your own presets.** Set the sliders the way you like and press *Save as
preset…*: the current values are stored under the name you type, in
`presets.yaml` next to the application (next to `config.yaml`). They then appear
as buttons beside the shipped ones, are picked by `--preset`, and can be deleted
with *Delete preset* (only your own — the ones in `config.yaml` are read-only).
`presets.yaml` is machine-specific and is never committed.

**There is no 4x.** The node offers exactly `1x`, `1.5x`, `1.724x`, `2x`, `3x`.
The tool warns you before submitting when the geometry you ask for is beyond the
node's limits (long edge 7680, short edge 4320).

## DLSS5 settings

The *DLSS5 settings* tab drives the node's own controls. Everything below is
also available on the command line, and a value out of range (or an impossible
combination) is refused **before** anything is submitted.

| Setting | Range (default) | What it really does |
|---|---|---|
| `upscaling_mode` | 1x DLAA · 1.5x · 1.724x · 2x · 3x (**1x**) | 1x cleans the render at its own resolution; the others clean **and** upscale |
| `dlss_model_preset` | Default / J / K / L / M (**M**) | the most important one: L and M rebuild markedly more skin and hair than Default/J/K |
| `local_structure_strength` | 0–2 (**1.5**) | local detail and structure reconstruction |
| `skin_structure_strength` | −1–2 (**2.0**) | pores and skin texture — only active while the mask is on |
| `automatic_mask` | on/off (**on**) | lets the model find what it treats as skin; unlocks the setting above |
| `nr_intensity` | 0–2 (**1.0**) | strength of the neural pass; clamped at 1.0, below it blends back to the source |
| `local_tone_strength` | 0–2 (**1.0**) | local tone mapping |
| `nr_style` | Default / Natural / Cinematic (**Default**) | Cinematic deepens shadows, Natural softens: it changes the look, not the amount |
| `motion` | auto / optical_flow / none (**auto**) | motion vectors for temporal accumulation (advanced) |
| `scene_change_threshold` | 0.01–1 (**0.24**) | luminance change above which the temporal history resets (advanced) |
| `warmup_frames` | 0–16 (**0**) | extra frames rendered before the first output settles (advanced) |
| `runtime_dir` | path (empty) | where the native runtime lives (advanced, set by the setup) |
| `nr_preset` | Default / #1–#3 (**Default**) | **inert** on current builds (bit-identical output) — not exposed |

`--enhance-strong` (or the same values written by hand) pushes structure, skin,
the mask and the model preset in one go — that is what `x2_plus` and `x3_plus`
are made of.

## Files and queue

- Each tab has its **own queue**: one for videos, one for images. The queue takes
  **files and folders**. A folder is expanded to the files it contains (the
  extensions the tab watches), in the order you added it; duplicates are ignored.
- **Drag and drop** works from Explorer (files or folders). If the optional
  `tkinterdnd2` module is missing, the buttons still work.
- A path that disappeared is reported when you drop it, and the whole queue is
  re-checked before a run: nothing is silently skipped.
- The batch runs **one file at a time** — the GPU is given to the DLSS5 worker.

## Images

The **Images** tab drives the `DLSS5EnhanceImages` node. It works like the video
tab — same queue, same presets, same DLSS5 sliders — with three differences:

- it uses its **own workflow** (`workflow.image.path`, default
  `workflows/exemple_dlss5_image.json`) and its **own output folder**
  (`settings.json` → `image_output_dir`), so images never land among your videos;
- the sources are **uploaded** to ComfyUI's input folder, then the results are
  fetched back and renamed `stem_YYYYMMDD-HHMMSS.ext` in your output folder (a
  re-run therefore never overwrites the previous file);
- the **output format belongs to the workflow**. The tab shows it; it is not
  chosen in the interface, because the save node's format sub-options only exist
  for the format it exports. Edit `SaveImageAdvanced` in your workflow to change
  it (PNG, AVIF or EXR).

The workflow you provide must contain a `DLSS5EnhanceImages` node (the injection
target), a `LoadImage` node feeding it, and a `SaveImageAdvanced` (or `SaveImage`)
node writing the result. Sources are never modified: the originals stay where
they are.

On the command line:

```bat
DLSS5-Enhance.exe --cli --preset x2 --images D:\photos --output D:\out
DLSS5-Enhance.exe --cli --preset x2 --images picture.png
```

## Output format

| | Choices | Notes |
|---|---|---|
| Container | **MKV**, **MP4**, **MOV** | there is no WebM output: the node writes only these three |
| Codec | **H.264**, **HEVC**, **AV1**, **ProRes Proxy** | AV1 needs an RTX 40+; ProRes needs MOV or MKV |
| Audio | — | MKV keeps the audio as it is (Opus, AAC, Vorbis…); MP4 and MOV re-encode to AAC 192 kbit/s and drop subtitles |

The extension of the result follows the container: a `.webm` source comes out as
`.mkv` unless you ask for something else.

This section is about **videos**. For images, the format is the workflow's save
node's (`SaveImageAdvanced`: PNG, AVIF or EXR) — see *Images* above.

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
| `--upscale <mode>` | 1x, 1.5x, 1.724x, 2x, 3x (or a bare factor) |
| `--model-preset <P>` | Default, J, K, L, M |
| `--structure <n>` | local structure strength (0 to 2) |
| `--skin <n>` | skin detail (−1 to 2, needs the mask) |
| `--mask` / `--no-mask` | automatic skin mask |
| `--intensity <n>` | neural intensity (0 to 2) |
| `--tone <n>` | local tone strength (0 to 2) |
| `--nr-style <S>` | Default, Natural, Cinematic |
| `--motion <M>` | auto, optical_flow, none |
| `--scene-threshold <n>` | 0.01 to 1.0 |
| `--warmup-frames <n>` | 0 to 16 |
| `--enhance-strong` | push structure, skin, mask and model preset on top of the preset |
| `--port <n>` | ComfyUI port (disables the fallback) |
| `--list-presets` | list the presets and exit |
| `--output <dir>` | output folder (default: your Downloads folder) |
| `--quality` | `draft`\|`low` → Auto, `normal`\|`medium` → Good, `high` → Best, `max` → Max |
| `--codec` | `h264`, `h265`\|`hevc`, `av1`, `prores` |
| `--container` | `mp4`, `mkv`, `mov` (ProRes needs MOV or MKV) |
| `--max-frames <n>` | 0 renders the whole file |
| `--copy-audio` / `--no-copy-audio` | mux the source audio |
| `--verify-neural-rendering` / `--no-...` | fail when feature-18 execution cannot be proven |
| `--workflow <json>` | workflow exported in API format (video) |
| `--images <path>` | run the image node on this file or folder instead of the video node |
| `--image-workflow <json>` | API workflow for the image node |
| `--image-format <fmt>` | expected image output format: `png`, `avif` or `exr` |
| `--image-extensions png,jpg` | extensions picked up in image folder mode |
| `--extensions mp4,mkv` | extensions picked up in video folder mode |
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
| `--download-comfyui` | let `--setup` download the portable ComfyUI (about 1.8 GB) without asking |
| `--accept-runtime` | accept the DLSS 5 runtime notice and download it during `--setup` |
| `--runtime-dir <dir>` | use an existing *DLSS 5 Visual Enhancer* runtime folder |
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
- **Another ComfyUI is already open?** It is reused: the tool never stops a server
  it did not start. If it finds one on the configured port, it checks that the
  DLSS5 node is loaded there and warns that the queue is shared and that the
  worker needs the GPU exclusively.
- **The configured port is taken by something else** (an SSH tunnel, another
  application)? The tool never talks to a remote ComfyUI, but it no longer gives
  up either: it looks for a local ComfyUI with the node on the fallback ports
  (`comfy.port_fallback`, default 8189/8199/8200), otherwise it starts its own on
  the first free port, and says so. The chosen port is remembered in
  `settings.json`, so the next run reuses that server.

## Configuration

Two files, next to the executable (or next to `dlss5_entry.py` when run from
source):

- **`config.yaml`** — defaults and presets, versioned, machine independent.
- **`settings.json`** — what was detected and chosen on *this* machine
  (ComfyUI paths, language, output folders, workflows, preset, last sources).
  Created on demand; falls back to `%APPDATA%\dlss5-enhance\settings.json` if the
  application folder is read-only.
- **`presets.yaml`** — the presets you created in the interface (*Save as
  preset…*), on top of the ones in `config.yaml`. Created on demand.

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

249 unit tests cover translations, configuration precedence, presets (shipped
and user-made) and the DLSS5 settings table, workflow injection, cache-hit
detection, output probing, the file queue, settings storage, port fallback,
source upload and result staging, image formats and the pre-flight plan, console
hiding, installation checks, ComfyUI detection and the GUI widgets. They run
**without a GPU and without ComfyUI**.

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
- No 4x upscaling (the node stops at 3x).
- The image output format is the workflow's save node's, not a dropdown: the
  node's format sub-options only exist for the format it exports.
- Your DLSS5 workflows themselves (model preset, style, masking) are left as you
  exported them — only the job inputs and the upscaling mode are written.
