# dlss5-enhance 1.3.0

Run **NVIDIA DLSS 5 neural rendering** over your videos *and your images*, on
your own machine, through ComfyUI — with one click or one command line.

## Download

- `DLSS5-Enhance-1.3.0.zip` — unzip it anywhere and run `DLSS5-Enhance.exe`.
  This is the recommended download: the folder is portable, `config.yaml` and the
  example workflows are included.
- `DLSS5-Enhance.exe` — the bare executable, if you already have the rest.

## What's new in 1.3.0

- **Images, not just videos.** A second tab drives the `DLSS5EnhanceImages`
  node: its own queue, its own workflow, its own output folder. Drop your
  pictures on it, press *Run*, and the enhanced files land next to your videos —
  renamed with a timestamp so a re-run never overwrites the previous one. The
  output format (PNG, AVIF or EXR) comes from the workflow's save node and is
  shown in the interface.
- **Your own presets.** Adjust the sliders, then *Save as preset…*: the settings
  are stored in `presets.yaml` next to the application, appear as a button beside
  the shipped presets, and can be deleted from the same place.
- **ComfyUI found on its own.** The first-run popup is gone: the tool looks for
  an installed ComfyUI, takes ffmpeg/ffprobe from the node pack it finds, and
  only asks for help when something is genuinely missing.
- **A tabbed interface** — *Video*, *Images*, *DLSS5 settings* — with an
  upscaling slider that shows the resulting size, and a bullet next to every
  setting you changed by hand.

### Fixed

- The container/codec row no longer overlaps the fields around it, and the
  *Advanced* toggle no longer draws text on top of existing controls.
- The upscaling control really moves the slider and the size readout.
- The worker thread no longer touches the interface from the background, which
  crashed some runs with `main thread is not in main loop`.

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
