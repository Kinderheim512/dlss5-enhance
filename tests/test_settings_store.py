import json
import tempfile
import unittest
from pathlib import Path

from dlss5_enhance import settings_store
from dlss5_enhance.settings_store import (
    AppSettings,
    load_settings,
    resolve_path,
    save_settings,
    store_path,
)


class RoundTripTests(unittest.TestCase):
    def test_save_then_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            original = AppSettings(
                language="fr",
                comfy_root="D:/comfyui-portable",
                output_dir="D:/out",
                workflow="workflows/x.json",
                preset="x2",
                source="D:/rushes/a.mp4",
            )
            saved = save_settings(original, path=path)
            loaded, found = load_settings(path=path)
        self.assertEqual(saved, path)
        self.assertEqual(found, path)
        self.assertEqual(loaded.language, "fr")
        self.assertEqual(loaded.comfy_root, "D:/comfyui-portable")
        self.assertEqual(loaded.preset, "x2")

    def test_missing_file_yields_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings, path = load_settings(path=Path(tmp) / "absent.json")
        self.assertEqual(settings, AppSettings())
        self.assertIsNone(path)

    def test_corrupt_file_yields_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("{not json", encoding="utf-8")
            settings, found = load_settings(path=path)
        self.assertEqual(settings, AppSettings())
        self.assertEqual(found, path)

    def test_unknown_and_wrong_typed_keys_are_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(
                json.dumps({"language": "fr", "nope": "x", "comfy_root": ["list"]}),
                encoding="utf-8",
            )
            settings, _ = load_settings(path=path)
        self.assertEqual(settings.language, "fr")
        self.assertIsNone(settings.comfy_root)

    def test_empty_values_are_not_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_settings(AppSettings(language="en"), path=path)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload, {"language": "en"})

    def test_unwritable_path_returns_none(self):
        missing_drive = Path("Q:/nowhere/settings.json")
        self.assertIsNone(save_settings(AppSettings(language="fr"), path=missing_drive))

    def test_falls_back_to_the_second_candidate(self):
        original = settings_store.state_paths
        with tempfile.TemporaryDirectory() as tmp:
            blocked = Path(tmp) / "file-not-a-dir" / "settings.json"
            (Path(tmp) / "file-not-a-dir").write_text("x", encoding="utf-8")
            fallback = Path(tmp) / "fallback.json"
            settings_store.state_paths = lambda app_root=None: [blocked, fallback]
            try:
                saved = save_settings(AppSettings(language="fr"))
            finally:
                settings_store.state_paths = original
            self.assertEqual(saved, fallback)
            self.assertTrue(fallback.is_file())


class PathTests(unittest.TestCase):
    def test_inside_the_app_folder_is_stored_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stored = store_path(root / "workflows" / "x.json", root)
        self.assertEqual(stored, "workflows/x.json")

    def test_outside_the_app_folder_stays_absolute(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app"
            root.mkdir()
            other = Path(tmp) / "elsewhere" / "x.json"
            stored = store_path(other, root)
        self.assertEqual(Path(stored), other)

    def test_resolve_anchors_relative_values_on_the_app_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolved = resolve_path("workflows/x.json", root)
            absolute = resolve_path(str(Path(tmp) / "a.json"), root)
        self.assertEqual(resolved, root / "workflows" / "x.json")
        self.assertTrue(absolute.is_absolute())

    def test_empty_values(self):
        self.assertIsNone(store_path(None, Path("D:/app")))
        self.assertIsNone(store_path("", Path("D:/app")))
        self.assertIsNone(resolve_path(None, Path("D:/app")))
        self.assertIsNone(resolve_path("", Path("D:/app")))

    def test_state_paths_prefers_the_app_folder(self):
        paths = settings_store.state_paths(Path("D:/app"))
        self.assertEqual(paths[0], Path("D:/app") / "settings.json")
        self.assertEqual(len(paths), 2)


if __name__ == "__main__":
    unittest.main()
