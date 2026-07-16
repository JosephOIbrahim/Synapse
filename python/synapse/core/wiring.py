"""Label-resolved node wiring against the probe-verified connectivity catalog.

Utility-flywheel cycle U.1 (``harness/notes/spec-U1-wiring-flywheel.md``).
Input indices drift in memory (the vellumsolver/rbdbulletsolver miswires);
input LABELS are the surface artists see and the probe records. This module
resolves a label to its live input index from the committed catalog and wires
through ``node.setInput`` — so the code names the *intent* and the catalog
supplies the index.

The catalog is the packaged copy of the U.1 probe output
(``python/synapse/cognitive/tools/data/connectivity_<major>.json`` — the scout
symbol-table pattern: per-major committed authority, blake2b-stamped,
byte-identical to ``harness/notes/verified_connectivity_<build>.json``).
Resolution is keyed on the RUNNING Houdini major (U.1-H22 fold, the validator
half of W.3): ``hou`` importable -> ``connectivity_<major>.json``; standalone
(stock python / CI) -> the H21 default, preserving the test-world truth. A
missing per-major catalog FAILS LOUD — never a silent cross-major fallback,
because a wrong-major catalog is exactly the miswire class this module exists
to kill (H22 renamed the set-dressing LOPs and moved Cop/light's inputs).

Fail-loud by design (``ScoutError``-style): an unknown type or label raises
``WiringError`` — never a silent index guess. Index fallback exists ONLY via
the explicit ``allow_index=True`` escape hatch.

Zero ``hou`` import at module scope — the node/source arguments are duck-typed
(live ``hou.Node`` in production, fakes in tests). The major resolver does a
guarded LOCAL ``hou`` import (the doctor.py pattern), so importing this module
stays pure Python.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Optional

CATALOG_SCHEMA = "verified_connectivity/v2"

# Committed package authority — travels to CI / headless / hython where the
# harness notes may be absent. Per-major naming like h21_symbol_table.json;
# _PKG_CATALOG is the STANDALONE default (no hou -> the H21 test-world truth),
# the running-major file is resolved by _pkg_catalog_path().
_PKG_CATALOG = (Path(__file__).resolve().parents[1] / "cognitive" / "tools"
                / "data" / "connectivity_21.json")

_VERSION_COMPONENT = re.compile(r"^[0-9][0-9.]*$")

_CATALOG_CACHE: dict = {}


class WiringError(RuntimeError):
    """Raised on any unresolvable wiring request (unknown type, unknown label,
    missing/corrupt catalog). A plain exception ON PURPOSE — callers surface it;
    nothing here degrades to a guessed input index."""


def _strip_version(full_name: str) -> str:
    parts = full_name.split("::")
    if len(parts) > 1 and _VERSION_COMPONENT.match(parts[-1]):
        return "::".join(parts[:-1])
    return full_name


def _running_houdini_major() -> Optional[int]:
    """The RUNNING Houdini major via ``hou.applicationVersion()[0]`` — the
    scout/doctor ``h<major>_symbol_table.json`` selection pattern. Guarded
    LOCAL import: the module stays zero-``hou`` at import time; standalone
    (stock python / CI) returns ``None``. Anything non-int (test fakes,
    residency-leaked MagicMocks) reads as unknown — never a guessed major."""
    try:
        import hou  # local + guarded on purpose (doctor.py pattern)
        major = hou.applicationVersion()[0]
    except Exception:
        return None
    return major if isinstance(major, int) else None


def _pkg_catalog_path() -> Path:
    """Per-major committed authority: ``connectivity_<major>.json`` for the
    RUNNING major; no major known (standalone/tests) -> the H21 default,
    preserving the test-world truth. NO existence check and NO cross-major
    fallback here — a wrong-major catalog is the miswire class itself, so a
    missing per-major file must fail in the loader, loudly."""
    major = _running_houdini_major()
    if major is None:
        return _PKG_CATALOG
    return _PKG_CATALOG.with_name(f"connectivity_{major}.json")


def load_connectivity_catalog(path: Optional[Path] = None, *,
                              strict: bool = True) -> Optional[dict]:
    """Load + integrity-check the packaged catalog. ``strict=True`` raises
    :class:`WiringError` on any problem (the wire-time posture: a mutation
    must not proceed on a missing/corrupt catalog); ``strict=False`` returns
    ``None`` (the validator posture: no catalog -> the additive check skips,
    the oracle-backed checks still run).

    ``path=None`` resolves the packaged catalog for the RUNNING Houdini major
    (see :func:`_pkg_catalog_path`); an explicit ``path`` is honored verbatim,
    untouched by major resolution."""
    fp = Path(path) if path is not None else _pkg_catalog_path()
    key = str(fp)
    if key in _CATALOG_CACHE:
        cached = _CATALOG_CACHE[key]
        if cached is None and strict:
            raise WiringError(f"connectivity catalog unusable at {fp}")
        return cached

    def _fail(reason: str):
        _CATALOG_CACHE[key] = None
        if strict:
            raise WiringError(f"connectivity catalog {reason} ({fp})")
        return None

    if not fp.is_file():
        if path is None:
            major = _running_houdini_major()
            if major is not None:
                # Rule (d) of the U.1-H22 fold: name the expected per-major
                # file and NEVER silently fall back across majors.
                return _fail(
                    f"missing for running Houdini major {major} — probe the "
                    f"build (host/introspect_connectivity.py) and package it "
                    f"as {fp.name}; wiring never falls back across majors")
        return _fail("missing")
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return _fail(f"unreadable/malformed: {e}")
    if data.get("schema") != CATALOG_SCHEMA:
        return _fail(f"has schema {data.get('schema')!r}, expected {CATALOG_SCHEMA!r}")
    digest = hashlib.blake2b(
        json.dumps(data.get("entries", {}), sort_keys=True,
                   ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()
    if digest != data.get("blake2b"):
        return _fail("checksum mismatch (corrupt or hand-edited)")
    _CATALOG_CACHE[key] = data
    return data


def resolve_catalog_entry(catalog: dict, category: str,
                          type_name: str) -> Optional[dict]:
    """The catalog entry for (category, type_name), accepting the spellings
    ``createNode`` accepts: exact full name, version-elided, or bare name.
    Ambiguous bare-name matches within a category return ``None`` (conservative
    — no check beats a wrong check)."""
    entries = catalog.get("entries", {})
    exact = entries.get(f"{category}/{type_name}")
    if exact is not None:
        return exact
    hits = []
    for entry in entries.values():
        if entry["category"] != category:
            continue
        base = _strip_version(entry["type_name"])
        if base == type_name or (
                "::" not in type_name and base.split("::")[-1] == type_name):
            hits.append(entry)
    return hits[0] if len(hits) == 1 else None


def resolve_input_index(catalog: dict, category: str, type_name: str,
                        label: str) -> int:
    """The input index carrying ``label`` (case-insensitive EXACT match) on
    (category, type_name). Raises :class:`WiringError` when the type is not in
    the catalog, carries no probed labels, or has no such label."""
    entry = resolve_catalog_entry(catalog, category, type_name)
    if entry is None:
        raise WiringError(
            f"node type '{category}/{type_name}' is not in the connectivity "
            f"catalog — probe it (host/introspect_connectivity.py) before "
            f"wiring by label")
    labels = entry.get("input_labels")
    if not labels:
        raise WiringError(
            f"'{category}/{type_name}' has no probed input labels "
            f"(instantiated={entry.get('instantiated')}) — wire_by_label "
            f"cannot resolve '{label}'")
    wanted = label.strip().lower()
    for i, have in enumerate(labels):
        if str(have).strip().lower() == wanted:
            return i
    raise WiringError(
        f"'{category}/{type_name}' has no input labeled '{label}' — probe-"
        f"verified labels are {labels}")


def wire_by_label(node, label: str, source, catalog: Optional[dict] = None, *,
                  source_output: int = 0, index: Optional[int] = None,
                  allow_index: bool = False) -> int:
    """Wire ``source`` into ``node``'s input named ``label``; returns the index.

    The index comes from the connectivity catalog (probe truth), never from
    memory. Unknown type/label FAILS LOUD with :class:`WiringError`; the ONLY
    escape hatch is ``allow_index=True`` + an explicit ``index``, for types the
    probe cannot label — and that fallback is a recorded decision at the call
    site, not a silent default.
    """
    if catalog is None:
        catalog = load_connectivity_catalog(strict=True)
    nt = node.type()
    type_name = nt.name()
    category = nt.category().name()
    try:
        resolved = resolve_input_index(catalog, category, type_name, label)
    except WiringError:
        if allow_index and index is not None:
            node.setInput(index, source, source_output)
            return index
        raise
    node.setInput(resolved, source, source_output)
    return resolved
