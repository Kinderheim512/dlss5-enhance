import tempfile
import unittest
from pathlib import Path

from dlss5_enhance import doctor, installer
from dlss5_enhance.config import load_config
from dlss5_enhance.doctor import (
    BROKEN,
    MISSING,
    OK,
    Check,
    check_comfyui,
    check_disk,
    check_ffmpeg,
    check_node,
    check_runtime,
    report,
    run_checks,
)
from dlss5_enhance.installer import NODE_DIR_NAME, RUNTIME_FILES
from dlss5_enhance.sink import CollectSink


def build_fake_install(base: Path) -> Path:
    root = base / "comfyui"
    (root / "ComfyUI").mkdir(parents=True)
    (root / "ComfyUI" / "main.py").write_text("", encoding="utf-8")
    (root / "python_embeded").mkdir()
    (root / "python_embeded" / "python.exe").write_text("", encoding="utf-8")
    node = root / "ComfyUI" / "custom_nodes" / NODE_DIR_NAME
    (node / "nodes").mkdir(parents=True)
    (node / "nodes" / "enhance_video.py").write_text("", encoding="utf-8")
    (node / "runtime").mkdir()
    for name in RUNTIME_FILES:
        (node / "runtime" / name).write_text("", encoding="utf-8")
    (node / "ffmpeg" / "bin").mkdir(parents=True)
    (node / "ffmpeg" / "bin" / "ffmpeg.exe").write_text("", encoding="utf-8")
    (node / "ffmpeg" / "bin" / "ffprobe.exe").write_text("", encoding="utf-8")
    return root


def node_bin(root: Path) -> Path:
    return root / "ComfyUI" / "custom_nodes" / NODE_DIR_NAME / "ffmpeg" / "bin"


def config_for(base: Path, root: Path | None = None):
    overrides = {}
    if root is not None:
        overrides = {
            "comfy": {
                "root": str(root),
                "python": str(root / "python_embeded" / "python.exe"),
                "ffmpeg": str(node_bin(root) / "ffmpeg.exe"),
                "ffprobe": str(node_bin(root) / "ffprobe.exe"),
            }
        }
    return load_config(
        path=base / "absent.yaml",
        base_dir=base,
        overrides=overrides,
        detect_comfy=False,
    )


class CheckTests(unittest.TestCase):
    def test_nothing_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = config_for(base)
            self.assertEqual(check_comfyui(config).status, MISSING)
            self.assertEqual(check_node(config).status, MISSING)
            self.assertEqual(check_runtime(config).status, MISSING)
            self.assertEqual(check_ffmpeg(config).status, MISSING)

    def test_complete_fake_install_is_all_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = build_fake_install(base)
            config = config_for(base, root)
            self.assertEqual(check_comfyui(config).status, OK)
            self.assertEqual(check_node(config).status, OK)
            self.assertEqual(check_runtime(config).status, OK)
            self.assertEqual(check_ffmpeg(config).status, OK)
            self.assertEqual(check_disk(config).status, OK)

    def test_partial_runtime_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = build_fake_install(base)
            node = root / "ComfyUI" / "custom_nodes" / NODE_DIR_NAME
            (node / "runtime" / "nvngx.dll").unlink()
            config = config_for(base, root)
            self.assertEqual(check_runtime(config).status, MISSING)

    def test_gpu_check_returns_a_status(self):
        result = doctor.check_gpu()
        self.assertIn(result.status, (OK, MISSING, BROKEN))
        self.assertTrue(result.detail)

    def test_run_checks_has_six_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            checks = run_checks(config_for(base))
        self.assertEqual(len(checks), 6)
        self.assertEqual(
            [check.key for check in checks],
            ["d.gpu", "d.comfyui", "d.node", "d.runtime", "d.ffmpeg", "d.disk"],
        )


class LayoutTests(unittest.TestCase):
    """ComfyUI ships in three layouts; the node folder must be found in each."""

    def test_nested_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ComfyUI").mkdir()
            (root / "ComfyUI" / "main.py").write_text("", encoding="utf-8")
            self.assertEqual(
                installer.node_dir(root),
                root / "ComfyUI" / "custom_nodes" / NODE_DIR_NAME,
            )

    def test_portable_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ComfyUI_windows_portable"
            (root / "ComfyUI").mkdir(parents=True)
            (root / "ComfyUI" / "main.py").write_text("", encoding="utf-8")
            self.assertEqual(
                installer.node_dir(root),
                root / "ComfyUI" / "custom_nodes" / NODE_DIR_NAME,
            )

    def test_flat_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ComfyUI"
            root.mkdir()
            (root / "main.py").write_text("", encoding="utf-8")
            self.assertEqual(
                installer.node_dir(root), root / "custom_nodes" / NODE_DIR_NAME
            )


class ReportTests(unittest.TestCase):
    def _report(self, checks) -> tuple[int, list[str]]:
        original = doctor.run_checks
        doctor.run_checks = lambda config: checks
        try:
            sink = CollectSink()
            code = report(None, sink)
        finally:
            doctor.run_checks = original
        return code, sink.lines

    def test_all_green_exits_zero(self):
        code, lines = self._report([Check("d.gpu", OK, "RTX"), Check("d.node", OK, "x")])
        self.assertEqual(code, 0)
        self.assertIn("Everything is ready.", lines[-1])

    def test_a_gap_exits_one(self):
        code, lines = self._report(
            [Check("d.gpu", OK, "RTX"), Check("d.node", MISSING, "nope")]
        )
        self.assertEqual(code, 1)
        self.assertIn("MISSING", "\n".join(lines))
        self.assertIn("still missing", lines[-1])


if __name__ == "__main__":
    unittest.main()
