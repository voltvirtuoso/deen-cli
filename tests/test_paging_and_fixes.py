"""Reading past the first page, and the data bugs found while checking the other flows."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from deen import content as content_module
from deen import database
from deen.__main__ import app
from deen.cli import _common
from deen.content import ContentEngine
from deen.errors import UserError
from deen.services.hadith import HadithMixin

from helpers import IsolatedHomeTestCase

ITEMS = [{"n": i} for i in range(1, 32)]  # 31 items -> 4 pages of 10


def _render(i, item):
    return f"item-{i}"


def _engine():
    return ContentEngine.__new__(ContentEngine)  # no config/network needed for paging


class NavigationTests(unittest.TestCase):
    def _run(self, keys, *, interactive=True, **kwargs):
        with patch.object(content_module, "is_interactive", return_value=interactive), patch.object(
            content_module, "read_nav_key", side_effect=keys
        ), patch.object(content_module, "page_text") as page_text:
            _engine()._page_through(ITEMS, "duas", _render, **kwargs)
        return [c.args[0] for c in page_text.call_args_list]

    def test_enter_walks_through_every_page_then_stops(self):
        shown = self._run(["next", "next", "next", "next"])
        self.assertEqual(len(shown), 4)
        self.assertIn("item-1\n", shown[0])
        self.assertIn("item-31", shown[3])  # the 31st item is only reachable past page 3
        self.assertNotIn("item-11", shown[0])

    def test_quit_stops_early(self):
        self.assertEqual(len(self._run(["quit"])), 1)

    def test_previous_goes_back_one_page(self):
        shown = self._run(["next", "prev", "quit"])
        self.assertEqual(len(shown), 3)
        self.assertIn("page 1/4", shown[2])

    def test_previous_on_first_page_stays_put(self):
        shown = self._run(["prev", "quit"])
        self.assertEqual(len(shown), 2)
        self.assertIn("page 1/4", shown[1])

    def test_page_flag_is_only_the_starting_point(self):
        shown = self._run(["next", "next"], page=3)
        self.assertEqual(len(shown), 2)
        self.assertIn("page 3/4", shown[0])
        self.assertIn("page 4/4", shown[1])

    def test_not_a_terminal_prints_just_the_requested_page(self):
        shown = self._run([], interactive=False, page=2)
        self.assertEqual(len(shown), 1)
        self.assertIn("page 2/4", shown[0])
        self.assertIn("--all", shown[0])  # tells scripts how to get everything

    def test_single_page_never_prompts(self):
        with patch.object(content_module, "is_interactive", return_value=True), patch.object(
            content_module, "read_nav_key", side_effect=AssertionError("must not prompt")
        ), patch.object(content_module, "page_text") as page_text:
            _engine()._page_through(ITEMS[:5], "duas", _render)
        self.assertEqual(page_text.call_count, 1)

    def test_all_shows_every_item_in_one_view(self):
        shown = self._run([], show_all=True)
        self.assertEqual(len(shown), 1)
        for i in (1, 10, 11, 31):
            self.assertIn(f"item-{i}", shown[0])


class PageErrorTests(unittest.TestCase):
    def test_out_of_range_page_is_a_user_error_with_the_range(self):
        with self.assertRaises(UserError) as ctx:
            _engine()._page_through(ITEMS, "duas", _render, page=9)
        self.assertIn("1-4", str(ctx.exception))

    def test_bad_page_and_per_page_are_user_errors(self):
        for kwargs in ({"page": 0}, {"per_page": 0}):
            with self.assertRaises(UserError):
                _engine()._page_through(ITEMS, "duas", _render, **kwargs)

    def test_out_of_range_page_shows_as_a_yellow_warning_not_a_red_error(self):
        engine = Mock()
        engine.display_dua_list.side_effect = UserError("--page 9 is outside the available range 1-4")
        with patch.object(_common, "_config", Mock(is_initialized=True)), patch(
            "deen.cli.dua.ContentEngine", return_value=engine
        ):
            r = CliRunner().invoke(app, ["dua", "read", "27", "--page", "9"])
        self.assertEqual(r.exit_code, 1)
        self.assertIn("outside the available range", r.stdout)
        self.assertNotIn("✗ Error", r.stdout)


class AllFlagTests(unittest.TestCase):
    def test_all_flag_is_forwarded_by_every_read_command_and_alias(self):
        cases = [
            (["dua", "read", "27", "--all"], "deen.cli.dua.ContentEngine", "display_dua_list"),
            (["quran", "read", "1", "-a"], "deen.cli.quran.ContentEngine", "display_ayah_list"),
            (["hadith", "read", "bukhari", "--all"], "deen.cli.hadith.ContentEngine", "display_hadith_list"),
            (["read-surah", "1", "--all"], "deen.cli.quran.ContentEngine", "display_ayah_list"),
            (["read-dua", "-c", "27", "--all"], "deen.cli.dua.ContentEngine", "display_dua_list"),
            (["read-hadith", "-c", "bukhari", "--all"], "deen.cli.hadith.ContentEngine", "display_hadith_list"),
        ]
        for argv, target, method in cases:
            with self.subTest(argv=argv):
                engine = Mock()
                with patch.object(_common, "_config", Mock(is_initialized=True)), patch(target, return_value=engine):
                    r = CliRunner().invoke(app, argv)
                self.assertEqual(r.exit_code, 0, r.stdout)
                self.assertTrue(getattr(engine, method).call_args.kwargs["show_all"])


class HabitDataTests(IsolatedHomeTestCase):
    def setUp(self):
        super().setUp()
        database._SCHEMA_CHECKED = False
        database.init_db()

    def test_afternoon_is_asr_not_dhuhr(self):
        self.assertEqual(database.normalize_prayer_name("afternoon"), "Asr")
        self.assertEqual(database.normalize_prayer_name("at noon"), "Dhuhr")
        self.assertEqual(database.normalize_prayer_name("Zuhr, on time"), "Dhuhr")
        self.assertIsNone(database.normalize_prayer_name("on time"))
        self.assertIsNone(database.normalize_prayer_name("fajrx"))  # whole words only

    def test_recent_commits_include_the_cutoff_day(self):
        # One minute after the cutoff, one day ago: must be inside --days 1.
        stamp = (datetime.now() - timedelta(days=1) + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
        with database.get_db() as conn:
            conn.execute("INSERT INTO commits (habit_id, note, timestamp) VALUES (1, 'edge', ?)", (stamp,))
        self.assertIn("edge", [row[3] for row in database.get_recent_commits(1)])

    def test_old_commits_stay_out(self):
        stamp = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        with database.get_db() as conn:
            conn.execute("INSERT INTO commits (habit_id, note, timestamp) VALUES (1, 'old', ?)", (stamp,))
        self.assertNotIn("old", [row[3] for row in database.get_recent_commits(1)])

    def test_todays_prayer_count_counts_todays_prayers(self):
        database.commit_habit("Fajr", "x")
        self.assertEqual(database.get_today_prayer_count(), {"Fajr": 1})


class HadithGradeTests(unittest.TestCase):
    def test_uses_the_sources_own_grade_list(self):
        h = {"grades": [{"name": "Al-Albani", "grade": "Hasan"}]}
        self.assertEqual(HadithMixin._grade_of(h, "tirmidhi"), "Hasan")

    def test_never_guesses_hasan_for_ungraded_non_sahih_collections(self):
        self.assertEqual(HadithMixin._grade_of({}, "abudawud"), "Ungraded")
        self.assertEqual(HadithMixin._grade_of({}, "ibnmajah"), "Ungraded")

    def test_bukhari_and_muslim_are_sahih_by_definition(self):
        self.assertEqual(HadithMixin._grade_of({}, "bukhari"), "Sahih")
        self.assertEqual(HadithMixin._grade_of({}, "muslim"), "Sahih")

    def test_daif_is_kept_as_daif(self):
        self.assertEqual(HadithMixin._grade_of({"grades": [{"grade": "Da'if"}]}, "ibnmajah"), "Da'if")


if __name__ == "__main__":
    unittest.main()
