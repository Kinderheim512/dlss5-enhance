# dlss5-enhance 1.3.1

Run **NVIDIA DLSS 5 neural rendering** over your videos *and your images*, on
your own machine, through ComfyUI — with one click or one command line.

## Download

- `DLSS5-Enhance-1.3.1.zip` — unzip it anywhere and run `DLSS5-Enhance.exe`.
  This is the recommended download: the folder is portable, `config.yaml` and the
  example workflows are included.
- `DLSS5-Enhance.exe` — the bare executable, if you already have the rest.

## What's new in 1.3.1

- **The preset selector moved to where you work.** Each of the *Video* and
  *Images* tabs now opens on a **Preset** block: the shipped presets as buttons,
  and *My presets*, a dropdown listing only the presets you created. Pick one in
  a tab and it shows in the other — it drives the same DLSS5 sliders.
- **The *DLSS5 settings* tab keeps no preset list.** It holds only *Save as
  preset…* and *Delete preset*, under *Custom presets*.
- **Creating a preset is immediate.** Name it, and it appears in the dropdown of
  both media tabs, selected and ready; the choice is written to `settings.json`
  straight away, so it comes back on the next launch.
- *Delete preset* is greyed out while you have not created any, and tells you
  that shipped presets are read-only if you ask for one of those.

## What's in 1.3.0

- **Images, not just videos.** A second tab drives the `DLSS5EnhanceImages`
  node: its own queue, its own workflow, its own output folder. Results are
  renamed with a timestamp so a re-run never overwrites the previous one; the
  output format (PNG, AVIF or EXR) comes from the workflow's save node.
- **ComfyUI found on its own**, with ffmpeg/ffprobe taken from the node pack: no
  first-run popup, and *Setup…* is offered only when something is genuinely
  missing.
- A tabbed interface with an upscaling slider that shows the resulting size, and
  a bullet next to every setting you changed by hand.

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
