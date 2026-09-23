import tempfile
import unittest
from pathlib import Path

from dlss5_enhance import image_formats, presets_store, staging


class FakeClient:
    """A ComfyUI stand-in: an input folder, an output folder and a result."""

    def __init__(self, payload: bytes = b"png-bytes") -> None:
        self.payload = payload
        self.uploaded: list[tuple[str, str]] = []
        self.files: list[str] = []
        self.views: list[str] = []

    def upload_image(self, path: Path, subfolder: str = "", type_: str = "input") -> str:
        self.uploaded.append((path.name, subfolder))
        return f"{subfolder}/{path.name}" if subfolder else path.name

    def output_files(self, subfolder: str = "") -> list[str]:
        return list(self.files)

    def view(self, filename: str, subfolder: str = "", type_: str = "output") -> bytes:
        self.views.append(filename)
        return self.payload


class StagingTests(unittest.TestCase):
    def test_upload_returns_the_relative_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "photo.jpg"
            source.write_bytes(b"jpeg")
            client = FakeClient()
            name = staging.upload_source(client, source)
        self.assertEqual(name, "dlss5-enhance/photo.jpg")
        self.assertEqual(client.uploaded, [("photo.jpg", "dlss5-enhance")])

    def test_prefix_is_unique_per_job(self):
        first = staging.result_prefix("clip", "aaa")
        second = staging.result_prefix("clip", "bbb")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("clip_"))

    def test_results_are_downloaded_and_renamed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out"
            client = FakeClient()
            client.files = ["clip_abc_00001_.png", "other_00001_.png"]
            written = staging.fetch_results(client, "clip_abc", target, "clip", ("png",))
            payload = written[0].read_bytes()
        self.assertEqual(len(written), 1)
        self.assertTrue(written[0].name.startswith("clip_"))
        self.assertEqual(written[0].suffix, ".png")
        self.assertEqual(payload, b"png-bytes")

    def test_several_results_get_a_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out"
            client = FakeClient()
            client.files = ["clip_abc_00001_.png", "clip_abc_00002_.png"]
            written = staging.fetch_results(client, "clip_abc", target, "clip", ("png",))
        self.assertEqual(len(written), 2)
        self.assertNotEqual(written[0].name, written[1].name)

    def test_other_prefixes_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out"
            client = FakeClient()
            client.files = ["other_00001_.png"]
            written = staging.fetch_results(
                client, "clip_abc", target, "clip", ("png",), timeout=0.1
            )
        self.assertEqual(written, [])
        self.assertEqual(client.views, [])

    def test_newest_local_finds_the_previous_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "clip_20260101-000000.png").write_bytes(b"x")
            (target / "other_20260101-000000.png").write_bytes(b"x")
            found = staging.newest_local(target, "clip")
        self.assertEqual(found.name, "clip_20260101-000000.png")

    def test_newest_local_without_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(staging.newest_local(Path(tmp), "clip"))


class FormatTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(image_formats.NAMES, ("png", "avif", "exr"))

    def test_normalize(self):
        self.assertEqual(image_formats.normalize("PNG"), "png")
        self.assertEqual(image_formats.normalize(".exr"), "exr")
        self.assertIsNone(image_formats.normalize("jpeg"))
        self.assertIsNone(image_formats.normalize(None))
        self.assertIsNone(image_formats.normalize("nope"))

    def test_inputs_carry_the_sub_inputs(self):
        values = image_formats.inputs_for("png")
        self.assertEqual(values["format"], "png")
        self.assertEqual(values["format.bit_depth"], "8-bit")
        self.assertEqual(values["format.input_color_space"], "sRGB")

    def test_avif_inputs(self):
        values = image_formats.inputs_for("avif", "format")
        self.assertEqual(values["format.save_mode"], "still images")
        self.assertIn("format.crf", values)

    def test_extension(self):
        self.assertEqual(image_formats.extension("exr"), ".exr")
        self.assertEqual(image_formats.extension(None), ".png")


class PresetStoreTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "presets.yaml"
            presets_store.save_user_preset(
                "maison", {"label": "Ma maison", "upscaling_mode": "2x"}, path
            )
            loaded = presets_store.load_user_presets(path)
            known = presets_store.is_user_preset("maison", path)
        self.assertEqual(loaded["maison"]["upscaling_mode"], "2x")
        self.assertTrue(known)

    def test_replace_and_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "presets.yaml"
            presets_store.save_user_preset("a", {"upscaling_mode": "1x"}, path)
            presets_store.save_user_preset("a", {"upscaling_mode": "3x"}, path)
            self.assertEqual(presets_store.load_user_presets(path)["a"]["upscaling_mode"], "3x")
            self.assertTrue(presets_store.delete_user_preset("a", path))
            self.assertEqual(presets_store.load_user_presets(path), {})

    def test_delete_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "presets.yaml"
            self.assertFalse(presets_store.delete_user_preset("nope", path))

    def test_broken_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "presets.yaml"
            path.write_text("presets: [oops\n", encoding="utf-8")
            self.assertEqual(presets_store.load_user_presets(path), {})

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(presets_store.load_user_presets(Path(tmp) / "absent.yaml"), {})


if __name__ == "__main__":
    unittest.main()
