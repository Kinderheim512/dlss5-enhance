Put your ComfyUI workflows here, exported in **API format**.

Two examples ship with the tool so you can start immediately:

- **`exemple_dlss5_video.json`** — the video chain (the default workflow);
- **`exemple_dlss5_image.json`** — the image chain.

They contain only the nodes the tool needs, with the node's default values. They
are not mandatory — they are there to prove the chain works while you prepare
your own export:

```bat
DLSS5-Enhance.exe --cli --preset x2 --folder D:\rushes --workflow workflows\exemple_dlss5_video.json
DLSS5-Enhance.exe --cli --preset x2 --images D:\photos --image-workflow workflows\exemple_dlss5_image.json
```

## Video workflow

Default name: `dlss5_video.json` (change it with `workflow.path` in
`config.yaml`, `--workflow`, or the *Browse…* button next to the Workflow field).

The workflow you provide must contain:

- a `DLSS5 Enhance Video File` node (`DLSS5EnhanceVideoFile`) — the injection
  target;
- a `DLSS5 Settings` node (`DLSS5Settings`) wired to its `settings` input.

These inputs are written for every job:
`video_path`, `filename_prefix`, `output_directory`, `codec`, `container`,
`quality`, `max_frames`, `copy_audio`, `verify_neural_rendering`.

When a preset is used, its upscaling mode is written into the `upscaling_mode`
input of the `DLSS5 Settings` node (configurable with
`workflow.settings.upscaling_input`), and its optional `settings:` into the
matching inputs of the same node. **Everything else is left untouched**: model
preset, style, masking, neural render strength — your manual settings win.

## Image workflow

Set with `workflow.image.path` in `config.yaml`, `--image-workflow`, or the
*Browse…* button on the **Images** tab.

The workflow you provide must contain:

- a `DLSS5EnhanceImages` node — the injection target;
- a `LoadImage` node feeding its `images` input. Its `image` input is set to the
  uploaded source file name;
- a `SaveImageAdvanced` (or `SaveImage`) node receiving the result. Its
  `filename_prefix` is set so the result can be found again, then fetched back
  and renamed `stem_YYYYMMDD-HHMMSS.ext` in your output folder.

The **output format** is the save node's, not the tool's: PNG, AVIF or EXR with
`SaveImageAdvanced` (`format` plus the matching `format.*` sub-options, which
only exist for the exported format). To change it, edit the workflow — the tool
reports the format it finds and refuses a `--image-format` that does not match.

Export: in ComfyUI, `Workflow` -> `Export (API)`.
