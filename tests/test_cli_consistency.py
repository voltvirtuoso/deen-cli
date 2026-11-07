import unittest
from unittest.mock import Mock, patch

import typer
from typer.testing import CliRunner

from deen import database
from deen.__main__ import app
from deen.cli import _common
from deen.cli._common import guard
from deen.errors import UserError

from helpers import IsolatedHomeTestCase

# command line -> must refuse to run before `deen init`
NEEDS_INIT = [
    ["status"],
    ["commit", "-m", "x"],
    ["log"],
    ["inspire"],
    ["quran", "list"],
    ["quran", "read", "1"],
    ["quran", "random"],
    ["hadith", "list"],
    ["hadith", "read", "bukhari"],
    ["hadith", "random"],
    ["dua", "list"],
    ["dua", "read", "morning"],
    ["dua", "random"],
    # deprecated aliases must obey the same rule
    ["surahs"],
    ["read-surah", "1"],
    ["read-hadith", "-c", "bukhari"],
    ["read-dua", "-c", "morning"],
    ["hadith-categories", "-c", "bukhari"],
    ["categories"],
]
# these work on a fresh install
NO_INIT_NEEDED = [["config", "path"], ["config", "show"], ["--version"]]


class InitGuardTests(IsolatedHomeTestCase):
    def setUp(self):
        super().setUp()
        _common.reset_config()
        self.addCleanup(_common.reset_config)

    def test_every_command_refuses_before_init(self):
        for argv in NEEDS_INIT:
            with self.subTest(argv=argv):
                result = CliRunner().invoke(app, argv)
                self.assertEqual(result.exit_code, 1, result.stdout)
                self.assertIn("deen init", result.stdout)

    def test_config_and_version_work_before_init(self):
        for argv in NO_INIT_NEEDED:
            with self.subTest(argv=argv):
                result = CliRunner().invoke(app, argv)
                self.assertEqual(result.exit_code, 0, result.stdout)

    def test_every_registered_command_is_covered_by_one_list_or_the_other(self):
        groups = {g.name: g.typer_instance for g in app.registered_groups}

        def name_of(c):
            return c.name or c.callback.__name__.replace("_", "-")

        registered = {(name_of(c),) for c in app.registered_commands}
        for gname, inst in groups.items():
            registered |= {(gname, name_of(c)) for c in inst.registered_commands}

        def key(argv):
            return tuple(argv[:2]) if argv[0] in groups else (argv[0],)

        covered = {key(a) for a in NEEDS_INIT + NO_INIT_NEEDED} | {("init",)}
        missing = {k for k in registered - covered if k[0] != "config"}  # config * is checked below
        self.assertEqual(missing, set(), "new command: add it to NEEDS_INIT or NO_INIT_NEEDED")

    def test_content_groups_all_have_the_same_verbs(self):
        verbs = {
            g.name: {c.name for c in g.typer_instance.registered_commands}
            for g in app.registered_groups
            if g.name in ("quran", "hadith", "dua")
        }
        for name, v in verbs.items():
            self.assertEqual(v, {"list", "read", "random"}, name)


class GuardTests(unittest.TestCase):
    def _run(self, fn):
        wrapped = guard(fn, requires_init=False)
        with patch.object(_common, "console") as con:
            with self.assertRaises(typer.Exit) as ctx:
                wrapped()
        return ctx.exception.exit_code, " ".join(str(c.args[0]) for c in con.print.call_args_list)

    def test_user_error_is_a_warning_with_exit_1(self):
        def boom():
            raise UserError("nope")
        code, out = self._run(boom)
        self.assertEqual(code, 1)
        self.assertIn("nope", out)
        self.assertIn("yellow", out)

    def test_unexpected_error_is_red_with_exit_1(self):
        def boom():
            raise RuntimeError("kaput")
        code, out = self._run(boom)
        self.assertEqual(code, 1)
        self.assertIn("✗ Error: kaput", out)

    def test_typer_exit_passes_through_untouched(self):
        def bye():
            raise typer.Exit(0)
        self.assertEqual(self._run(bye)[0], 0)

    def test_signature_is_preserved_for_typer(self):
        import inspect
        def f(a: int, b: str = "x"): ...
        self.assertEqual(list(inspect.signature(guard(f)).parameters), ["a", "b"])


class HabitFlowTests(IsolatedHomeTestCase):
    """commit -> log end to end against a real temp database."""

    def setUp(self):
        super().setUp()
        _common.reset_config()
        self.addCleanup(_common.reset_config)
        cfg = _common.get_config()
        cfg.set("user.name", "T")
        cfg.set("user.location", "Lahore")
        cfg.set("prayer.calculation_method", "1")
        cfg.set("prayer.school", "1")
        database.init_db()

    def test_commit_then_log(self):
        r = CliRunner().invoke(app, ["commit", "-t", "quran", "-m", "Juz 1"])
        self.assertEqual(r.exit_code, 0, r.stdout)
        self.assertIn("Quran committed", r.stdout)
        r = CliRunner().invoke(app, ["log"])
        self.assertEqual(r.exit_code, 0, r.stdout)
        self.assertIn("Juz 1", r.stdout)

    def test_makeup_marker_renders_instead_of_leaking_markup(self):
        CliRunner().invoke(app, ["commit", "-t", "dhikr", "-m", "x", "--makeup"])
        out = CliRunner().invoke(app, ["log"]).stdout
        self.assertIn("(M)", out)
        self.assertNotIn("[yellow]", out)

    def test_accepted_overwrite_updates_the_same_commit(self):
        runner = CliRunner()
        first = runner.invoke(app, ["commit", "-t", "salah", "-m", "Fajr"])
        with patch("deen.cli.habits.Confirm.ask", return_value=True):
            second = runner.invoke(app, ["commit", "-t", "salah", "-m", "Fajr (updated)"])
        self.assertEqual(second.exit_code, 0, second.stdout)
        self.assertEqual(
            [l for l in first.stdout.split() if l.isdigit()][:1], [l for l in second.stdout.split() if l.isdigit()][:1]
        )

    def test_declined_duplicate_prayer_is_a_nonzero_warning(self):
        runner = CliRunner()
        runner.invoke(app, ["commit", "-t", "salah", "-m", "Fajr"])
        with patch("deen.cli.habits.Confirm.ask", return_value=False):
            r = runner.invoke(app, ["commit", "-t", "salah", "-m", "Fajr"])
        self.assertEqual(r.exit_code, 1, r.stdout)
        self.assertIn("cancelled", r.stdout)


if __name__ == "__main__":
    unittest.main()
