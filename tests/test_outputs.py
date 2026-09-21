import os
import tempfile
import unittest
from pathlib import Path

from dlss5_enhance.outputs import (
    OUTPUT_EXTENSIONS,
    OutputProbe,
    classify,
    probe_output,
    sanitize_prefix,
    snapshot_outputs,
)

EXTENSIONS = ("mp4", "mov", "mkv")


class PrefixTests(unittest.TestCase):
    def test_plain_stem_is_kept(self):
        self.assertEqual(sanitize_prefix("clip final 01"), "clip final 01")

    def test_unsafe_characters_are_replaced(self):
        self.assertEqual(sanitize_prefix('a<b>c:d"e/f'), "a_b_c_d_e_f")

    def test_leading_dash_is_neutralised(self):
        self.assertEqual(sanitize_prefix("-render"), "DLSS5_-render")

    def test_empty_becomes_default(self):
        self.assertEqual(sanitize_prefix("   "), "DLSS5")


class SnapshotTests(unittest.TestCase):
    def test_only_matching_files_are_snapshotted(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "clip_20260101-120000.mkv").write_bytes(b"x")
            (directory / "clip_notes.txt").write_bytes(b"x")
            (directory / "other_20260101-120000.mkv").write_bytes(b"x")
            snapshot = snapshot_outputs(directory, "clip", EXTENSIONS)
        self.assertEqual(len(snapshot), 1)

    def test_missing_directory_is_empty(self):
        self.assertEqual(snapshot_outputs(Path("D:/nope-dlss5"), "clip", EXTENSIONS), {})


class ProbeTests(unittest.TestCase):
    def test_new_file_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            snapshot = snapshot_outputs(directory, "clip", EXTENSIONS)
            produced = directory / "clip_20260101-120000.mkv"
            produced.write_bytes(b"rendu")
            probe = probe_output(snapshot, directory, "clip", EXTENSIONS)
        self.assertTrue(probe.is_new)
        self.assertTrue(probe.usable)
        self.assertEqual(probe.path.name, "clip_20260101-120000.mkv")

    def test_unchanged_file_is_a_cache_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            existing = directory / "clip_20260101-120000.mkv"
            existing.write_bytes(b"ancien")
            os.utime(existing, (1_700_000_000, 1_700_000_000))
            snapshot = snapshot_outputs(directory, "clip", EXTENSIONS)
            probe = probe_output(snapshot, directory, "clip", EXTENSIONS)
        self.assertFalse(probe.is_new)
        self.assertTrue(probe.usable)
        self.assertEqual(probe.path, existing)

    def test_rewritten_file_counts_as_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            existing = directory / "clip_20260101-120000.mkv"
            existing.write_bytes(b"ancien")
            os.utime(existing, (1_700_000_000, 1_700_000_000))
            snapshot = snapshot_outputs(directory, "clip", EXTENSIONS)
            existing.write_bytes(b"nouveau contenu")
            os.utime(existing, (1_800_000_000, 1_800_000_000))
            probe = probe_output(snapshot, directory, "clip", EXTENSIONS)
        self.assertTrue(probe.is_new)

    def test_no_file_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            snapshot = snapshot_outputs(directory, "clip", EXTENSIONS)
            probe = probe_output(snapshot, directory, "clip", EXTENSIONS)
        self.assertIsNone(probe.path)

    def test_other_prefixes_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "autre_20260101-120000.mkv").write_bytes(b"x")
            snapshot = snapshot_outputs(directory, "clip", EXTENSIONS)
            probe = probe_output(snapshot, directory, "clip", EXTENSIONS)
        self.assertIsNone(probe.path)


class ClassifyTests(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(classify(OutputProbe(), set(), "2"), "missing")

    def test_new_wins_over_cached_signal(self):
        probe = OutputProbe(path=Path("clip_x.mkv"), is_new=True, size=10)
        self.assertEqual(classify(probe, {"2"}, "2"), "new")

    def test_cache_confirmed_by_websocket(self):
        probe = OutputProbe(path=Path("clip_x.mkv"), is_new=False, size=10)
        self.assertEqual(classify(probe, {"2"}, "2"), "cache")

    def test_cache_without_websocket_signal(self):
        probe = OutputProbe(path=Path("clip_x.mkv"), is_new=False, size=10)
        self.assertEqual(classify(probe, set(), "2"), "cache")


class OutputExtensionTests(unittest.TestCase):
    def test_the_output_list_is_the_container_list(self):
        self.assertEqual(OUTPUT_EXTENSIONS, ("mp4", "mkv", "mov"))
        self.assertNotIn("webm", OUTPUT_EXTENSIONS)

    def test_a_webm_source_still_produces_a_detectable_mkv(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            snapshot = snapshot_outputs(directory, "clip", OUTPUT_EXTENSIONS)
            produced = directory / "clip_20260101-120000.mkv"
            produced.write_bytes(b"rendu")
            found = probe_output(snapshot, directory, "clip", OUTPUT_EXTENSIONS)
            missed = probe_output(snapshot, directory, "clip", ("webm",))
        self.assertTrue(found.is_new)
        self.assertEqual(found.path, produced)
        self.assertIsNone(missed.path)


if __name__ == "__main__":
    unittest.main()
