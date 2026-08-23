from __future__ import annotations

import json
import string
import tempfile
import unittest
from pathlib import Path

from recording_agent_hub import app
from recording_agent_hub.i18n import EN, LANGUAGE_NAMES, TRANSLATIONS, translate


def format_fields(value: str) -> set[str]:
    return {field for _, field, _, _ in string.Formatter().parse(value) if field}


class TranslationTests(unittest.TestCase):
    def test_every_language_has_every_interface_key_and_matching_placeholders(self) -> None:
        self.assertEqual(set(LANGUAGE_NAMES), set(TRANSLATIONS))
        for language, catalog in TRANSLATIONS.items():
            self.assertEqual(set(EN), set(catalog), language)
            for key, english in EN.items():
                self.assertEqual(format_fields(english), format_fields(catalog[key]), f"{language}:{key}")

    def test_unknown_language_and_key_have_safe_fallbacks(self) -> None:
        self.assertEqual(translate("unknown", "pause"), "Pause execution")
        self.assertEqual(translate("en", "unknown_key"), "unknown_key")

    def test_language_setting_is_migrated_to_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config = app.default_config()
            config.pop("ui_language")
            config_path.write_text(json.dumps(config), encoding="utf-8")
            loaded = app.load_config(config_path)
            self.assertEqual(loaded["ui_language"], "zh_CN")
            self.assertEqual(json.loads(config_path.read_text(encoding="utf-8"))["ui_language"], "zh_CN")


if __name__ == "__main__":
    unittest.main()
