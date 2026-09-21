import unittest

from dlss5_enhance.errors import MappingError
from dlss5_enhance.mappings import (
    normalize_extensions,
    resolve_codec,
    resolve_container,
    resolve_quality,
    validate_codec_container,
)


class QualityTests(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(resolve_quality("draft"), "Auto")
        self.assertEqual(resolve_quality("low"), "Auto")
        self.assertEqual(resolve_quality("normal"), "Good")
        self.assertEqual(resolve_quality("medium"), "Good")
        self.assertEqual(resolve_quality("high"), "Best")
        self.assertEqual(resolve_quality("max"), "Max")

    def test_canonical_and_case(self):
        self.assertEqual(resolve_quality("Auto"), "Auto")
        self.assertEqual(resolve_quality("best"), "Best")
        self.assertEqual(resolve_quality("  HIGH  "), "Best")

    def test_invalid_lists_accepted(self):
        with self.assertRaises(MappingError) as ctx:
            resolve_quality("ultra")
        message = str(ctx.exception)
        self.assertIn("ultra", message)
        self.assertIn("draft", message)
        self.assertIn("high", message)


class CodecTests(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(resolve_codec("h264"), "H.264")
        self.assertEqual(resolve_codec("h265"), "HEVC")
        self.assertEqual(resolve_codec("hevc"), "HEVC")
        self.assertEqual(resolve_codec("av1"), "AV1")
        self.assertEqual(resolve_codec("prores"), "ProRes Proxy")

    def test_invalid(self):
        with self.assertRaises(MappingError) as ctx:
            resolve_codec("vp9")
        self.assertIn("vp9", str(ctx.exception))


class ContainerTests(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(resolve_container("mp4"), "MP4")
        self.assertEqual(resolve_container("MKV"), "MKV")
        self.assertEqual(resolve_container("mov"), "MOV")

    def test_invalid(self):
        with self.assertRaises(MappingError):
            resolve_container("avi")


class CompatibilityTests(unittest.TestCase):
    def test_prores_needs_mov_or_mkv(self):
        validate_codec_container("ProRes Proxy", "MOV")
        validate_codec_container("ProRes Proxy", "MKV")
        with self.assertRaises(MappingError) as ctx:
            validate_codec_container("ProRes Proxy", "MP4")
        self.assertIn("MOV or MKV", str(ctx.exception))

    def test_others_accept_mp4(self):
        validate_codec_container("HEVC", "MP4")
        validate_codec_container("AV1", "MP4")
        validate_codec_container("H.264", "MP4")


class ExtensionTests(unittest.TestCase):
    def test_normalise(self):
        self.assertEqual(normalize_extensions("mp4, .MOV ;mkv"), ("mp4", "mov", "mkv"))
        self.assertEqual(normalize_extensions(["*.mp4", "MP4"]), ("mp4",))
        self.assertEqual(normalize_extensions(None), ())


if __name__ == "__main__":
    unittest.main()
