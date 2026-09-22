import tempfile
import unittest
from pathlib import Path

from dlss5_enhance.config import load_config
from dlss5_enhance.dlss5_settings import (
    BY_NAME,
    SETTINGS,
    STRONG,
    coerce_all,
    validate,
)
from dlss5_enhance.errors import UsageError
from dlss5_enhance.workflow import read_settings_values


class TableTests(unittest.TestCase):
    def test_every_setting_has_a_label_and_a_hint(self):
        for setting in SETTINGS:
            self.assertTrue(setting.label_key.startswith("d.set."), setting.name)
            self.assertTrue(setting.hint_key.endswith(".hint"), setting.name)

    def test_bounds_match_the_node(self):
        self.assertEqual(BY_NAME["local_structure_strength"].maximum, 2.0)
        self.assertEqual(BY_NAME["skin_structure_strength"].minimum, -1.0)
        self.assertEqual(BY_NAME["warmup_frames"].maximum, 16)
        self.assertEqual(BY_NAME["scene_change_threshold"].minimum, 0.01)
        self.assertEqual(BY_NAME["upscaling_mode"].options[0], "1x (DLAA / native)")
        self.assertEqual(len(BY_NAME["upscaling_mode"].options), 5)

    def test_nr_preset_is_not_exposed(self):
        self.assertNotIn("nr_preset", BY_NAME)

    def test_strong_covers_structure_skin_mask_and_model(self):
        self.assertEqual(STRONG["local_structure_strength"], 2.0)
        self.assertEqual(STRONG["skin_structure_strength"], 2.0)
        self.assertIs(STRONG["automatic_mask"], True)
        self.assertEqual(STRONG["dlss_model_preset"], "M")


class ValidateTests(unittest.TestCase):
    def test_accepts_valid_values(self):
        validate({"local_structure_strength": 2.0, "automatic_mask": True})

    def test_unknown_name(self):
        with self.assertRaises(UsageError) as ctx:
            validate({"nope": 1})
        self.assertIn("nope", str(ctx.exception))

    def test_out_of_range(self):
        with self.assertRaises(UsageError):
            validate({"local_structure_strength": 3.0})
        with self.assertRaises(UsageError):
            validate({"warmup_frames": -1})

    def test_bad_option(self):
        with self.assertRaises(UsageError) as ctx:
            validate({"dlss_model_preset": "Z"})
        self.assertIn("Default", str(ctx.exception))

    def test_skin_without_mask_is_refused(self):
        with self.assertRaises(UsageError) as ctx:
            validate({"skin_structure_strength": 2.0, "automatic_mask": False})
        self.assertIn("mask", str(ctx.exception).lower())

    def test_coerce_types(self):
        coerced = coerce_all(
            {
                "local_structure_strength": "2.0",
                "warmup_frames": "4",
                "automatic_mask": "on",
                "dlss_model_preset": "L",
            }
        )
        self.assertEqual(coerced["local_structure_strength"], 2.0)
        self.assertEqual(coerced["warmup_frames"], 4)
        self.assertIs(coerced["automatic_mask"], True)
        self.assertEqual(coerced["dlss_model_preset"], "L")


class ConfigTests(unittest.TestCase):
    def test_settings_section_is_read_and_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text(
                "dlss5_settings:\n  local_structure_strength: 2.0\n  dlss_model_preset: L\n",
                encoding="utf-8",
            )
            config = load_config(path=base / "config.yaml", base_dir=base)
        self.assertEqual(config.settings_overrides["local_structure_strength"], 2.0)
        self.assertEqual(config.settings_overrides["dlss_model_preset"], "L")

    def test_bad_settings_section_fails_at_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text(
                "dlss5_settings:\n  local_structure_strength: 9\n", encoding="utf-8"
            )
            with self.assertRaises(UsageError):
                load_config(path=base / "config.yaml", base_dir=base)

    def test_no_settings_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = load_config(path=base / "absent.yaml", base_dir=base)
        self.assertEqual(dict(config.settings_overrides), {})


class ReadTests(unittest.TestCase):
    def test_reads_the_settings_node(self):
        workflow = {
            "1": {
                "class_type": "DLSS5Settings",
                "inputs": {"upscaling_mode": "2x (Performance)", "nr_style": "Natural"},
            },
            "2": {"class_type": "DLSS5EnhanceVideoFile", "inputs": {}},
        }
        values = read_settings_values(
            workflow, "DLSS5Settings", ["upscaling_mode", "nr_style", "missing"]
        )
        self.assertEqual(values, {"upscaling_mode": "2x (Performance)", "nr_style": "Natural"})

    def test_no_settings_node(self):
        workflow = {"2": {"class_type": "X", "inputs": {}}}
        self.assertEqual(read_settings_values(workflow, "Y", ["a"]), {})


if __name__ == "__main__":
    unittest.main()
