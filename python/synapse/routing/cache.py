"""
Synapse Response Cache (He2025)

Deterministic response caching via SHA-256 canonicalization.
Same canonical input → same cached output → O(1) retrieval.

Inspired by [He2025]: batch-invariant kernels + temperature 0 = identical
output for identical input. Canonicalization enables cross-session caching.

TTL strategy per tier:
  Tier 1: 1h  (knowledge is static within session)
  Tier 2: 30m (LLM responses may vary with context)
  Tier 3: 10m (plans depend on mutable scene state)
"""

import hashlib
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Tuple

# xxhash is ~100x faster than SHA-256 for cache keying (non-crypto use)
try:
    import xxhash
    _XXHASH_AVAILABLE = True
except ImportError:
    _XXHASH_AVAILABLE = False


def _fast_hash(data: str) -> str:
    """Fast non-cryptographic hash for cache keys.

    Uses xxhash (O(n) with tiny constant) when available,
    falls back to SHA-256.
    """
    encoded = data.encode("utf-8")
    if _XXHASH_AVAILABLE:
        return xxhash.xxh64(encoded).hexdigest()
    return hashlib.sha256(encoded).hexdigest()


# Default TTLs per tier name
_DEFAULT_TTLS: Dict[str, int] = {
    "recipe": 0,    # No cache — already instant
    "instant": 0,   # No cache — already instant
    "fast": 3600,   # 1 hour
    "standard": 1800,  # 30 minutes
    "deep": 600,    # 10 minutes
}


@dataclass
class _CacheEntry:
    """Internal cache entry with expiry tracking."""
    result: Any
    created_at: float
    ttl: int
    tier: str
    hits: int = 0

    @property
    def expired(self) -> bool:
        if self.ttl <= 0:
            return True  # TTL 0 = never cache
        return (time.monotonic() - self.created_at) > self.ttl


class ResponseCache:
    """
    Deterministic response cache using SHA-256 canonicalization.

    Thread-safe via lock. LRU eviction when max_size exceeded.
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self._max_size = max_size
        self._default_ttl = ttl_seconds
        self._cache: Dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self._total_hits = 0
        self._total_misses = 0
        self._evictions = 0

    def get(
        self,
        tier: str,
        input_text: str,
        context_hash: str = "",
    ) -> Optional[Any]:
        """
        Look up cached result for canonical input.

        Returns the cached RoutingResult or None on miss/expiry.
        """
        key = self._canonical_key(tier, input_text, context_hash)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._total_misses += 1
                return None
            if entry.expired:
                del self._cache[key]
                self._total_misses += 1
                return None
            entry.hits += 1
            self._total_hits += 1
            return entry.result

    def put(
        self,
        tier: str,
        input_text: str,
        context_hash: str,
        result: Any,
        ttl: Optional[int] = None,
    ):
        """
        Cache a result for the canonical input.

        Uses tier-specific TTL if not provided.
        """
        if ttl is None:
            ttl = _DEFAULT_TTLS.get(tier, self._default_ttl)
        if ttl <= 0:
            return  # Don't cache instant tiers

        key = self._canonical_key(tier, input_text, context_hash)
        with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict_one()

            self._cache[key] = _CacheEntry(
                result=result,
                created_at=time.monotonic(),
                ttl=ttl,
                tier=tier,
            )

    def invalidate(self, pattern: Optional[str] = None):
        """
        Clear cache entries.

        Args:
            pattern: If provided, only clear entries whose key contains pattern.
                     If None, clear all entries.
        """
        with self._lock:
            if pattern is None:
                self._cache.clear()
            else:
                pattern_lower = pattern.lower()
                keys_to_remove = [
                    k for k in self._cache
                    if pattern_lower in k.lower()
                ]
                for k in keys_to_remove:
                    del self._cache[k]

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            total = self._total_hits + self._total_misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._total_hits,
                "misses": self._total_misses,
                "hit_rate": (self._total_hits / total) if total > 0 else 0.0,
                "evictions": self._evictions,
            }

    def _canonical_key(self, tier: str, input_text: str, context_hash: str) -> str:
        """
        Produce canonical cache key via SHA-256.

        Canonicalization (He2025-inspired):
        1. Strip whitespace, lowercase
        2. Hash: SHA-256(tier + ":" + canonical_text + ":" + context_hash)
        """
        canonical = input_text.strip().lower()
        raw = f"{tier}:{canonical}:{context_hash}"
        return _fast_hash(raw)

    def _evict_one(self):
        """Batch eviction: remove expired entries, then oldest 10% by created_at.

        Amortizes the O(n) scan cost by evicting multiple entries at once
        instead of finding a single min on every put().
        """
        if not self._cache:
            return

        # Phase 1: sweep all expired entries
        expired_keys = [k for k, e in self._cache.items() if e.expired]
        if expired_keys:
            for k in expired_keys:
                del self._cache[k]
            self._evictions += len(expired_keys)
            return

        # Phase 2: evict oldest 10% (minimum 1) sorted by created_at
        batch_size = max(1, len(self._cache) // 10)
        victims = sorted(
            self._cache,
            key=lambda k: self._cache[k].created_at,
        )[:batch_size]
        for k in victims:
            del self._cache[k]
        self._evictions += len(victims)
