from unittest.mock import Mock, patch

from typer.testing import CliRunner

from deen.__main__ import app
from deen.cache import Fetched
from deen.cli import _common
from deen.services.dua import search_dua_categories

import unittest

# Titles copied from the Hisn al-Muslim chapter index (sunnah.com/hisn).
CATEGORIES = [
    {"number": "8", "en": "Before ablution", "ar": "الذكر قبل الوضوء"},
    {"number": "9", "en": "Upon completing the ablution", "ar": "الذكر بعد الفراغ من الوضوء"},
    {"number": "15", "en": "Concerning the athan (the call to prayer)", "ar": "أذكار الأذان"},
    {"number": "26", "en": "For seeking guidance in forming a decision or choosing the proper course", "ar": "دعاء صلاة الاستخارة"},
    {"number": "27", "en": "In the morning and evening", "ar": "أذكار الصباح والمساء"},
    {"number": "44", "en": "Upon committing a sin", "ar": "ما يقول ويفعل من أذنب ذنباً"},
]
DATA = {"shortcuts": ["morning", "evening", "forgiveness"], "categories": CATEGORIES}


def _numbers(query):
    return [c["number"] for c in search_dua_categories(CATEGORIES, query)]


class SearchTests(unittest.TestCase):
    def test_istikhara_finds_the_guidance_chapter_even_though_english_title_lacks_the_word(self):
        self.assertEqual(_numbers("istikhara"), ["26"])
        self.assertEqual(_numbers("Istikharah"), ["26"])

    def test_arabic_title_and_number_and_plain_english(self):
        self.assertEqual(_numbers("الاستخارة"), ["26"])
        self.assertEqual(_numbers("26"), ["26"])
        self.assertEqual(_numbers("sin"), ["44"])  # not "choosing" in chapter 26

    def test_transliterated_names_map_to_titles(self):
        self.assertEqual(_numbers("wudu"), ["8", "9"])
        self.assertEqual(_numbers("adhan"), ["15"])

    def test_blank_and_unknown(self):
        self.assertEqual(_numbers("   "), [])
        self.assertEqual(_numbers("zzz"), [])


class ResolveCliTests(unittest.TestCase):
    def _invoke(self, argv, data=DATA):
        api = Mock()
        api.fetch_dua_categories.return_value = Fetched(data)
        engine = Mock()
        with patch.object(_common, "_config", Mock(is_initialized=True)), patch(
            "deen.cli.dua.ApiService", return_value=api
        ), patch("deen.cli.dua.ContentEngine", return_value=engine), patch(
            "deen.cli.inspire.ContentEngine", return_value=engine
        ):
            return CliRunner().invoke(app, argv), engine

    def test_read_by_name_resolves_to_the_chapter_number(self):
        result, engine = self._invoke(["dua", "read", "istikhara"])
        self.assertEqual(result.exit_code, 0, result.stdout)
        self.assertEqual(engine.display_dua_list.call_args.args[0], "26")
        self.assertIn("seeking guidance", result.stdout)

    def test_numbers_and_shortcuts_pass_straight_through(self):
        for given in ("26", "forgiveness", "morning"):
            result, engine = self._invoke(["dua", "read", given])
            self.assertEqual(engine.display_dua_list.call_args.args[0], given)

    def test_random_by_name(self):
        result, engine = self._invoke(["dua", "random", "istikhara"])
        self.assertEqual(engine.display_content.call_args.kwargs["category"], "26")

    def test_inspire_dua_category_by_name(self):
        result, engine = self._invoke(["inspire", "-t", "dua", "-c", "istikhara"])
        self.assertEqual(engine.display_content.call_args.kwargs["category"], "26")

    def test_ambiguous_name_lists_choices_and_exits_nonzero(self):
        result, engine = self._invoke(["dua", "read", "ablution"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("matches 2 categories", result.stdout)
        engine.display_dua_list.assert_not_called()

    def test_unknown_name_is_a_clear_error(self):
        result, engine = self._invoke(["dua", "read", "zzz"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("No dua category matches", result.stdout)

    def test_offline_with_no_category_list_passes_the_name_through(self):
        result, engine = self._invoke(["dua", "read", "istikhara"], data={"shortcuts": [], "categories": []})
        self.assertEqual(engine.display_dua_list.call_args.args[0], "istikhara")

    def test_list_search_filters_the_table(self):
        result, _ = self._invoke(["dua", "list", "--search", "istikhara"])
        self.assertEqual(result.exit_code, 0, result.stdout)
        self.assertIn("seeking guidance", result.stdout)
        self.assertNotIn("morning and evening", result.stdout)

    def test_list_search_with_no_match_says_so(self):
        result, _ = self._invoke(["dua", "list", "--search", "zzz"])
        self.assertIn("No category matches", result.stdout)


if __name__ == "__main__":
    unittest.main()
