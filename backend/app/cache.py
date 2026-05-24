from __future__ import annotations

import json
import logging
from typing import Any

import redis

from .config import get_settings

log = logging.getLogger(__name__)


class ReviewCache:
    """Thin wrapper around Redis for cached review results.

    Falls back to a no-op cache if Redis is unreachable, so a flaky cache never
    breaks the request path.
    """

    def __init__(self, url: str, ttl_seconds: int) -> None:
        self.ttl = ttl_seconds
        try:
            self._client: redis.Redis | None = redis.Redis.from_url(
                url, decode_responses=True, socket_connect_timeout=2
            )
            self._client.ping()
        except Exception as exc:
            log.warning("Redis unreachable, caching disabled: %s", exc)
            self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def get(self, key: str) -> dict[str, Any] | None:
        if not self._client:
            return None
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            log.warning("cache get failed: %s", exc)
            return None

    def set(self, key: str, value: dict[str, Any]) -> None:
        if not self._client:
            return
        try:
            self._client.set(key, json.dumps(value, default=str), ex=self.ttl)
        except Exception as exc:
            log.warning("cache set failed: %s", exc)

    def ping(self) -> bool:
        if not self._client:
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            return False


_cache: ReviewCache | None = None


def get_cache() -> ReviewCache:
    global _cache
    if _cache is None:
        settings = get_settings()
        _cache = ReviewCache(settings.redis_url, settings.cache_ttl_seconds)
    return _cache
