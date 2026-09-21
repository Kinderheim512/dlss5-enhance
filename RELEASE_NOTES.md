# dlss5-enhance 1.1.0

Run **NVIDIA DLSS 5 neural rendering** over your videos, on your own machine,
through ComfyUI — with one click or one command line.

## Download

- `DLSS5-Enhance-1.1.0.zip` — unzip it anywhere and run `DLSS5-Enhance.exe`.
  This is the recommended download: the folder is portable, `config.yaml` and the
  example workflow are included.
- `DLSS5-Enhance.exe` — the bare executable, if you already have the rest.

## First run

Open **Setup…** (or run `DLSS5-Enhance.exe --cli --doctor`). It lists what is
present and what is missing:

```
[OK]      NVIDIA GPU and driver — your card, your driver
[OK]      ComfyUI — D:\... (reused if found, or browse to it)
[MISSING] DLSS5 node pack — installed on demand from its repository
[MISSING] DLSS5 native runtime — about 467 MB, third-party binaries
[MISSING] ffmpeg / ffprobe — ships with the node's runtime
[OK]      Free disk space
```

**Setup…** fills the gaps: it downloads ComfyUI's official Windows portable
build if you do not have it (about 1.8 GB, SHA-256 verified), installs the node
pack (no git required), and shows the DLSS 5 runtime's licence notice before
downloading it. Nothing is downloaded before you accept. It finishes with a
self test: a one-second clip is rendered to prove the whole chain works.

## What's new

- **Presets**: `Enhance (1x)`, `Enhance+ (1x)`, `Upscale x1.5`, `x2`, `x3` —
  clickable in the GUI, `--preset <name>` on the command line, and declared in
  `config.yaml` so you can add your own in a few lines.
- **English by default, French available** (`--lang fr`, the language selector,
  or `language:` in `config.yaml`).
- **First-run setup** that installs ComfyUI, the node pack and the runtime on
  demand, plus `--doctor` for a read-only report.
- **Remembered settings**: language, output folder, workflow, preset and last
  source survive between runs (`settings.json`).
- Output defaults to your **Downloads** folder; the workflow defaults to the
  shipped example next to the application.
- **WebM input**; the output probe no longer mistakes an `.mkv` result for a
  failure when the source was a `.webm`.
- An **SSH tunnel** holding the configured port is detected and refused with a
  clear message instead of being used by mistake.

## Requirements

Windows, an NVIDIA RTX 20-series or newer with a current driver, and an
interactive desktop session (the DLSS 5 worker is a native D3D12 process). About
6 GB of free disk space for the whole chain.

## Notes

This tool orchestrates other projects and redistributes none of them: ComfyUI,
[ComfyUI-DLSS5-Enhancer](https://github.com/Blueforcer/ComfyUI-DLSS5-Enhancer)
and the DLSS 5 runtime are downloaded from their own repositories, under their
own licences. It is not affiliated with NVIDIA, ReShade or RenoDX. MIT licensed —
see the README for details.
