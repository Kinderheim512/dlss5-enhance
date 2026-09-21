import unittest
from pathlib import Path

from dlss5_enhance.media import codec_encoder, output_size, probe_encoder


def _ffmpeg() -> Path | None:
    """Resolved from the configuration, so no machine path is hard-coded."""
    try:
        from dlss5_enhance.config import load_config
        from dlss5_enhance.settings_store import load_settings

        config = load_config(settings=load_settings()[0])
    except Exception:
        return None
    candidate = config.comfy.ffmpeg
    return candidate if candidate is not None and candidate.is_file() else None


FFMPEG = _ffmpeg()


class EncoderNameTests(unittest.TestCase):
    def test_codec_to_encoder(self):
        self.assertEqual(codec_encoder("H.264"), "h264_nvenc")
        self.assertEqual(codec_encoder("HEVC"), "hevc_nvenc")
        self.assertEqual(codec_encoder("AV1"), "av1_nvenc")
        self.assertEqual(codec_encoder("ProRes Proxy"), "prores_ks")


class OutputSizeTests(unittest.TestCase):
    def test_1x_is_native(self):
        self.assertEqual(output_size(1920, 1080, 1.0), (1920, 1080))

    def test_2x_doubles(self):
        self.assertEqual(output_size(1920, 1080, 2.0), (3840, 2160))

    def test_odd_sizes_are_made_even(self):
        width, height = output_size(1001, 563, 1.0)
        self.assertEqual(width % 2, 0)
        self.assertEqual(height % 2, 0)

    def test_long_edge_is_clamped(self):
        width, height = output_size(3840, 2160, 3.0)
        self.assertLessEqual(max(width, height), 7680)

    def test_short_edge_is_clamped(self):
        width, height = output_size(2160, 3840, 3.0)
        self.assertLessEqual(min(width, height), 4320)


class ProbeTests(unittest.TestCase):
    def test_missing_ffmpeg_reports_a_reason(self):
        ok, reason = probe_encoder(Path("D:/nope/ffmpeg.exe"), "hevc_nvenc", 320, 240)
        self.assertFalse(ok)
        self.assertTrue(reason)

    @unittest.skipUnless(FFMPEG, "node ffmpeg not present")
    def test_real_probe_returns_a_verdict_for_each_encoder(self):
        for encoder in ("h264_nvenc", "hevc_nvenc", "av1_nvenc"):
            ok, reason = probe_encoder(FFMPEG, encoder, 640, 360, timeout=120)
            self.assertIsInstance(ok, bool)
            self.assertTrue(reason)
            if not ok:
                self.assertTrue(reason.strip())


if __name__ == "__main__":
    unittest.main()
