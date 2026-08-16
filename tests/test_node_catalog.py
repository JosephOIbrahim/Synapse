"""Pins the build-keyed schema catalog (W5-CATALOG substrate P1).

Reads only the COMMITTED artifacts under ``rag/catalog/h22.0.400/`` -- no ``hou``,
no live Houdini -- so it runs in CI on any machine. It is the standing guard for
the acceptance predicates:

  * catalog files exist for every category the dump recorded, build-keyed;
  * VOP rows carry wire signatures with typed entries;
  * APEX callbacks carry typed ports;
  * docs are visited-pages-only and never synthesized (every ``doc`` traces to a
    cache anchor; no ``doc`` without one);
  * the live spot-audit committed a passing verdict.

If build_node_catalog.py's schema changes, or a row is hand-edited in a way that
breaks the shape, these fail loud.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

BUILD = "22.0.400"
_REPO = Path(__file__).resolve().parents[1]
CATALOG = _REPO / "rag" / "catalog" / f"h{BUILD}"

pytestmark = pytest.mark.skipif(
    not CATALOG.is_dir(),
    reason=f"catalog not dumped for build {BUILD} (run scripts/build_node_catalog.py in hython)",
)


def _load(name):
    return json.loads((CATALOG / name).read_text(encoding="utf-8"))


def _manifest():
    return _load("_manifest.json")


def test_manifest_is_build_keyed():
    m = _manifest()
    assert m["build"] == BUILD
    assert m["schema"] == "node_catalog_manifest/v1"
    # The build-keyed path is the staleness contract.
    assert CATALOG.name == f"h{BUILD}"
    assert m["category_count"] == 18


def test_a_file_exists_for_every_category():
    """Predicate 1: catalog files exist for every category the dump enumerated."""
    m = _manifest()
    cat_files = {n for n, f in m["files"].items() if "category" in f}
    # 18 categories were dumped (including empty Director/Manager).
    assert len(cat_files) == 18
    for name in cat_files:
        fp = CATALOG / name
        assert fp.is_file(), f"missing category file {name}"
        payload = json.loads(fp.read_text(encoding="utf-8"))
        assert payload["build"] == BUILD
        assert payload["schema"] == "node_catalog_live/v1"
        assert "types" in payload
        assert payload["count"] == len(payload["types"])


def test_empty_categories_still_have_files():
    """Director/Manager are empty on this build but must still have honest files."""
    for empty in ("Director.json", "Manager.json"):
        payload = _load(empty)
        assert payload["count"] == 0
        assert payload["types"] == {}


def test_parm_records_have_typed_surface():
    """Rows carry the full parm surface: name/label/type, and value parms carry
    defaults; at least one menu parm somewhere carries tokens AND labels."""
    sop = _load("Sop.json")
    seen_menu = seen_default = 0
    for tn, rec in sop["types"].items():
        assert isinstance(rec.get("parms"), list)
        for p in rec["parms"]:
            assert "name" in p and "type" in p, f"{tn} parm missing name/type: {p}"
            if "default" in p:
                seen_default += 1
            if "menu_tokens" in p:
                assert "menu_labels" in p, f"{tn}.{p['name']}: tokens without labels"
                assert len(p["menu_tokens"]) == len(p["menu_labels"])
                seen_menu += 1
    assert seen_default > 100, "expected many value parms with defaults"
    assert seen_menu > 10, "expected many menu parms with token+label pairs"


def test_vop_wire_signatures_present_with_typed_entries():
    """Acceptance predicate 3a: VOP wire signatures present with typed entries."""
    vop = _load("Vop.json")
    meta = vop["vop_signatures"]
    assert meta["instantiated"] > 1000, "most VOP types should instantiate"
    typed = 0
    for tn, rec in vop["types"].items():
        sig = rec.get("wire_signature")
        assert isinstance(sig, dict), f"{tn} missing wire_signature"
        if sig.get("instantiated"):
            for k in ("input_names", "output_names",
                      "input_data_types", "output_data_types"):
                assert k in sig, f"{tn} signature missing {k}"
                assert isinstance(sig[k], list)
            # a typed entry means the data-type lists carry type strings
            if sig["output_data_types"]:
                assert all(isinstance(x, str) for x in sig["output_data_types"])
                typed += 1
        else:
            assert "note" in sig  # honest not-instantiated record
    assert typed > 500, "expected many VOP types with typed output signatures"


def test_apex_callback_ports_present_with_typed_entries():
    """Acceptance predicate 3b: APEX callback ports present with typed entries."""
    apex = _load("apex_callbacks.json")
    assert apex["schema"] == "apex_callback_catalog_live/v1"
    assert apex["count"] > 2000, "expected the full callback surface"
    cbs = apex["callbacks"]
    typed = 0
    for name, e in cbs.items():
        for side in ("inputs", "outputs"):
            if side in e:
                for port in e[side]:
                    # a typed port carries a name and a type string
                    assert "name" in port and "type" in port, f"{name} port untyped: {port}"
        if e.get("inputs") and e.get("outputs"):
            typed += 1
    assert typed > 1000, "expected many callbacks with typed in+out ports"


def test_docs_are_visited_only_never_synthesized():
    """Every doc traces to a real cache anchor; no doc is invented from a name."""
    report = _load("_docs_report.json")
    assert report["total_docs_joined"] > 0
    for name in ("Cop.json", "Vop.json", "Dop.json", "Sop.json"):
        payload = _load(name)
        dj = payload["docs_join"]
        joined = 0
        for tn, rec in payload["types"].items():
            doc = rec.get("doc")
            if doc is None:
                continue
            joined += 1
            # honesty: a doc MUST carry the cache anchor it was copied from.
            assert "cache" in doc, f"{tn} doc without cache anchor (synthesized?)"
            assert doc["cache"].startswith("nodes/")
            # every doc discloses HOW it was matched (provenance, not a guess).
            assert doc.get("match") in ("exact", "version_relaxed", "namespace_relaxed"), \
                f"{tn} doc missing/invalid match tier: {doc.get('match')}"
            # includes, when present, are resolved flags, not invented text.
            for inc in doc.get("includes", []):
                assert "ref" in inc and "resolved" in inc
        assert joined == dj["joined"], f"{name}: doc count != docs_join.joined"


def _node_id(type_name):
    """(namespace, base) ignoring version -- two versions of one node share it."""
    parts = type_name.split("::")
    if len(parts) > 1 and parts[-1] and all(c in "0123456789." for c in parts[-1]):
        parts = parts[:-1]
    if len(parts) == 1:
        return ("", parts[0])
    return (parts[0], "::".join(parts[1:]))


def test_no_help_page_cross_attributed_to_different_nodes():
    """The mis-join guard: a single cache page must not be attached to two
    DIFFERENT nodes (the labs::karma-steals-native-karma-doc class). Version
    siblings of the SAME node (filecache + filecache::2.0) legitimately share a
    version-agnostic page, so identity ignores version. This is the invariant
    the plain 'has a cache anchor' check could not catch."""
    for name in ("Lop.json", "Sop.json", "Top.json", "Vop.json", "Cop.json",
                 "Dop.json", "Object.json", "Cop2.json", "Shop.json", "Driver.json"):
        payload = _load(name)
        owners: dict = {}
        for tn, rec in payload["types"].items():
            doc = rec.get("doc")
            if doc:
                owners.setdefault(doc["cache"], set()).add(_node_id(tn))
        cross = {c: sorted(ids) for c, ids in owners.items() if len(ids) > 1}
        assert not cross, f"{name}: page cross-attributed to different nodes: {cross}"


def test_meta_files_are_build_stamped():
    """Claim-4: apex_callbacks and the docs report carry an agreeing build field."""
    assert _load("apex_callbacks.json")["build"] == BUILD
    assert _load("_docs_report.json")["build"] == BUILD


def test_live_spot_audit_verdict_is_pass():
    """Predicate 2: the committed live spot-audit passed with zero mismatches."""
    audit = _load("_audit.json")
    assert audit["build"] == BUILD
    assert audit["verdict"] == "pass"
    assert audit["total_mismatches"] == 0
    for domain in ("dop", "vop", "chop", "cop", "apex"):
        d = audit["domains"][domain]
        assert d["audited"] == 20, f"{domain}: expected 20 audited"
        assert d["mismatched"] == 0, f"{domain}: has mismatches"
        # every receipt is anchored
        for r in d["receipts"]:
            assert "anchor" in r or "note" in r


def test_determinism_marker_present():
    """The dump advertises byte-identical re-runs (no wall-clock stamp)."""
    for name in ("Sop.json", "apex_callbacks.json", "_manifest.json"):
        payload = _load(name)
        note = payload["generated"]["note"].lower()
        assert "deterministic" in note or "no wall-clock" in note
