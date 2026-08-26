import inspect
import unittest
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from deen.arabic import prepare_arabic
from deen.__main__ import app, inspire


class ArabicRenderingTests(unittest.TestCase):
    def test_prepare_arabic_shapes_and_reorders_logical_text(self):
        logical = "الفاتحة"
        rendered = prepare_arabic(logical)

        self.assertTrue(rendered)
        self.assertNotEqual(rendered, logical)

    def test_surah_listing_uses_shared_arabic_parser(self):
        api = Mock()
        api.fetch_surah_list.return_value = (
            [
                {
                    "number": 1,
                    "name": "الفاتحة",
                    "englishName": "Al-Faatiha",
                    "englishNameTranslation": "The Opening",
                    "numberOfAyahs": 7,
                }
            ],
            False,
        )

        with patch("deen.__main__.ApiService", return_value=api):
            result = CliRunner().invoke(app, ["surahs"])

        self.assertEqual(result.exit_code, 0, result.stdout)
        self.assertIn(prepare_arabic("الفاتحة"), result.stdout)


class CommandSeparationTests(unittest.TestCase):
    def test_inspire_has_no_full_list_option(self):
        self.assertNotIn("list_all", inspect.signature(inspire).parameters)

    def test_dedicated_read_commands_are_registered(self):
        names = {
            command.name or command.callback.__name__
            for command in app.registered_commands
        }
        self.assertTrue({"read-surah", "read-hadith", "read-dua"}.issubset(names))

    def test_read_commands_expose_required_specific_flags(self):
        runner = CliRunner()
        for command, flag in (
            ("read-surah", "--surah"),
            ("read-hadith", "--collection"),
            ("read-dua", "--category"),
        ):
            result = runner.invoke(app, [command, "--help"])
            self.assertEqual(result.exit_code, 0, result.stdout)
            self.assertIn(flag, result.stdout)

    def test_inspire_help_does_not_advertise_full_list_mode(self):
        result = CliRunner().invoke(app, ["inspire", "--help"])
        self.assertEqual(result.exit_code, 0, result.stdout)
        self.assertNotIn("--list", result.stdout)


if __name__ == "__main__":
    unittest.main()
