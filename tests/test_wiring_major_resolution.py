"""U.1-H22 fold pins — major-aware connectivity catalog resolution (SB-2).

The validator half of the merged W.3: SYNAPSE now emits the H22 canonical
set-dressing LOPs (``paintinstances`` ex-``layout``, ``copytopoints``
ex-``instancer``) and H22 moved input surfaces (``Cop/light`` 3 -> 8 inputs,
``mask`` index 2 -> 7). ``synapse.core.wiring`` resolves the packaged catalog
PER RUNNING MAJOR (the ``h<major>_symbol_table.json`` selection pattern):

  * ``hou`` importable -> ``connectivity_<hou.applicationVersion()[0]>.json``
  * ``hou`` absent     -> the H21 default (the test-world truth, unchanged)
  * missing major file -> ``WiringError`` naming the expected file — NEVER a
                          silent cross-major fallback (a wrong-major catalog
                          IS the miswire class U.1 exists to kill)
  * explicit ``path``  -> honored verbatim, untouched by resolution

Pure Python — no Houdini. ``hou`` presence is simulated through
``sys.modules`` (``None`` forces ``import hou`` to raise, deterministically
simulating absence even when another test module leaked a resident fake).
"""
from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from synapse.core import wiring
from synapse.core.wiring import (
    WiringError,
    load_connectivity_catalog,
    resolve_catalog_entry,
    resolve_input_index,
    wire_by_label,
)

_REPO = Path(__file__).resolve().parents[1]
_DATA = _REPO / "python/synapse/cognitive/tools/data"
PKG_21 = _DATA / "connectivity_21.json"
PKG_22 = _DATA / "connectivity_22.json"
HARNESS_22 = _REPO / "harness/notes/verified_connectivity_22.0.368.json"


def _fake_hou(major):
    mod = types.ModuleType("hou")
    mod.applicationVersion = lambda: (major, 0, 368)
    return mod


# ---------------------------------------------------------------------------
# 1. Resolver rules (a)-(d)
# ---------------------------------------------------------------------------

class TestMajorResolution:
    def test_no_hou_defaults_to_h21(self, monkeypatch):
        # sys.modules["hou"] = None makes `import hou` raise ImportError —
        # deterministic absence, immune to resident fakes from other modules.
        monkeypatch.setitem(sys.modules, "hou", None)
        assert wiring._pkg_catalog_path() == PKG_21
        cat = load_connectivity_catalog()
        assert cat["houdini_version"] == "21.0.671"

    def test_h22_major_resolves_h22_catalog(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "hou", _fake_hou(22))
        assert wiring._pkg_catalog_path() == PKG_22
        cat = load_connectivity_catalog()
        assert cat["houdini_version"] == "22.0.368"

    def test_missing_major_fails_loud_never_cross_major(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "hou", _fake_hou(99))
        with pytest.raises(WiringError, match=r"connectivity_99\.json"):
            load_connectivity_catalog(strict=True)
        # Validator posture: honest skip (None) — still no cross-major fallback.
        assert load_connectivity_catalog(strict=False) is None

    def test_non_int_major_reads_unknown_default_21(self, monkeypatch):
        # The residency-leak shape: a MagicMock hou whose applicationVersion()
        # yields a MagicMock, not an int. Must read UNKNOWN -> H21 default,
        # never a garbage-named catalog.
        monkeypatch.setitem(sys.modules, "hou", MagicMock())
        assert wiring._pkg_catalog_path() == PKG_21

    def test_explicit_path_honored_over_resolution(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "hou", _fake_hou(22))
        cat = load_connectivity_catalog(PKG_21)
        assert cat["houdini_version"] == "21.0.671"


# ---------------------------------------------------------------------------
# 2. H22 catalog determinism + content pins (probe truth, never hand-edited)
# ---------------------------------------------------------------------------

