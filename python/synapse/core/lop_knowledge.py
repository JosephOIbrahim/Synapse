"""LOP/Solaris knowledge catalog — corpus-authored, probe-cross-checked.

Utility-flywheel cycle U.5 (``harness/notes/spec-U5-lop-solaris-flywheel.md``).
Where core/wiring.py carries WIRING truth (input indices from a live probe), this
carries CONTEXT truth for Solaris: per-LOP-type role / USD type / key parms, the
ordering constraints a valid stage implies (e.g. assignmaterial needs a
materiallibrary upstream), and the types the corpus marks affirmatively absent
(no ``grid``/``plane`` LOP).

Same integrity posture as ``core/wiring.py``: the packaged copy
(``python/synapse/cognitive/tools/data/lop_solaris_knowledge_<major>.json``) is
the per-major committed authority; blake2b is stamped over the ``content``
payload; ``strict=True`` raises on any problem (a wire-time posture) while
``strict=False`` returns ``None`` so an additive validator phase simply skips.

Resolution is keyed on the RUNNING Houdini major (C-U5, the twin of the
U.1-H22 wiring fold): ``hou`` importable -> ``lop_solaris_knowledge_<major>.json``;
standalone (stock python / CI) -> the H21 default, preserving the test-world
truth. A missing per-major catalog FAILS LOUD in strict mode — never a silent
cross-major fallback, because wrong-major CONTEXT truth is exactly the stale-
advice class this fold exists to kill (H22 renamed the instancer LOPs and
consolidated the per-shape lights). ``strict=False`` still returns ``None``:
GraphValidator's LOP phase skips honestly instead of advising from H21 truth.

Zero ``hou`` import at module scope — the major resolver
(:func:`synapse.core.wiring._running_houdini_major`, shared on purpose so
U.1b hardening lands in ONE place) does a guarded LOCAL ``hou`` import.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from .wiring import _running_houdini_major

CATALOG_SCHEMA = "lop_solaris_knowledge/v1"

# Committed package authority — per-major naming like connectivity_<major>.json;
# _PKG is the STANDALONE default (no hou -> the H21 test-world truth), the
# running-major file is resolved by _pkg_catalog_path().
_PKG = (Path(__file__).resolve().parents[1] / "cognitive" / "tools"
        / "data" / "lop_solaris_knowledge_21.json")

_CACHE: dict = {}


class LopKnowledgeError(RuntimeError):
    """Raised on an unusable catalog in strict mode. A plain exception on purpose —
    callers surface it; nothing here degrades to a guessed fact."""


def _pkg_catalog_path() -> Path:
    """Per-major committed authority: ``lop_solaris_knowledge_<major>.json`` for
    the RUNNING major; no major known (standalone/tests) -> the H21 default,
    preserving the test-world truth. NO existence check and NO cross-major
    fallback here — wrong-major CONTEXT truth is the stale-advice class itself,
    so a missing per-major file must fail in the loader, loudly."""
    major = _running_houdini_major()
    if major is None:
        return _PKG
    return _PKG.with_name(f"lop_solaris_knowledge_{major}.json")


def load_lop_catalog(path: Optional[Path] = None, *,
                     strict: bool = True) -> Optional[dict]:
    """Load + integrity-check the packaged LOP knowledge catalog. ``strict=True``
    raises :class:`LopKnowledgeError` on any problem; ``strict=False`` returns
    ``None`` (the validator posture: no catalog -> the additive LOP phase skips).

    ``path=None`` resolves the packaged catalog for the RUNNING Houdini major
    (see :func:`_pkg_catalog_path`); an explicit ``path`` is honored verbatim,
    untouched by major resolution."""
    fp = Path(path) if path is not None else _pkg_catalog_path()
    key = str(fp)
    if key in _CACHE:
        cached = _CACHE[key]
        if cached is None and strict:
            raise LopKnowledgeError(f"LOP knowledge catalog unusable at {fp}")
        return cached

    def _fail(reason: str):
        _CACHE[key] = None
        if strict:
            raise LopKnowledgeError(f"LOP knowledge catalog {reason} ({fp})")
        return None

    if not fp.is_file():
        if path is None:
            major = _running_houdini_major()
            if major is not None:
                # Rule (d) of the U.1-H22 fold, mirrored: name the expected
                # per-major file and NEVER silently fall back across majors.
                return _fail(
                    f"missing for running Houdini major {major} — probe the "
                    f"build (scripts/author_lop_knowledge_22.py pattern) and "
                    f"package it as {fp.name}; LOP knowledge never falls back "
                    f"across majors")
        return _fail("missing")
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return _fail(f"unreadable/malformed: {e}")
    if data.get("schema") != CATALOG_SCHEMA:
        return _fail(f"has schema {data.get('schema')!r}, expected {CATALOG_SCHEMA!r}")
    digest = hashlib.blake2b(
        json.dumps(data.get("content", {}), sort_keys=True,
                   ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()
    if digest != data.get("blake2b"):
        return _fail("checksum mismatch (corrupt or hand-edited)")
    _CACHE[key] = data
    return data


def lop_entry(catalog: Optional[dict], type_name: str) -> Optional[dict]:
    """The knowledge entry for a LOP type, or None."""
    return (catalog or {}).get("content", {}).get("entries", {}).get(type_name)


def ordering_rules(catalog: Optional[dict]) -> list:
    """The ordering constraints a valid Solaris stage must satisfy."""
    return (catalog or {}).get("content", {}).get("ordering_rules", [])


def known_absent(catalog: Optional[dict]) -> dict:
    """LOP type names the corpus marks affirmatively absent, with remediations."""
    return (catalog or {}).get("content", {}).get("known_absent", {})
