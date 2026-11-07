"""The single place deen-cli makes outbound HTTP requests.

Every service (Quran, Hadith, Dua, Prayer, Location, Metadata) goes through
:func:`http_get` so retry, redirect, timeout and User-Agent behaviour is
identical everywhere. Do not call ``httpx.get`` directly elsewhere.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("deen.http")

USER_AGENT = "deen-cli/0.1 (https://github.com/voltvirtuoso/deen-cli)"
DEFAULT_TIMEOUT = 10.0


def http_get(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = 2,
    **kwargs: Any,
) -> httpx.Response:
    """GET ``url`` with a small retry/backoff for transient failures.

    Retries only on connection/timeout errors and 5xx responses; 4xx errors
    fail fast because retrying won't help. Redirects are followed (httpx
    does not do this by default, and a moved endpoint would otherwise fail
    silently and fall back to stale cache). Pass ``max_retries=0`` for
    best-effort calls where a caller already has its own fallback chain
    (e.g. trying several geolocation providers in turn).
    """
    kwargs.setdefault("follow_redirects", True)
    headers = kwargs.setdefault("headers", {})
    headers.setdefault("User-Agent", USER_AGENT)

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = httpx.get(url, timeout=timeout, **kwargs)
            if resp.status_code < 500:
                resp.raise_for_status()  # 4xx: raised straight out, never retried
                return resp
            last_exc = httpx.HTTPStatusError(
                f"Server error {resp.status_code}", request=resp.request, response=resp
            )
        except httpx.TransportError as e:
            last_exc = e

        if attempt < max_retries:
            backoff = 0.5 * (2 ** attempt)
            logger.debug(f"Request to {url} failed ({last_exc}); retrying in {backoff}s")
            time.sleep(backoff)
        else:
            logger.warning(f"Request to {url} failed after {attempt + 1} attempt(s): {last_exc}")
    assert last_exc is not None
    raise last_exc
