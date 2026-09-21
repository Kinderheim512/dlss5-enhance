import os
import unittest

from dlss5_enhance import i18n
from dlss5_enhance.i18n import (
    DEFAULT_LANGUAGE,
    MESSAGES,
    language,
    normalize_language,
    resolve_language,
    set_language,
    tr,
)


class CatalogTests(unittest.TestCase):
    def test_every_message_has_both_languages(self):
        missing = [
            key
            for key, entry in MESSAGES.items()
            if len(entry) != 2 or not entry[0].strip() or not entry[1].strip()
        ]
        self.assertEqual(missing, [])

    def test_keys_are_unique_and_prefixed(self):
        for key in MESSAGES:
            self.assertTrue(key.split(".")[0], key)
            self.assertNotIn(" ", key)

    def test_no_french_left_in_the_english_catalog(self):
        suspicious = {
            "é",
            "è",
            "ê",
            "à",
            "ç",
            "ù",
            "î",
            "ô",
            "û",
            "«",
        }
        offenders = [
            key
            for key, (english, _french) in MESSAGES.items()
            if any(char in english for char in suspicious)
        ]
        self.assertEqual(offenders, [])


class LanguageTests(unittest.TestCase):
    def tearDown(self):
        set_language(DEFAULT_LANGUAGE)

    def test_default_is_english(self):
        self.assertEqual(DEFAULT_LANGUAGE, "en")
        set_language("en")
        self.assertEqual(language(), "en")

    def test_normalize_accepts_locales(self):
        self.assertEqual(normalize_language("fr"), "fr")
        self.assertEqual(normalize_language("fr-FR"), "fr")
        self.assertEqual(normalize_language("en_US"), "en")
        self.assertEqual(normalize_language("FR"), "fr")
        self.assertIsNone(normalize_language("de"))
        self.assertIsNone(normalize_language(None))
        self.assertIsNone(normalize_language(""))

    def test_resolve_precedence(self):
        self.assertEqual(resolve_language("fr", "en"), "fr")
        self.assertEqual(resolve_language(None, "fr"), "fr")
        self.assertEqual(resolve_language("nope", "fr"), "fr")
        self.assertEqual(resolve_language("nope"), DEFAULT_LANGUAGE)

    def test_environment_is_the_last_resort(self):
        previous = os.environ.get("DLSS5_LANG")
        os.environ["DLSS5_LANG"] = "fr"
        try:
            self.assertEqual(resolve_language(), "fr")
            self.assertEqual(resolve_language("en"), "en")
        finally:
            if previous is None:
                os.environ.pop("DLSS5_LANG", None)
            else:
                os.environ["DLSS5_LANG"] = previous

    def test_switch_changes_the_message(self):
        set_language("en")
        english = tr("s.one_source")
        set_language("fr")
        french = tr("s.one_source")
        self.assertNotEqual(english, french)
        self.assertIn("exactly one source", english)
        self.assertIn("exactement une source", french)

    def test_unknown_key_returns_the_key(self):
        self.assertEqual(tr("nope.not.here"), "nope.not.here")

    def test_formatting_falls_back_when_arguments_are_missing(self):
        set_language("en")
        self.assertIn("{path}", tr("s.file_missing"))

    def test_missing_french_entry_falls_back_to_english(self):
        i18n.MESSAGES["test.only_english"] = ("Only English", "")
        try:
            set_language("fr")
            self.assertEqual(tr("test.only_english"), "Only English")
        finally:
            i18n.MESSAGES.pop("test.only_english", None)


if __name__ == "__main__":
    unittest.main()
