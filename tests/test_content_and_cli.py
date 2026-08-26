import inspect
import unittest
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from deen.arabic import prepare_arabic
from deen.__main__ import app, inspire
from deen.content import ContentEngine


class ArabicRenderingTests(unittest.TestCase):
    def test_prepare_arabic_shapes_and_reorders_logical_text(self):
        logical = "الفاتحة"
        rendered = prepare_arabic(logical)

        self.assertTrue(rendered)
        self.assertNotEqual(rendered, logical)

    def test_prepare_arabic_repairs_literal_unicode_escapes(self):
        self.assertEqual(
            prepare_arabic(r"\u0627\u0644\u0641\u0627\u062a\u062d\u0629"),
            prepare_arabic("الفاتحة"),
        )

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
        self.assertTrue({"read-surah", "read-hadith", "read-dua", "hadith-categories"}.issubset(names))

    def test_read_surah_accepts_positional_number(self):
        engine = Mock()
        with patch("deen.__main__.DeenConfig") as config_cls, patch(
            "deen.__main__.ContentEngine", return_value=engine
        ):
            config_cls.return_value.is_initialized = True
            result = CliRunner().invoke(app, ["read-surah", "101", "--per-page", "5"])

        self.assertEqual(result.exit_code, 0, result.stdout)
        engine.display_ayah_list.assert_called_once_with("101", page=1, per_page=5)

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

    def test_hadith_help_exposes_search_category_number_and_paging(self):
        result = CliRunner().invoke(app, ["read-hadith", "--help"])
        self.assertEqual(result.exit_code, 0, result.stdout)
        for flag in ("--search", "--category", "--number", "--page", "--per-page"):
            self.assertIn(flag, result.stdout)


class ReaderOutputTests(unittest.TestCase):
    def test_pager_prefers_less_with_utf8_input(self):
        from deen import pager

        stdout = Mock(isatty=lambda: True)
        stdin = Mock(isatty=lambda: True)
        completed = Mock(returncode=0)
        with patch.object(pager.sys, "stdout", stdout), patch.object(
            pager.sys, "stdin", stdin
        ), patch.object(
            pager.shutil, "which", side_effect=lambda name: "less.exe" if name == "less" else None
        ), patch.object(pager.subprocess, "run", return_value=completed) as run:
            pager.page_text("Arabic — الفاتحة")

        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["input"], "Arabic — الفاتحة")
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.args[0][0], "less.exe")

    def test_pager_writes_directly_when_output_is_redirected(self):
        from deen import pager

        stdout = Mock(isatty=lambda: False)
        stdin = Mock(isatty=lambda: False)
        with patch.object(pager.sys, "stdout", stdout), patch.object(
            pager.sys, "stdin", stdin
        ), patch.object(pager.subprocess, "run") as run:
            pager.page_text("Arabic — الفاتحة")

        run.assert_not_called()
        stdout.write.assert_called_once_with("Arabic — الفاتحة")

    def test_page_through_does_not_use_legacy_system_pager(self):
        from deen import content as content_module

        engine = ContentEngine.__new__(ContentEngine)
        with patch.object(content_module, "console") as console_mock, patch.object(
            content_module, "page_text"
        ) as page_text_mock:
            engine._page_through([{"id": 1}], "items", lambda i, item: f"item {i}")

        console_mock.pager.assert_not_called()
        page_text_mock.assert_called_once()


class HadithFilteringTests(unittest.TestCase):
    def test_filters_by_search_category_and_exact_number(self):
        hadiths = [
            {"id": "1", "text": "Prayer is the key to Paradise", "narrator": "Abu Hurairah", "reference": "Bukhari 1", "section_number": "8", "section_name": "Prayers (Salat)"},
            {"id": "2", "text": "The reward of deeds depends upon intentions", "narrator": "Umar", "reference": "Bukhari 2", "section_number": "2", "section_name": "Belief"},
            {"id": "3", "text": "Prayer times are established", "narrator": "Ibn Umar", "reference": "Bukhari 3", "section_number": "8", "section_name": "Prayers (Salat)"},
        ]

        by_search = ContentEngine.filter_hadiths(hadiths, search="intentions")
        self.assertEqual([item["id"] for item in by_search], ["2"])

        by_category = ContentEngine.filter_hadiths(hadiths, category="prayers")
        self.assertEqual([item["id"] for item in by_category], ["1", "3"])

        by_number = ContentEngine.filter_hadiths(hadiths, number="3")
        self.assertEqual([item["id"] for item in by_number], ["3"])


if __name__ == "__main__":
    unittest.main()
