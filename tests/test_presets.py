import unittest

from dlss5_enhance.errors import UsageError
from dlss5_enhance.presets import (
    UPSCALING_MODES,
    describe_presets,
    load_presets,
    normalize_upscaling,
    resolve_preset,
)


class NormalizeTests(unittest.TestCase):
    def test_label_is_kept(self):
        self.assertEqual(normalize_upscaling("2x (Performance)"), "2x (Performance)")

    def test_bare_factors(self):
        self.assertEqual(normalize_upscaling("2x"), "2x (Performance)")
        self.assertEqual(normalize_upscaling(2), "2x (Performance)")
        self.assertEqual(normalize_upscaling(2.0), "2x (Performance)")
        self.assertEqual(normalize_upscaling("1.5"), "1.5x (Quality)")
        self.assertEqual(normalize_upscaling(1), "1x (DLAA / native)")
        self.assertEqual(normalize_upscaling("3x"), "3x (Ultra Performance)")

    def test_unknown_lists_the_modes(self):
        with self.assertRaises(UsageError) as ctx:
            normalize_upscaling("4x")
        message = str(ctx.exception)
        self.assertIn("4x", message)
        for mode in UPSCALING_MODES:
            self.assertIn(mode, message)

    def test_missing_value(self):
        with self.assertRaises(UsageError):
            normalize_upscaling(None)


class LoadTests(unittest.TestCase):
    def test_shipped_shape(self):
        presets = load_presets(
            {
                "x2": {
                    "label": "Upscale x2",
                    "upscaling_mode": "2x (Performance)",
                    "quality": "Best",
                    "codec": "h265",
                    "container": "mkv",
                }
            }
        )
        preset = presets["x2"]
        self.assertEqual(preset.label, "Upscale x2")
        self.assertEqual(preset.factor, 2.0)
        self.assertEqual(
            preset.job_values(),
            {"quality": "Best", "codec": "h265", "container": "mkv"},
        )

    def test_label_defaults_to_name(self):
        presets = load_presets({"x3": {"upscaling_mode": 3}})
        self.assertEqual(presets["x3"].label, "x3")

    def test_settings_values_carry_the_upscaling_mode(self):
        presets = load_presets(
            {
                "x3": {
                    "upscaling_mode": "3x (Ultra Performance)",
                    "settings": {"local_structure_strength": 2.0},
                }
            }
        )
        self.assertEqual(
            presets["x3"].settings_values(),
            {
                "local_structure_strength": 2.0,
                "upscaling_mode": "3x (Ultra Performance)",
            },
        )

    def test_settings_values_respect_a_custom_input_name(self):
        presets = load_presets({"x2": {"upscaling_mode": "2x (Performance)"}})
        self.assertEqual(
            presets["x2"].settings_values("upscale"), {"upscale": "2x (Performance)"}
        )

    def test_settings_values_empty_without_upscaling(self):
        presets = load_presets({"nu": {"quality": "Best"}})
        self.assertEqual(presets["nu"].settings_values(), {})

    def test_settings_mapping(self):
        presets = load_presets(
            {
                "plus": {
                    "upscaling_mode": "1x",
                    "settings": {"local_structure_strength": 2.0, "automatic_mask": True},
                }
            }
        )
        self.assertEqual(
            presets["plus"].settings,
            {"local_structure_strength": 2.0, "automatic_mask": True},
        )

    def test_unknown_key_is_rejected(self):
        with self.assertRaises(UsageError) as ctx:
            load_presets({"x2": {"upscale": "2x"}})
        message = str(ctx.exception)
        self.assertIn("upscale", message)
        self.assertIn("upscaling_mode", message)

    def test_bad_upscaling_mode_is_rejected(self):
        with self.assertRaises(UsageError):
            load_presets({"x9": {"upscaling_mode": "9x"}})

    def test_settings_must_be_a_mapping(self):
        with self.assertRaises(UsageError):
            load_presets({"x2": {"settings": ["nope"]}})

    def test_body_must_be_a_mapping(self):
        with self.assertRaises(UsageError):
            load_presets({"x2": "2x"})

    def test_empty_section(self):
        self.assertEqual(load_presets(None), {})
        self.assertEqual(load_presets({}), {})


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.presets = load_presets(
            {
                "x2": {"label": "Upscale x2", "upscaling_mode": "2x (Performance)"},
                "x3": {"label": "Upscale x3", "upscaling_mode": "3x (Ultra Performance)"},
            }
        )

    def test_none_means_no_preset(self):
        self.assertIsNone(resolve_preset(None, self.presets))

    def test_known_name(self):
        self.assertEqual(resolve_preset("x3", self.presets).label, "Upscale x3")

    def test_unknown_name_lists_available(self):
        with self.assertRaises(UsageError) as ctx:
            resolve_preset("x4", self.presets)
        message = str(ctx.exception)
        self.assertIn("x4", message)
        self.assertIn("x2", message)
        self.assertIn("x3", message)

    def test_describe(self):
        lines = describe_presets(self.presets)
        self.assertEqual(len(lines), 2)
        self.assertIn("x2", lines[0])
        self.assertIn("2x (Performance)", lines[0])


if __name__ == "__main__":
    unittest.main()
