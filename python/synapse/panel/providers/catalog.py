"""Cached model catalog — discovery persisted across panel starts.

``probe.py`` answers "what does the provider serve *right now*"; its results
live in memory and die with the process. This module is the persistence half
of discovery: every successful refresh is folded into
``.synapse/model_catalog.json`` so the next panel start knows what was served
*last time*, even when the provider is down at that moment.

GATE A scope: **Ollama only** — ``GET /api/tags`` over stdlib ``urllib``
(providers are SDK-free; nothing here imports a vendor SDK). Each entry
carries a ``provider`` column so later gates can fold in more providers
without a file-format migration.

Contract
--------
* **Discovery never blocks panel start.** Panel start reads the cache only —
  :func:`load_catalog` is one local file read, no network, non-raising.
  :func:`refresh` is the only function that touches the network; it is bounded
  by a short timeout, converts every failure into a value, and is meant to run
  after start (or off the UI thread). There is no code path by which a dead
  endpoint becomes a hang or an exception at startup.
* **Failure degrades to the cache, flagged.** When the endpoint cannot be
  enumerated, :func:`refresh` returns the cached entries with ``stale=True``
  and a ``reason`` — never an exception, and never a silently-empty catalog
  that would read as "the provider serves nothing". The cache file is left
  untouched on failure, so ``last_seen`` keeps saying when each entry was
  really last observed instead of being laundered forward.
* **The diff is the event stream.** Each successful refresh reports ``new``
  (ids the cache did not have) and ``removed`` (cached ids the endpoint no
  longer serves). Removed entries leave the file, so a removal is reported
  exactly once. ``first_seen`` survives across refreshes — that continuity is
  what the cache is *for*.
* **No model names in code.** Entries are whatever ``/api/tags`` returned this
  refresh. This module contains zero model identifiers — a name typed into
  code is documentation, and documentation ages (R74; see ``probe.py``).
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Union

from . import probe

logger = logging.getLogger(__name__)

CATALOG_VERSION = 1

DEFAULT_CATALOG_RELPATH = os.path.join(".synapse", "model_catalog.json")
"""Default cache location, resolved against the process working directory.
The panel passes its own explicit path; this default serves repo-rooted and
test contexts. Always injectable — nothing below hardcodes a location."""

_PROVIDER = "ollama"          # GATE A: the only provider discovered here
_HTTP_TIMEOUT_S = 2.0         # local-first endpoint; bounded, never a hang


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """One discovered model as the cache remembers it.

    ``first_seen``/``last_seen`` are epoch seconds. ``local`` is probe-derived
    (an ``/api/tags`` row with no ``remote_host`` runs on this machine).
    ``auth_ok`` records whether the endpoint answered without an auth
    challenge; ``None`` means never established.
    """

    id: str
    provider: str
    endpoint: str
    local: bool
    first_seen: float
    last_seen: float
    latency_ms: Optional[float]
    auth_ok: Optional[bool]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "local": self.local,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "latency_ms": self.latency_ms,
            "auth_ok": self.auth_ok,
        }


@dataclass(frozen=True, slots=True)
class RefreshResult:
    """What one :func:`refresh` established.

    ``stale=True`` means the entries came from the cache because the endpoint
    could not be enumerated — ``reason`` says which kind of no. ``new`` and
    ``removed`` are the diff events, empty on a stale result (a failure
    teaches nothing about what appeared or disappeared).
    """

    entries: tuple[CatalogEntry, ...]
    new: tuple[str, ...]
    removed: tuple[str, ...]
    stale: bool
    reason: Optional[str]


# ---------------------------------------------------------------------------
# Cache file I/O — local, non-raising, atomic on write.
# ---------------------------------------------------------------------------

def _as_path(path: Union[str, os.PathLike, None]) -> Path:
    return Path(path) if path is not None else Path(DEFAULT_CATALOG_RELPATH)


def _entry_from_row(row: dict) -> Optional[CatalogEntry]:
    """One persisted row → entry, or ``None`` when the row is unusable.
    Per-row tolerance: one malformed row must not void the rest of the cache."""
    try:
        model_id = str(row["id"])
        provider = str(row["provider"])
        if not model_id or not provider:
            return None
        latency = row.get("latency_ms")
        auth = row.get("auth_ok")
        return CatalogEntry(
            id=model_id,
            provider=provider,
            endpoint=str(row.get("endpoint") or ""),
            local=bool(row.get("local")),
            first_seen=float(row.get("first_seen") or 0.0),
            last_seen=float(row.get("last_seen") or 0.0),
            latency_ms=float(latency) if latency is not None else None,
            auth_ok=bool(auth) if auth is not None else None,
        )
    except Exception as exc:
        logger.debug("catalog row skipped: %s", exc)
        return None


def load_catalog(path: Union[str, os.PathLike, None] = None) -> tuple[CatalogEntry, ...]:
    """The cached entries — one local file read, no network, never raises.

    This is the panel-start read path. Missing file, unreadable file, or
    malformed JSON all degrade to ``()`` with a debug log — an empty catalog
    is a determinate answer ("nothing has been discovered yet"), not an error.
    """
    p = _as_path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ()
    except Exception as exc:
        logger.debug("catalog unreadable at %s: %s", p, exc)
        return ()
    try:
        payload = json.loads(text)
        rows = payload.get("entries") or []
    except Exception as exc:
        logger.debug("catalog malformed at %s: %s", p, exc)
        return ()
    out = []
    for row in rows:
        entry = _entry_from_row(row) if isinstance(row, dict) else None
        if entry is not None:
            out.append(entry)
    return tuple(out)


def save_catalog(entries: Sequence[CatalogEntry],
                 path: Union[str, os.PathLike, None] = None) -> bool:
    """Persist ``entries`` atomically (``.tmp`` + replace). Returns success.

    Non-raising: a full disk or a locked file must not take the panel down —
    the in-memory result the caller already holds is still good, only the
    next process start loses this refresh.
    """
    p = _as_path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        payload = {
            "version": CATALOG_VERSION,
            "entries": [e.to_dict() for e in entries],
        }
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, p)
        return True
    except Exception as exc:
        logger.warning("catalog not persisted at %s: %s", p, exc)
        return False


# ---------------------------------------------------------------------------
# Discovery — stdlib urllib, bounded, every failure becomes a value.
# ---------------------------------------------------------------------------

def _discover_ollama(endpoint: str, timeout: float):
    """``GET {endpoint}/api/tags`` → ``(models, latency_ms, reason)``.

    ``models`` maps model id → ``local`` (no ``remote_host`` on the tag);
    ``None`` with a ``reason`` when the endpoint could not be enumerated.
    Never retries, never follows the failure with a second request.
    """
    url = endpoint.rstrip("/") + "/api/tags"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
        latency_ms = (time.perf_counter() - t0) * 1000.0
    except urllib.error.HTTPError as exc:
        reason = ("unauthorized" if exc.code in (401, 403)
                  else "rate_limited" if exc.code == 429
                  else "http_%d" % exc.code)
        return None, None, reason
    except Exception as exc:
        logger.debug("ollama discovery unreachable at %s: %s", url, exc)
        return None, None, "unreachable"
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
        models: dict[str, bool] = {}
        for m in payload.get("models") or []:
            name = m.get("name") or m.get("model")
            if not name:
                continue
            models[str(name)] = not (m.get("remote_host") or "")
        return models, latency_ms, None
    except Exception as exc:
        logger.debug("ollama /api/tags unparseable: %s", exc)
        return None, latency_ms, "unparseable_response"


def refresh(*, path: Union[str, os.PathLike, None] = None,
            endpoint: Optional[str] = None,
            now: Optional[float] = None,
            timeout: float = _HTTP_TIMEOUT_S) -> RefreshResult:
    """Discover what Ollama serves, fold it into the cache, report the diff.

    On success the file holds exactly what is served now: surviving entries
    keep their ``first_seen``, appearing ids are ``new``, vanished ids are
    ``removed`` and leave the file. On any failure the cached entries come
    back with ``stale=True`` and the file is untouched. This function never
    raises — discovery must never block panel start.
    """
    ts = time.time() if now is None else now
    p = _as_path(path)
    cached = load_catalog(p)
    try:
        ep = endpoint or probe.ollama_endpoint()
        served, latency_ms, reason = _discover_ollama(ep, timeout)
    except Exception as exc:            # pragma: no cover - defensive belt
        logger.warning("catalog refresh raised: %s", exc)
        served, latency_ms, reason = None, None, "probe_error"
    if served is None:
        return RefreshResult(entries=cached, new=(), removed=(),
                             stale=True, reason=reason)

    prior = {e.id: e for e in cached if e.provider == _PROVIDER}
    kept = [e for e in cached if e.provider != _PROVIDER]
    rows = [
        CatalogEntry(
            id=model_id,
            provider=_PROVIDER,
            endpoint=ep,
            local=is_local,
            first_seen=prior[model_id].first_seen if model_id in prior else ts,
            last_seen=ts,
            latency_ms=latency_ms,
            auth_ok=True,
        )
        for model_id, is_local in served.items()
    ]
    entries = tuple(sorted(kept + rows, key=lambda e: (e.provider, e.id)))
    new_ids = tuple(sorted(set(served) - set(prior)))
    removed_ids = tuple(sorted(set(prior) - set(served)))
    save_catalog(entries, p)
    return RefreshResult(entries=entries, new=new_ids, removed=removed_ids,
                         stale=False, reason=None)
