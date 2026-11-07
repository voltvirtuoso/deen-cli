import json
import unittest
from unittest.mock import Mock

from deen import database
from deen.cache import Cache, Fetched, fetch_live_first, get_or_fetch
from deen.services.api import ApiService

from helpers import FakeConfig, IsolatedHomeTestCase


def _json_resp(payload):
    r = Mock()
    r.json.return_value = payload
    return r


class CacheStrategyTests(IsolatedHomeTestCase):
    def test_get_or_fetch_live_then_cache_hit(self):
        cache = Cache("t")
        fn = Mock(return_value={"a": 1})
        self.assertEqual(get_or_fetch(cache, "k", 60, fn), Fetched({"a": 1}))
        self.assertEqual(get_or_fetch(cache, "k", 60, fn), Fetched({"a": 1}))
        fn.assert_called_once()

    def test_get_or_fetch_serves_stale_when_live_fails(self):
        cache = Cache("t")
        cache.set("k", "old")
        # ttl=-1 makes the entry expired immediately
        result = get_or_fetch(cache, "k", -1, Mock(side_effect=RuntimeError("down")))
        self.assertEqual(result, Fetched("old", is_stale=True))

    def test_get_or_fetch_nothing_available(self):
        result = get_or_fetch(Cache("t"), "k", 60, Mock(return_value=None))
        self.assertFalse(result.ok)

    def test_live_first_never_serves_fresh_cache(self):
        cache = Cache("t")
        fn = Mock(side_effect=["one", "two"])
        self.assertEqual(fetch_live_first(cache, "k", fn).data, "one")
        self.assertEqual(fetch_live_first(cache, "k", fn).data, "two")

    def test_live_first_falls_back_to_last_good(self):
        cache = Cache("t")
        fetch_live_first(cache, "k", Mock(return_value="good"))
        result = fetch_live_first(cache, "k", Mock(side_effect=RuntimeError("down")))
        self.assertEqual(result, Fetched("good", is_stale=True))


class ServiceTests(IsolatedHomeTestCase):
    def setUp(self):
        super().setUp()
        self.api = ApiService(FakeConfig())

    def test_random_ayah_shape(self):
        payload = {"data": [
            {"edition": {"identifier": "quran-uthmani"}, "text": "AR", "numberInSurah": 5, "surah": {"number": 94, "englishName": "Ash-Sharh"}},
            {"edition": {"identifier": "en.sahih"}, "text": "EN"},
            {"edition": {"identifier": "en.transliteration"}, "text": "TR"},
        ]}
        self.api._get = Mock(return_value=_json_resp(payload))
        ayah = self.api.fetch_random_ayah()
        self.assertEqual(ayah["id"], "94:5")
        self.assertEqual((ayah["arabic"], ayah["translation"], ayah["transliteration"]), ("AR", "EN", "TR"))

    def test_surah_rejects_out_of_range(self):
        self.api._get = Mock()
        self.assertIsNone(self.api.fetch_ayahs_by_surah("115"))
        self.assertIsNone(self.api.fetch_ayahs_by_surah("abc"))
        self.api._get.assert_not_called()

    def test_surah_list_failure_is_not_ok(self):
        self.api._get = Mock(side_effect=RuntimeError("down"))
        self.assertFalse(self.api.fetch_surah_list().ok)

    def test_dua_categories_offline_marker(self):
        self.api._get = Mock(side_effect=RuntimeError("down"))
        result = self.api.fetch_dua_categories()
        self.assertTrue(result.is_offline)
        self.assertIn("morning", result.data["shortcuts"])

    def test_prayer_times_trimmed_and_stale_flag(self):
        timings = {k: f"{h:02d}:00 (PKT)" for h, k in enumerate(["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"], 5)}
        self.api._get = Mock(return_value=_json_resp({"data": {"timings": timings}}))
        result = self.api.fetch_prayer_times(31.5, 74.3, "2026-01-01")
        self.assertEqual(result.data["Fajr"], "05:00")
        self.assertFalse(result.is_stale)

    def test_hadith_collection_fetched_once_for_all_helpers(self):
        eng = {"metadata": {"sections": {"1": "Revelation"}, "section_details": {"1": {"hadithnumber_first": 1, "hadithnumber_last": 7}}},
               "hadiths": [{"hadithnumber": 1, "text": "Deeds are by intentions", "reference": {"book": 1}}]}

        def fake_get(url, **kw):
            if "eng-bukhari" in url:
                return _json_resp(eng)
            raise RuntimeError("no arabic edition")

        self.api._get = Mock(side_effect=fake_get)
        cats = self.api.fetch_hadith_categories("bukhari")
        self.assertEqual(cats[0]["name"], "Revelation")
        hadiths = self.api.fetch_hadiths_list("bukhari")
        self.assertEqual(hadiths[0]["section_name"], "Revelation")
        self.assertEqual(hadiths[0]["reference"], "Bukhari 1")
        english_calls = [c for c in self.api._get.call_args_list if "eng-bukhari" in c.args[0]]
        self.assertEqual(len(english_calls), 1)

    def test_mood_match_flag(self):
        eng = {"hadiths": [{"hadithnumber": 1, "text": "Be grateful and give thanks"}]}
        self.api._get = Mock(side_effect=lambda url, **kw: _json_resp(eng) if "eng-" in url else (_ for _ in ()).throw(RuntimeError()))
        h = self.api.fetch_random_hadith(mood="grateful", collection="bukhari")
        self.assertTrue(h["mood_matched"])


class OfflineFallbackTests(IsolatedHomeTestCase):
    def setUp(self):
        super().setUp()
        database.init_db()
        self.api = ApiService(FakeConfig(**{"cache.enable": False}))
        self.api._get = Mock(side_effect=RuntimeError("network down"))

    def test_every_content_type_has_an_offline_fallback(self):
        self.assertTrue(self.api.fetch_random_ayah()["translation"])
        self.assertTrue(self.api.fetch_random_hadith()["text"])
        dua = self.api.fetch_random_dua()
        self.assertTrue(dua["translation"])
        self.assertEqual(set(dua), {"arabic", "translation", "transliteration", "source", "category"})

    def test_offline_hadith_list(self):
        self.assertTrue(self.api.fetch_hadiths_list("bukhari"))

    def test_unknown_dua_category_falls_back_to_any_dua(self):
        self.assertIsNotNone(self.api.fetch_random_dua("no-such-category-xyz"))


if __name__ == "__main__":
    unittest.main()
