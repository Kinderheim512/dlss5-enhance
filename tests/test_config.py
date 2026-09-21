import tempfile
import unittest
from pathlib import Path

from dlss5_enhance.config import load_config
from dlss5_enhance.errors import UsageError


class ConfigTests(unittest.TestCase):
    def test_defaults_without_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(path=Path(tmp) / "absent.yaml", base_dir=Path(tmp))
        self.assertEqual(config.comfy.port, 8188)
        self.assertEqual(config.comfy.host, "127.0.0.1")
        self.assertEqual(config.processing.extensions, ("mp4", "mov", "mkv", "webm"))
        self.assertEqual(config.processing.timeout, 1200.0)
        self.assertIsNone(config.config_path)

    def test_yaml_overrides_defaults_and_cli_overrides_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text(
                "comfy:\n  port: 9999\nprocessing:\n  quality: high\n  timeout: 30\n"
                "  output: sorties\n",
                encoding="utf-8",
            )
            config = load_config(
                path=base / "config.yaml",
                overrides={"processing": {"codec": "h264", "timeout": 45}},
                base_dir=base,
            )
        self.assertEqual(config.comfy.port, 9999)
        self.assertEqual(config.processing.quality, "high")
        self.assertEqual(config.processing.codec, "h264")
        self.assertEqual(config.processing.timeout, 45.0)
        self.assertEqual(config.processing.output, base / "sorties")

    def test_relative_paths_resolve_against_config_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text(
                "workflow:\n  path: mes_workflows/du_jour.json\nlogging:\n  dir: mes_logs\n",
                encoding="utf-8",
            )
            config = load_config(path=base / "config.yaml", base_dir=base)
        self.assertEqual(config.workflow.path, base / "mes_workflows" / "du_jour.json")
        self.assertEqual(config.log_dir, base / "mes_logs")

    def test_absolute_paths_are_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text(
                "processing:\n  output: D:/rendus\n", encoding="utf-8"
            )
            config = load_config(path=base / "config.yaml", base_dir=base)
        self.assertEqual(config.processing.output, Path("D:/rendus"))

    def test_invalid_yaml_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text("comfy: [unclosed\n", encoding="utf-8")
            with self.assertRaises(UsageError):
                load_config(path=base / "config.yaml", base_dir=base)

    def test_non_mapping_top_level_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text("- a\n- b\n", encoding="utf-8")
            with self.assertRaises(UsageError):
                load_config(path=base / "config.yaml", base_dir=base)

    def test_zero_timeout_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text("processing:\n  timeout: 0\n", encoding="utf-8")
            with self.assertRaises(UsageError):
                load_config(path=base / "config.yaml", base_dir=base)

    def test_server_command_contains_listen_and_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = load_config(path=base / "absent.yaml", base_dir=base)
        command = config.comfy.server_command()
        self.assertIn("--listen", command)
        self.assertIn("127.0.0.1", command)
        self.assertIn("--port", command)
        self.assertIn("8188", command)
        self.assertNotIn("--extra-model-paths-config", command)
        self.assertEqual(config.comfy.base_url, "http://127.0.0.1:8188")
        self.assertEqual(config.comfy.ws_url, "ws://127.0.0.1:8188/ws")
        self.assertFalse(config.installed)

    def test_server_command_uses_the_configured_interpreter(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "config.yaml").write_text(
                "comfy:\n  python: D:/tools/python.exe\n  port: 9000\n", encoding="utf-8"
            )
            config = load_config(path=base / "config.yaml", base_dir=base)
        command = config.comfy.server_command()
        self.assertEqual(command[0], "D:\\tools\\python.exe")
        self.assertIn("9000", command)

    def test_output_defaults_to_downloads_and_workflow_to_the_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = load_config(path=base / "absent.yaml", base_dir=base)
        self.assertEqual(config.processing.output, Path.home() / "Downloads")
        self.assertEqual(
            config.workflow.path, base / "workflows" / "exemple_dlss5_video.json"
        )


if __name__ == "__main__":
    unittest.main()
