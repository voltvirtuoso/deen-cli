"""Guard rails: fail the build when someone reintroduces a second way of doing a thing.

If one of these fails, the fix is almost never to edit the test -- it's to use
the shared helper named in the message. See "Conventions" in the README.
"""
import re
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "deen"


def _sources():
    for path in PKG.rglob("*.py"):
        yield path.relative_to(PKG).as_posix(), path.read_text(encoding="utf-8")


def _offenders(pattern, allowed):
    rx = re.compile(pattern)
    return [
        f"{name}:{i}"
        for name, text in _sources()
        if name not in allowed
        for i, line in enumerate(text.splitlines(), 1)
        if rx.search(line) and not line.lstrip().startswith("#")
    ]


class ConventionTests(unittest.TestCase):
    def test_http_only_via_http_get(self):
        bad = _offenders(r"\bhttpx\.(get|post|request|Client|AsyncClient)\b", {"http.py"})
        self.assertEqual(bad, [], "use deen.http.http_get instead of calling httpx directly")

    def test_single_console(self):
        bad = _offenders(r"\bConsole\(", {"ui.py"})
        self.assertEqual(bad, [], "import `console` from deen.ui instead of creating a Console")

    def test_config_is_not_constructed_ad_hoc(self):
        # get_config() owns the instance; ContentEngine accepts one but may default it.
        bad = _offenders(r"\bDeenConfig\(\)", {"cli/_common.py", "content.py", "config.py"})
        self.assertEqual(bad, [], "use deen.cli._common.get_config() / pass the config in")

    def test_commands_go_through_the_guard(self):
        bad = _offenders(r"@(app|config_app)\.command\(", {"cli/app.py"})
        self.assertEqual(bad, [], "register commands with @command(...) from deen.cli.app")

    def test_no_raw_sql_in_cli_or_services(self):
        bad = _offenders(r"\b(SELECT|INSERT INTO|UPDATE \w+ SET|DELETE FROM)\b", {"database.py"})
        self.assertEqual(bad, [], "SQL belongs in deen/database.py")

    def test_database_layer_is_free_of_ui_and_network(self):
        bad = _offenders(r"^\s*(from|import)\s+(\.services|rich|httpx|\.cli|\.ui)\b", {n for n, _ in _sources() if n != "database.py"})
        self.assertEqual(bad, [], "database.py must not import services, rich, httpx or cli: take callbacks instead")

    def test_no_hand_rolled_stale_cache_fallbacks(self):
        bad = _offenders(r"\.get_stale\(", {"cache.py"})
        self.assertEqual(bad, [], "use get_or_fetch / fetch_live_first from deen.cache")


if __name__ == "__main__":
    unittest.main()
