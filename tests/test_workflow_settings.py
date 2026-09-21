import unittest

from dlss5_enhance.errors import WorkflowError
from dlss5_enhance.workflow import build_prompt


def sample_workflow():
    return {
        "1": {
            "class_type": "DLSS5Settings",
            "inputs": {
                "upscaling_mode": "1x (DLAA / native)",
                "nr_style": "Default",
                "local_structure_strength": 1.5,
                "automatic_mask": True,
            },
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


JOB = {
    "video_path": r"D:\in\clip.mp4",
    "filename_prefix": "clip",
    "output_directory": r"D:\out",
}


class SettingsInjectionTests(unittest.TestCase):
    def test_preset_upscaling_reaches_the_settings_node(self):
        prompt = build_prompt(
            sample_workflow(),
            "2",
            JOB,
            settings_class_type="DLSS5Settings",
            settings_values={"upscaling_mode": "2x (Performance)"},
        )
        self.assertEqual(prompt["1"]["inputs"]["upscaling_mode"], "2x (Performance)")

    def test_other_settings_inputs_are_untouched(self):
        prompt = build_prompt(
            sample_workflow(),
            "2",
            JOB,
            settings_class_type="DLSS5Settings",
            settings_values={"upscaling_mode": "3x (Ultra Performance)"},
        )
        self.assertEqual(prompt["1"]["inputs"]["nr_style"], "Default")
        self.assertEqual(prompt["1"]["inputs"]["local_structure_strength"], 1.5)
        self.assertEqual(prompt["1"]["inputs"]["automatic_mask"], True)

    def test_extra_settings_overrides(self):
        prompt = build_prompt(
            sample_workflow(),
            "2",
            JOB,
            settings_class_type="DLSS5Settings",
            settings_values={
                "upscaling_mode": "1x (DLAA / native)",
                "local_structure_strength": 2.0,
            },
        )
        self.assertEqual(prompt["1"]["inputs"]["local_structure_strength"], 2.0)

    def test_the_video_node_is_still_filled(self):
        prompt = build_prompt(
            sample_workflow(),
            "2",
            JOB,
            settings_class_type="DLSS5Settings",
            settings_values={"upscaling_mode": "2x (Performance)"},
        )
        self.assertEqual(prompt["2"]["inputs"]["video_path"], r"D:\in\clip.mp4")
        self.assertEqual(prompt["2"]["inputs"]["settings"], ["1", 0])

    def test_original_workflow_is_not_mutated(self):
        workflow = sample_workflow()
        build_prompt(
            workflow,
            "2",
            JOB,
            settings_class_type="DLSS5Settings",
            settings_values={"upscaling_mode": "2x (Performance)"},
        )
        self.assertEqual(workflow["1"]["inputs"]["upscaling_mode"], "1x (DLAA / native)")

    def test_unknown_settings_key_is_reported(self):
        with self.assertRaises(WorkflowError) as ctx:
            build_prompt(
                sample_workflow(),
                "2",
                JOB,
                settings_class_type="DLSS5Settings",
                settings_values={"upscaling": "2x"},
            )
        message = str(ctx.exception)
        self.assertIn("upscaling", message)
        self.assertIn("upscaling_mode", message)

    def test_missing_settings_node_is_reported(self):
        workflow = sample_workflow()
        del workflow["1"]
        with self.assertRaises(WorkflowError) as ctx:
            build_prompt(
                workflow,
                "2",
                JOB,
                settings_class_type="DLSS5Settings",
                settings_values={"upscaling_mode": "2x (Performance)"},
            )
        self.assertIn("DLSS5Settings", str(ctx.exception))

    def test_settings_values_without_class_type_is_reported(self):
        with self.assertRaises(WorkflowError):
            build_prompt(
                sample_workflow(),
                "2",
                JOB,
                settings_values={"upscaling_mode": "2x (Performance)"},
            )

    def test_no_settings_values_leaves_the_workflow_alone(self):
        prompt = build_prompt(sample_workflow(), "2", JOB)
        self.assertEqual(prompt["1"]["inputs"]["upscaling_mode"], "1x (DLAA / native)")


if __name__ == "__main__":
    unittest.main()
