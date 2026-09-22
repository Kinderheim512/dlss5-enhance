import tempfile
import unittest
from pathlib import Path

from dlss5_enhance.sources import resolve_many


def tree(root: Path) -> None:
    (root / "a.mp4").write_bytes(b"x")
    (root / "b.mkv").write_bytes(b"x")
    (root / "notes.txt").write_bytes(b"x")
    sub = root / "sub"
    sub.mkdir()
    (sub / "c.mov").write_bytes(b"x")


class ResolveManyTests(unittest.TestCase):
    def test_files_and_folders_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree(root)
            sources, problems = resolve_many(
                [root / "a.mp4", root], extensions=("mp4", "mkv", "mov")
            )
        self.assertEqual(problems, [])
        self.assertEqual([path.name for path in sources], ["a.mp4", "b.mkv"])

    def test_duplicates_are_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree(root)
            sources, _ = resolve_many(
                [root / "a.mp4", root / "a.mp4", str(root / "a.mp4")], extensions=("mp4",)
            )
        self.assertEqual(len(sources), 1)

    def test_a_folder_without_video_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty = root / "empty"
            empty.mkdir()
            sources, problems = resolve_many([empty], extensions=("mp4",))
        self.assertEqual(sources, [])
        self.assertEqual(len(problems), 1)
        self.assertIn("empty", problems[0])

    def test_a_missing_path_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.mp4"
            sources, problems = resolve_many([missing], extensions=("mp4",))
        self.assertEqual(sources, [])
        self.assertIn("nope.mp4", problems[0])

    def test_recursive_finds_nested_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree(root)
            sources, _ = resolve_many([root], extensions=("mp4", "mkv", "mov"), recursive=True)
        self.assertEqual(sorted(path.name for path in sources), ["a.mp4", "b.mkv", "c.mov"])

    def test_empty_input(self):
        sources, problems = resolve_many([], extensions=("mp4",))
        self.assertEqual((sources, problems), ([], []))


if __name__ == "__main__":
    unittest.main()
