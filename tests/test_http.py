import unittest
from unittest.mock import Mock, patch

import httpx

from deen import http


def _resp(status):
    r = Mock(status_code=status)
    r.request = Mock()
    r.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError("bad", request=r.request, response=r) if status >= 400 else None
    )
    return r


class HttpGetTests(unittest.TestCase):
    def test_sets_user_agent_and_follows_redirects(self):
        with patch.object(http.httpx, "get", return_value=_resp(200)) as get:
            http.http_get("https://x.test")
        kwargs = get.call_args.kwargs
        self.assertTrue(kwargs["follow_redirects"])
        self.assertIn("deen-cli", kwargs["headers"]["User-Agent"])

    def test_retries_5xx_then_succeeds(self):
        with patch.object(http.httpx, "get", side_effect=[_resp(503), _resp(200)]) as get, patch.object(
            http.time, "sleep"
        ):
            http.http_get("https://x.test", max_retries=2)
        self.assertEqual(get.call_count, 2)

    def test_4xx_fails_fast_without_retry(self):
        with patch.object(http.httpx, "get", return_value=_resp(404)) as get, patch.object(http.time, "sleep"):
            with self.assertRaises(httpx.HTTPStatusError):
                http.http_get("https://x.test", max_retries=2)
        self.assertEqual(get.call_count, 1)

    def test_zero_retries_raises_after_one_attempt(self):
        with patch.object(http.httpx, "get", side_effect=httpx.ConnectError("down")) as get:
            with self.assertRaises(httpx.ConnectError):
                http.http_get("https://x.test", max_retries=0)
        self.assertEqual(get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
