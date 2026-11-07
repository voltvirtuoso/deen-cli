"""The version lives in two files and the changelog; keep them in step."""
import re
import unittest
from pathlib import Path

import deen

ROOT = Path(__file__).resolve().parent.parent


def _pyproject_version():
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


class ReleaseConsistencyTests(unittest.TestCase):
    def test_package_and_pyproject_versions_match(self):
        self.assertEqual(deen.__version__, _pyproject_version())

    def test_changelog_has_a_heading_for_the_current_version(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(changelog, rf"(?m)^## \[{re.escape(deen.__version__)}\] - \d{{4}}-\d{{2}}-\d{{2}}")

    def test_no_unreleased_section_left_behind_at_release_time(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertNotIn("## [Unreleased]", changelog, "cut the release: rename [Unreleased] to the new version")


if __name__ == "__main__":
    unittest.main()
