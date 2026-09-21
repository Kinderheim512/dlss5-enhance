import tempfile
import unittest
from pathlib import Path

from dlss5_enhance.errors import UsageError
from dlss5_enhance.sources import resolve_sources


def make_tree(root: Path) -> None:
    (root / "a.mp4").write_bytes(b"x")
    (root / "b.mkv").write_bytes(b"x")
    (root / "notes.txt").write_bytes(b"x")
    nested = root / "sub"
    nested.mkdir()
    (nested / "c.mov").write_bytes(b"x")


class FileTests(unittest.TestCase):
    def test_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_tree(root)
            sources, folder_mode = resolve_sources(
                input_path=str(root / "a.mp4"), extensions=("mp4", "mkv")
            )
        self.assertFalse(folder_mode)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].name, "a.mp4")

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(UsageError):
            resolve_sources(input_path=str(Path(tmp) / "nope.mp4"), extensions=("mp4",))

    def test_off_extension_warns_but_proceeds(self):
        warnings: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_tree(root)
            sources, _ = resolve_sources(
                input_path=str(root / "notes.txt"),
                extensions=("mp4",),
                warn=warnings.append,
            )
        self.assertEqual(len(sources), 1)
        self.assertEqual(len(warnings), 1)
        self.assertIn("notes.txt", warnings[0])


class FolderTests(unittest.TestCase):
    def test_non_recursive_skips_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_tree(root)
            sources, folder_mode = resolve_sources(
                folder=str(root), extensions=("mp4", "mkv", "mov")
            )
        self.assertTrue(folder_mode)
        self.assertEqual([path.name for path in sources], ["a.mp4", "b.mkv"])

    def test_recursive_includes_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_tree(root)
            sources, _ = resolve_sources(
                folder=str(root), extensions=("mp4", "mkv", "mov"), recursive=True
            )
        self.assertEqual([path.name for path in sources], ["a.mp4", "b.mkv", "c.mov"])

    def test_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(UsageError):
            resolve_sources(folder=tmp, extensions=("mp4",))

    def test_missing_folder(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(UsageError):
            resolve_sources(folder=str(Path(tmp) / "nope"), extensions=("mp4",))


class ExclusiveTests(unittest.TestCase):
    def test_neither_source(self):
        with self.assertRaises(UsageError):
            resolve_sources(extensions=("mp4",))

    def test_both_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_tree(root)
            with self.assertRaises(UsageError):
                resolve_sources(
                    input_path=str(root / "a.mp4"), folder=str(root), extensions=("mp4",)
                )


if __name__ == "__main__":
    unittest.main()
