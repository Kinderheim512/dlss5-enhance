# dlss5-enhance 1.2.0

Run **NVIDIA DLSS 5 neural rendering** over your videos, on your own machine,
through ComfyUI — with one click or one command line.

## Download

- `DLSS5-Enhance-1.2.0.zip` — unzip it anywhere and run `DLSS5-Enhance.exe`.
  This is the recommended download: the folder is portable, `config.yaml` and the
  example workflow are included.
- `DLSS5-Enhance.exe` — the bare executable, if you already have the rest.

## What's new in 1.2.0

- **A queue, with drag & drop.** Drop your videos (or whole folders) on the list
  and press *Run*: they are processed one at a time, and the list is remembered
  between sessions.
- **Every DLSS5 setting, on sliders.** Upscaling mode, DLSS model preset, local
  structure, skin detail, automatic skin mask, neural intensity, local tone and
  look — plus motion vectors, scene-cut threshold and warm-up frames behind an
  *Advanced* toggle. Presets are shortcuts: picking one moves the sliders, then
  you adjust freely. **Only what you touch is written** into your workflow; the
  *Read the workflow again* button puts the controls back on your JSON's values.
- **Output format in the interface**: MKV / MP4 / MOV and H.264 / HEVC / AV1 /
  ProRes Proxy, remembered like everything else.
- **Upscale *and* enhance**: presets `x2_plus` and `x3_plus`, or `--enhance-strong`
  on top of any preset.
- **No console window.** The interface is launched through `pythonw.exe`, and
  every helper process runs hidden.
- **An already-open ComfyUI is reused**, and a port taken by an SSH tunnel or
  another application no longer blocks anything: the tool finds a local ComfyUI
  with the node, or starts its own on the next free port, and remembers it.

## First run

Open **Setup…** (or run `DLSS5-Enhance.exe --cli --doctor`). It lists what is
present and what is missing:

```
[OK]      NVIDIA GPU and driver — your card, your driver
[OK]      ComfyUI — reused if found, or browse to it
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
