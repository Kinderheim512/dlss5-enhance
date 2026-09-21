import json
import tempfile
import unittest
from pathlib import Path

from dlss5_enhance.config import TargetSelector
from dlss5_enhance.errors import WorkflowError
from dlss5_enhance.workflow import (
    EXAMPLE_WORKFLOW_NAME,
    build_prompt,
    load_workflow,
    missing_workflow_message,
    read_upscaling_mode,
    resolve_target,
)


def sample_workflow():
    return {
        "1": {
            "class_type": "DLSS5Settings",
            "inputs": {"upscaling_mode": "2x (Performance)", "nr_style": "Cinematic"},
            "_meta": {"title": "DLSS5 Settings"},
        },
        "2": {
            "class_type": "DLSS5EnhanceVideoFile",
            "inputs": {
                "video_path": "",
                "settings": ["1", 0],
                "codec": "HEVC",
                "container": "MKV",
                "quality": "Auto",
                "filename_prefix": "DLSS5",
                "output_directory": "",
                "max_frames": 0,
                "copy_audio": True,
                "verify_neural_rendering": True,
            },
            "_meta": {"title": "DLSS5 Enhance Video File"},
        },
    }


VALUES = {
    "video_path": r"D:\rushes\clip.mp4",
    "filename_prefix": "clip",
    "output_directory": r"D:\out",
    "codec": "HEVC",
    "container": "MKV",
    "quality": "Best",
    "max_frames": 0,
    "copy_audio": True,
    "verify_neural_rendering": True,
}


class MissingWorkflowMessageTests(unittest.TestCase):
    def test_message_explains_how_to_get_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            message = missing_workflow_message(Path(tmp) / "dlss5_video.json")
        self.assertIn("not found", message)
        self.assertIn("Export (API)", message)
        self.assertIn("--workflow", message)
        self.assertNotIn("exemple", message)

    def test_message_points_at_the_example_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / EXAMPLE_WORKFLOW_NAME).write_text("{}", encoding="utf-8")
            message = missing_workflow_message(base / "dlss5_video.json")
        self.assertIn(EXAMPLE_WORKFLOW_NAME, message)


class LoadTests(unittest.TestCase):
    def test_missing_file(self):
        with self.assertRaises(WorkflowError):
            load_workflow(Path(tempfile.gettempdir()) / "nope-dlss5.json")

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{oops", encoding="utf-8")
            with self.assertRaises(WorkflowError):
                load_workflow(path)

    def test_ui_format_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ui.json"
            path.write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
            with self.assertRaises(WorkflowError) as ctx:
                load_workflow(path)
            self.assertIn("Export (API)", str(ctx.exception))

    def test_valid_api_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wf.json"
            path.write_text(json.dumps(sample_workflow()), encoding="utf-8")
            self.assertEqual(len(load_workflow(path)), 2)


class ResolveTests(unittest.TestCase):
    def test_by_class_type(self):
        selector = TargetSelector(class_type="DLSS5EnhanceVideoFile")
        self.assertEqual(resolve_target(sample_workflow(), selector), "2")

    def test_by_title(self):
        selector = TargetSelector(class_type=None, title="DLSS5 Enhance Video File")
        self.assertEqual(resolve_target(sample_workflow(), selector), "2")

    def test_by_id_wins(self):
        selector = TargetSelector(id="1", class_type="DLSS5EnhanceVideoFile")
        self.assertEqual(resolve_target(sample_workflow(), selector), "1")

    def test_unknown_id(self):
        with self.assertRaises(WorkflowError) as ctx:
            resolve_target(sample_workflow(), TargetSelector(id="42"))
        self.assertIn("42", str(ctx.exception))

    def test_no_match_lists_nodes(self):
        selector = TargetSelector(class_type="DLSS5EnhanceImages")
        with self.assertRaises(WorkflowError) as ctx:
            resolve_target(sample_workflow(), selector)
        message = str(ctx.exception)
        self.assertIn("DLSS5EnhanceImages", message)
        self.assertIn("DLSS5EnhanceVideoFile", message)

    def test_ambiguous_match_asks_for_id(self):
        workflow = sample_workflow()
        workflow["3"] = {
            "class_type": "DLSS5EnhanceVideoFile",
            "inputs": dict(workflow["2"]["inputs"]),
        }
        with self.assertRaises(WorkflowError) as ctx:
            resolve_target(workflow, TargetSelector(class_type="DLSS5EnhanceVideoFile"))
        message = str(ctx.exception)
        self.assertIn("2 nodes", message)
        self.assertIn("workflow.target.id", message)


class BuildPromptTests(unittest.TestCase):
    def test_injection_and_isolation(self):
        workflow = sample_workflow()
        prompt = build_prompt(workflow, "2", VALUES)

        self.assertEqual(prompt["2"]["inputs"]["video_path"], r"D:\rushes\clip.mp4")
        self.assertEqual(prompt["2"]["inputs"]["filename_prefix"], "clip")
        self.assertEqual(prompt["2"]["inputs"]["quality"], "Best")
        self.assertEqual(prompt["2"]["inputs"]["settings"], ["1", 0])
        self.assertEqual(prompt["1"]["inputs"]["upscaling_mode"], "2x (Performance)")
        self.assertEqual(workflow["2"]["inputs"]["video_path"], "")

    def test_unknown_input_is_reported_with_available_inputs(self):
        values = dict(VALUES)
        values["upscaling"] = "2x"
        with self.assertRaises(WorkflowError) as ctx:
            build_prompt(sample_workflow(), "2", values)
        message = str(ctx.exception)
        self.assertIn("upscaling", message)
        self.assertIn("video_path", message)

    def test_force_sets_is_changed(self):
        prompt = build_prompt(sample_workflow(), "2", VALUES, force=True, is_changed_token="abc")
        self.assertEqual(prompt["2"]["is_changed"], "abc")

    def test_no_force_leaves_is_changed_alone(self):
        prompt = build_prompt(sample_workflow(), "2", VALUES)
        self.assertNotIn("is_changed", prompt["2"])


class UpscalingTests(unittest.TestCase):
    def test_reads_factor(self):
        self.assertEqual(read_upscaling_mode(sample_workflow()), 2.0)

    def test_defaults_to_one(self):
        workflow = sample_workflow()
        workflow["1"]["inputs"]["upscaling_mode"] = "surprise"
        self.assertEqual(read_upscaling_mode(workflow), 1.0)

    def test_missing_settings_node(self):
        self.assertEqual(read_upscaling_mode({"2": {"class_type": "X", "inputs": {}}}), 1.0)


if __name__ == "__main__":
    unittest.main()
