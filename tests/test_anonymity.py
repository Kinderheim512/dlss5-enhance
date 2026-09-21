"""No personal data, no machine path, and no French left in the shipped files."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "dist", "build", "logs", ".tmp-it", ".ruff_cache", "__pycache__"}
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".cmd", ".toml", ".spec", ".json", ".txt"}
SKIP_FILES = {"test_anonymity.py", "settings.json"}

PERSONAL_PATTERNS = (
    "lllam",
    "Kinderheim",
    "OpenFox",
    "forge_stack",
    "instance-model-paths",
    "Comfy-Desktop",
)
PATH_PATTERNS = (
    re.compile(r"[A-Za-z]:\\\\Users\\\\", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\\\Comfy", re.IGNORECASE),
    re.compile(r"C:/Users/", re.IGNORECASE),
    re.compile(r"D:/Comfy", re.IGNORECASE),
)
FRENCH = re.compile(r"[àâäéèêëîïôöùûüçÉÈÊÀ«»]")


def shipped_files(include_tests: bool = True):
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.name in SKIP_FILES:
            continue
        parts = path.relative_to(ROOT).parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        if not include_tests and parts and parts[0] == "tests":
            continue
        yield path


class AnonymityTests(unittest.TestCase):
    def test_no_personal_marker(self):
        offenders = []
        for path in shipped_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in PERSONAL_PATTERNS:
                if marker in text:
                    offenders.append(f"{path.relative_to(ROOT)}: {marker}")
        self.assertEqual(offenders, [])

    def test_no_machine_path(self):
        """Test fixtures use synthetic paths, so the scan covers the shipped files."""
        offenders = []
        for path in shipped_files(include_tests=False):
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in PATH_PATTERNS:
                if pattern.search(text):
                    offenders.append(f"{path.relative_to(ROOT)}: {pattern.pattern}")
        self.assertEqual(offenders, [])

    def test_the_scan_actually_sees_the_project(self):
        names = {path.name for path in shipped_files()}
        self.assertIn("config.yaml", names)
        self.assertIn("README.md", names)
        self.assertIn("comfy_server.py", names)


class LanguageTests(unittest.TestCase):
    def test_no_french_outside_the_catalogue(self):
        """Tests assert French strings on purpose, so only the tool is scanned."""
        offenders = []
        for path in shipped_files(include_tests=False):
            if path.name == "i18n.py":
                continue
            if path.suffix.lower() not in {".py", ".cmd"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if FRENCH.search(text):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_documentation_is_english(self):
        for name in ("README.md", "CHANGELOG.md", "workflows/README.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIsNone(FRENCH.search(text), name)


if __name__ == "__main__":
    unittest.main()
