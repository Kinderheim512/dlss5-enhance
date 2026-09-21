import tempfile
import unittest
from pathlib import Path

from dlss5_enhance.config import default_presets, load_config
from dlss5_enhance.errors import UsageError


class PresetConfigTests(unittest.TestCase):
    def test_defaults_ship_five_presets(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(path=Path(tmp) / "absent.yaml", base_dir=Path(tmp))
        self.assertEqual(
            sorted(config.presets), ["ameliore", "ameliore_plus", "x15", "x2", "x3"]
        )
        self.assertEqual(config.presets["x2"].factor, 2.0)
        self.assertEqual(config.presets["x3"].factor, 3.0)
        self.assertEqual(config.presets["ameliore"].factor, 1.0)
        self.assertEqual(
            config.presets["ameliore_plus"].settings, {"local_structure_strength": 2.0}
        )
        self.assertIsNone(config.preset)

    def test_no_preset_leaves_the_workflow_in_charge(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(path=Path(tmp) / "absent.yaml", base_dir=Path(tmp))
        self.assertEqual(config.processing.quality, "Auto")
        self.assertEqual(config.processing.codec, "HEVC")

    def test_preset_sets_job_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(
                path=Path(tmp) / "absent.yaml",
                overrides={"run": {"preset": "x3"}},
                base_dir=Path(tmp),
            )
        self.assertIsNotNone(config.preset)
        self.assertEqual(config.preset.name, "x3")
        self.assertEqual(config.run.preset_name, "x3")
        self.assertEqual(config.processing.quality, "Best")
        self.assertEqual(config.processing.codec, "h265")
        self.assertEqual(config.processing.container, "mkv")

    def test_cli_overrides_the_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(
                path=Path(tmp) / "absent.yaml",
                overrides={
                    "run": {"preset": "x2"},
                    "processing": {"codec": "h264", "container": "mp4"},
                },
                base_dir=Path(tmp),
            )
        self.assertEqual(config.preset.name, "x2")
        self.assertEqual(config.processing.codec, "h264")
        self.assertEqual(config.processing.container, "mp4")
        self.assertEqual(config.processing.quality, "Best")

    def test_preset_from_yaml_run_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text("run:\n  preset: x15\n", encoding="utf-8")
            config = load_config(path=base / "config.yaml", base_dir=base)
        self.assertEqual(config.preset.name, "x15")
        self.assertEqual(config.processing.quality, "Best")

    def test_unknown_preset_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(UsageError) as ctx:
            load_config(
                path=Path(tmp) / "absent.yaml",
                overrides={"run": {"preset": "x4"}},
                base_dir=Path(tmp),
            )
        self.assertIn("x4", str(ctx.exception))

    def test_user_preset_section_adds_to_the_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text(
                "presets:\n  maison:\n    label: Maison\n    upscaling_mode: 2x\n"
                "    quality: high\n",
                encoding="utf-8",
            )
            config = load_config(
                path=base / "config.yaml",
                overrides={"run": {"preset": "maison"}},
                base_dir=base,
            )
        self.assertIn("maison", config.presets)
        self.assertIn("x2", config.presets)
        self.assertEqual(config.preset.label, "Maison")
        self.assertEqual(config.processing.quality, "high")

    def test_user_can_redefine_a_shipped_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text(
                "presets:\n  x2:\n    label: Mon 2x\n    upscaling_mode: 1.5x\n",
                encoding="utf-8",
            )
            config = load_config(
                path=base / "config.yaml",
                overrides={"run": {"preset": "x2"}},
                base_dir=base,
            )
        self.assertEqual(config.preset.label, "Mon 2x")
        self.assertEqual(config.preset.upscaling_mode, "1.5x (Quality)")

    def test_broken_preset_section_fails_at_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text(
                "presets:\n  casse:\n    upscaling_mode: 4x\n", encoding="utf-8"
            )
            with self.assertRaises(UsageError):
                load_config(path=base / "config.yaml", base_dir=base)

    def test_default_presets_helper_shape(self):
        presets = default_presets()
        for name, body in presets.items():
            self.assertIn("label", body, name)
            self.assertIn("upscaling_mode", body, name)


if __name__ == "__main__":
    unittest.main()
