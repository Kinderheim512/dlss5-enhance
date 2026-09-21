Put your ComfyUI workflow here, exported in **API format**.

Default name: `dlss5_video.json` (change it with `workflow.path` in
`config.yaml`, `--workflow`, or the *Browse…* button next to the Workflow field).

**`exemple_dlss5_video.json`** ships with the tool so you can start immediately:
two nodes (the DLSS5 node and its settings) with the node's default values. It is
not the default workflow — it is there to prove the chain works while you prepare
your own export:

```bat
DLSS5-Enhance.exe --cli --preset x2 --folder D:\rushes --workflow workflows\exemple_dlss5_video.json
```

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

Export: in ComfyUI, `Workflow` -> `Export (API)`.