class TestH22CatalogTruth:
    def _cat(self):
        return load_connectivity_catalog(PKG_22)

    def test_packaged_copy_byte_identical_to_probe_artifact(self):
        assert PKG_22.read_bytes() == HARNESS_22.read_bytes(), (
            "packaged connectivity_22.json drifted from the harness probe "
            "artifact — re-run host/introspect_connectivity.py and re-copy"
        )

    def test_blake2b_recomputes_over_sorted_entries(self):
        raw = json.loads(PKG_22.read_text(encoding="utf-8"))
        digest = hashlib.blake2b(
            json.dumps(raw["entries"], sort_keys=True,
                       ensure_ascii=False).encode("utf-8"),
            digest_size=16,
        ).hexdigest()
        assert digest == raw["blake2b"]
        assert raw["schema"] == "verified_connectivity/v2"
        assert raw["houdini_version"] == "22.0.368"
        assert raw["probe_errors"] == []

    def test_w3_setdressing_types_present(self):
        # The exact gap the fold closes: W.3 emits these; the H21 catalog
        # cannot carry them, so pre-fold wire_by_label raised on H22.
        cat = self._cat()
        paint = cat["entries"]["Lop/paintinstances"]
        assert paint["instantiated"] is True
        assert paint["input_labels"] == ["Input Stage"]
        copy = cat["entries"]["Lop/copytopoints"]
        assert copy["instantiated"] is True
        assert copy["input_labels"] == ["Input Stage", "Possible Prototype Source"]
        # Renames, not additions — the H21 spellings are GONE on 22.
        assert "Lop/instancer" not in cat["entries"]
        assert "Lop/layout" not in cat["entries"]

    def test_cop_light_h22_input_surface(self):
        # H21 remembered 3 inputs with mask at index 2; H22 truth is 8 inputs
        # with mask at index 7 — the silent-miswire class the fold kills.
        cat = self._cat()
        entry = resolve_catalog_entry(cat, "Cop", "light")
        assert entry is not None
        assert entry["max_inputs"] == 8
        assert len(entry["input_labels"]) == 8
        assert entry["input_labels"][7] == "mask"
        assert resolve_input_index(cat, "Cop", "light", "mask") == 7

    def test_vellumsolver_golden_seeds_unchanged(self):
        # The seeds the whole U.1 cycle grew from hold on H22 too.
        cat = self._cat()
        vs = cat["entries"]["Sop/vellumsolver"]
        assert vs["input_labels"] == [
            "Vellum Geometry", "Constraint Geometry", "Collision Geometry"]
        rbd = cat["entries"]["Sop/rbdbulletsolver"]
        assert rbd["input_labels"][0] == "Geometry"
        assert rbd["input_labels"][1] == "Constraint Geometry"


# ---------------------------------------------------------------------------
# 3. End to end: wire_by_label under a (faked) H22 host
# ---------------------------------------------------------------------------

class _FakeCategory:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _FakeType:
    def __init__(self, name, category):
        self._name, self._category = name, _FakeCategory(category)

    def name(self):
        return self._name

    def category(self):
        return self._category


class _FakeNode:
    def __init__(self, type_name, category="Sop"):
        self._type = _FakeType(type_name, category)
        self.wired = []

    def type(self):
        return self._type

    def setInput(self, index, source, source_output=0):
        self.wired.append((index, source, source_output))


class TestWireByLabelUnderH22:
    def test_cop_light_mask_resolves_to_7(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "hou", _fake_hou(22))
        node, src = _FakeNode("light", category="Cop"), object()
        assert wire_by_label(node, "mask", src) == 7
        assert node.wired == [(7, src, 0)]

    def test_paintinstances_wires_input_stage(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "hou", _fake_hou(22))
        node, src = _FakeNode("paintinstances", category="Lop"), object()
        assert wire_by_label(node, "Input Stage", src) == 0

    def test_copytopoints_wires_prototype_source(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "hou", _fake_hou(22))
        node, src = _FakeNode("copytopoints", category="Lop"), object()
        assert wire_by_label(node, "Possible Prototype Source", src) == 1
