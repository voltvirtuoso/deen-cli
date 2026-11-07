"""Shared test helpers: an isolated HOME/cache and a dict-backed fake config."""
import os
import tempfile
import unittest
from unittest.mock import patch


class FakeConfig:
    def __init__(self, **values):
        self._v = {
            "api.quran_base_url": "https://quran.test",
            "api.hadith_base_url": "https://hadith.test",
            "api.dua_base_url": "https://dua.test",
            "api.aladhan_base_url": "https://aladhan.test",
            "cache.enable": True,
            **values,
        }
        self.is_initialized = True

    def get(self, key, default=None):
        return self._v.get(key, default)


class IsolatedHomeTestCase(unittest.TestCase):
    """Point HOME and the XDG dirs at a temp dir so tests never touch real user data."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = self._tmp.name
        env = {"HOME": root, "USERPROFILE": root, "XDG_CACHE_HOME": f"{root}/cache", "XDG_STATE_HOME": f"{root}/state"}
        self._env = patch.dict(os.environ, env)
        self._env.start()
        os.makedirs(f"{root}/.deen", exist_ok=True)
        self.addCleanup(self._env.stop)
        self.addCleanup(self._tmp.cleanup)
