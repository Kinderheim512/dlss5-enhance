import json
import logging
import tempfile
import unittest
from pathlib import Path

from dlss5_enhance.config import load_config
from dlss5_enhance.errors import UsageError
from dlss5_enhance.runner import Orchestrator
from dlss5_enhance.sink import CollectSink

IMAGE_WORKFLOW = {
    "1": {
        "class_type": "DLSS5Settings",
        "inputs": {"upscaling_mode": "1x (DLAA / native)"},
    },
    "2": {"class_type": "LoadImage", "inputs": {"image": "x.png"}},
    "3": {"class_type": "DLSS5EnhanceImages", "inputs": {}},
    "4": {
        "class_type": "SaveImageAdvanced",
        "inputs": {
            "filename_prefix": "p",
            "format": "png",
            "format.bit_depth": "8-bit",
            "format.input_color_space": "sRGB",
        },
    },
}
VIDEO_WORKFLOW = {
    "1": {
        "class_type": "DLSS5Settings",
        "inputs": {"upscaling_mode": "2x (Performance)"},
    },
    "2": {
        "class_type": "DLSS5EnhanceVideoFile",
        "inputs": {
            "video_path": "",
            "filename_prefix": "p",
            "output_directory": "",
            "codec": "HEVC",
            "container": "MKV",
            "quality": "Best",
            "max_frames": 0,
            "copy_audio": True,
            "verify_neural_rendering": True,
        },
    },
}


def build(tmp: str, mode: str) -> tuple[Orchestrator, CollectSink]:
    base = Path(tmp)
    (base / "config.yaml").write_text(
        "processing:\n  output: sorties\n"
        "workflow:\n  path: video.json\n  image:\n    path: image.json\n",
        encoding="utf-8",
    )
    (base / "video.json").write_text(json.dumps(VIDEO_WORKFLOW), encoding="utf-8")
    (base / "image.json").write_text(json.dumps(IMAGE_WORKFLOW), encoding="utf-8")
    config = load_config(path=base / "config.yaml")
    sink = CollectSink()
    orchestrator = Orchestrator(
        config=config,
        logger=logging.getLogger("test"),
        sink=sink,
        mode=mode,
    )
    if mode == "image":
        orchestrator._validate_image_environment()
    else:
        orchestrator._validate_environment()
    return orchestrator, sink


class PlanTests(unittest.TestCase):
    def test_image_plan_names_the_image_workflow_and_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            orchestrator, sink = build(tmp, "image")
            source = Path(tmp) / "photo.png"
            source.write_bytes(b"x")
            orchestrator._print_plan([source])
            text = "\n".join(sink.lines)
            self.assertIn("image.json", text)
            self.assertIn("DLSS5EnhanceImages", text)
            self.assertIn("image format      : png", text)
            self.assertNotIn("codec / container", text)
            self.assertNotIn("encoders", text)
            self.assertNotIn("video.json", text)

    def test_an_unreachable_image_format_is_refused_before_submitting(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text(
                "processing:\n  output: sorties\n  image_format: avif\n"
                "workflow:\n  path: video.json\n  image:\n    path: image.json\n",
                encoding="utf-8",
            )
            (base / "video.json").write_text(json.dumps(VIDEO_WORKFLOW), encoding="utf-8")
            (base / "image.json").write_text(json.dumps(IMAGE_WORKFLOW), encoding="utf-8")
            config = load_config(path=base / "config.yaml")
            orchestrator = Orchestrator(
                config=config,
                logger=logging.getLogger("test"),
                sink=CollectSink(),
                mode="image",
            )
            with self.assertRaises(UsageError):
                orchestrator._validate_image_environment()

    def test_video_plan_still_shows_the_codec_and_encoders(self):
        with tempfile.TemporaryDirectory() as tmp:
            orchestrator, sink = build(tmp, "video")
            source = Path(tmp) / "clip.mp4"
            source.write_bytes(b"x")
            orchestrator._print_plan([source])
            text = "\n".join(sink.lines)
            self.assertIn("video.json", text)
            self.assertIn("codec / container", text)
            self.assertNotIn("image.json", text)


if __name__ == "__main__":
    unittest.main()
