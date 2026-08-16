"""W5-PARMGATE: the Parm Gate rejects hallucinated parm names before mutating.

Hermetic, ``hou``-free unit coverage of ``synapse.validation.parm_gate`` and
``synapse.validation.catalog``. Every test gates against the committed fixture
catalog (``tests/fixtures/parm_catalog/h22.0.400/Cop.json`` -- a faithful tiny
subset of the live 22.0.400 dump: real parm names only, phantom ``code``
deliberately absent), so nothing here depends on the 2.5M-line W5-CATALOG data
being in the tree.

Pins acceptance predicate 1 (reject-with-suggestion, RED/GREEN) and the
crucible criteria: the gate opens no undo path of its own (criterion 1) and its
failures are catchable + self-correcting, never silent (criterion 3).
"""

from pathlib import Path

import pytest

from synapse.validation import catalog as catalog_mod
from synapse.validation.catalog import Catalog
from synapse.validation.parm_gate import (
    ParmGateError,
    gated_set,
    nearest_matches,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "parm_catalog" / "h22.0.400"


@pytest.fixture
def cat():
    """Authoritative catalog rooted at the committed fixture."""
    return Catalog(_FIXTURE_DIR)


# ── A tiny undo-group recorder + recording node (no hou) ────────────────────
#
# The recorder counts group open/close depth; a recording parm stamps the
# CURRENT depth onto every set, so a test can prove a write landed inside the
# caller's group (depth >= 1) and that the gate itself opened no group.


class _UndoRecorder:
    def __init__(self):
        self.groups = []      # names opened, in order
        self.depth = 0
        self.mutations = []   # (parm_name, depth_at_set)

    def group(self, name=""):
        return _Group(self, name)


class _Group:
    def __init__(self, rec, name):
        self._rec, self._name = rec, name

    def __enter__(self):
        self._rec.groups.append(self._name)
        self._rec.depth += 1
        return self

    def __exit__(self, *exc):
        self._rec.depth -= 1
        return False  # grouping is not rollback -- never swallow


class _RecParm:
    def __init__(self, name, rec):
        self._name, self._rec = name, rec
        self.value = None
        self.set_calls = 0

    def name(self):
        return self._name

    def set(self, value):
        self.value = value
        self.set_calls += 1
        self._rec.mutations.append((self._name, self._rec.depth))


class _RecType:
    def __init__(self, name, category):
        self._name, self._cat = name, category

    def name(self):
        return self._name

    def category(self):
        return _RecCat(self._cat)


class _RecCat:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _RecNode:
    """Node exposing only ``live_parms``; ``parm(x)`` is None for anything else
    (exactly like a real node), and each resolved parm records its set depth."""

    def __init__(self, live_parms, type_name="opencl", category="Cop", rec=None):
        self._live = set(live_parms)
        self._type = _RecType(type_name, category)
        self.rec = rec or _UndoRecorder()
        self.made = {}

    def type(self):
        return self._type

    def parm(self, name):
        if name not in self._live:
            return None
        if name not in self.made:
            self.made[name] = _RecParm(name, self.rec)
        return self.made[name]

    def parmTuple(self, name):
        return None


# ── Catalog lookup (target 2) ───────────────────────────────────────────────

class TestCatalogLookup:
    def test_parms_are_the_real_opencl_names(self, cat):
        names = cat.parms("Cop", "opencl")
        assert names is not None
        assert "kernelcode" in names          # real
        assert "code" not in names            # phantom -- the whole point
        assert "kernelname" in names

    def test_signature_carries_parm_dicts(self, cat):
        sig = cat.signature("Cop", "opencl")
        assert isinstance(sig, list) and sig
        assert all("name" in p for p in sig)

    def test_uncatalogued_type_is_none(self, cat):
        assert cat.parms("Cop", "no_such_node") is None
        assert cat.signature("Cop", "no_such_node") is None

    def test_uncatalogued_category_is_none(self, cat):
        assert cat.parms("Nope", "opencl") is None

    def test_null_catalog_is_unavailable(self):
        empty = Catalog(None)
        assert empty.available is False
        assert empty.parms("Cop", "opencl") is None
        assert empty.has_type("Cop", "opencl") is False

    def test_has_type(self, cat):
        assert cat.has_type("Cop", "opencl") is True
        assert cat.has_type("Cop", "no_such_node") is False

    def test_lookup_is_embedding_free(self):
        # target 2: cheap exact lookups, no embedding round-trips -> the module
        # pulls in no vector/embedding dependency and does its work with json.
        src = Path(catalog_mod.__file__).read_text(encoding="utf-8")
        assert "import json" in src
        for banned in ("import numpy", "sentence_transformers", "import torch",
                       "faiss", "import chromadb", "OllamaEmbed"):
            assert banned not in src, f"catalog must not depend on {banned}"


# ── RED / GREEN: reject a hallucinated name with a suggestion (predicate 1) ──

class TestRejectionRedGreen:
    def test_red_phantom_name_rejected_with_suggestion(self, cat):
        node = _RecNode(live_parms={"kernelcode"})
        with pytest.raises(ParmGateError) as ei:
            gated_set(node, {"code": "// kernel"}, catalog=cat)
        err = ei.value
        assert err.unknown[0]["name"] == "code"
        assert "kernelcode" in err.unknown[0]["suggestions"]

    def test_red_is_pre_mutation_no_write_happened(self, cat):
        # The rejection must fire BEFORE any node mutation.
        node = _RecNode(live_parms={"kernelcode"})
        with pytest.raises(ParmGateError):
            gated_set(node, {"code": "// kernel"}, catalog=cat)
        assert node.made == {}          # no parm was ever resolved/set
        assert node.rec.mutations == []

    def test_red_typo_suggests_correct_name(self, cat):
        node = _RecNode(live_parms={"kernelcode"})
        with pytest.raises(ParmGateError) as ei:
            gated_set(node, {"kernelcod": "x"}, catalog=cat)
        assert ei.value.unknown[0]["suggestions"][0] == "kernelcode"

    def test_green_valid_name_sets(self, cat):
        node = _RecNode(live_parms={"kernelcode"})
        result = gated_set(node, {"kernelcode": "float v = @P.x;"}, catalog=cat)
        assert result["gated"] is True
        assert result["authority"] == "catalog"
        assert result["set"] == ["kernelcode"]
        assert node.made["kernelcode"].value == "float v = @P.x;"

    def test_partial_batch_rejects_whole_before_any_write(self, cat):
        # One good + one bad name: the bad one rejects the batch atomically,
        # the good one is NOT written (no partial mutation).
        node = _RecNode(live_parms={"kernelcode", "kernelname"})
        with pytest.raises(ParmGateError):
            gated_set(node, {"kernelname": "k", "code": "x"}, catalog=cat)
        assert node.made == {}


# ── Suggestion quality (predicate 1, "useful suggestion") ───────────────────

class TestSuggestionQuality:
    def test_code_ranks_kernelcode_first_by_substring(self, cat):
        names = sorted(cat.parms("Cop", "opencl"))
        assert nearest_matches("code", names)[0] == "kernelcode"

    def test_typo_ranks_by_edit_distance(self, cat):
        names = sorted(cat.parms("Cop", "opencl"))
        assert nearest_matches("kernelcod", names)[0] == "kernelcode"

    def test_wildly_wrong_name_is_honest_empty(self, cat):
        names = sorted(cat.parms("Cop", "opencl"))
        assert nearest_matches("zzzqqxx", names) == []


# ── Catchable + self-correcting, never silent (crucible criterion 3) ────────

class TestCatchableSelfCorrecting:
    def test_error_is_a_valueerror(self, cat):
        node = _RecNode(live_parms={"kernelcode"})
        with pytest.raises(ValueError):        # subclass -> existing catches work
            gated_set(node, {"code": "x"}, catalog=cat)

    def test_to_result_is_structured_for_the_agent_loop(self, cat):
        node = _RecNode(live_parms={"kernelcode"})
        try:
            gated_set(node, {"code": "x"}, catalog=cat)
        except ParmGateError as err:
            payload = err.to_result()
        assert payload["ok"] is False
        assert payload["error"] == "parm_gate_rejected"
        assert payload["node_type"] == "opencl"
        flat = [s for u in payload["unknown"] for s in u["suggestions"]]
        assert "kernelcode" in flat

    def test_message_names_the_bad_parm_and_the_fix(self, cat):
        node = _RecNode(live_parms={"kernelcode"})
        with pytest.raises(ParmGateError) as ei:
            gated_set(node, {"code": "x"}, catalog=cat)
        msg = str(ei.value)
        assert "code" in msg and "kernelcode" in msg


# ── The gate opens no undo path of its own (crucible criterion 1) ───────────

class TestUndoDiscipline:
    def test_source_never_touches_undo_or_hou(self):
        # AST-based so the module docstring (which *describes* the invariant)
        # cannot false-trip it: assert the CODE never imports hou and never
        # references `.undos` / calls `undos.group`.
        import ast

        from synapse.validation import parm_gate
        tree = ast.parse(Path(parm_gate.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name != "hou" and not a.name.startswith("hou.")
                           for a in node.names)
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert mod != "hou" and not mod.startswith("hou.")
            if isinstance(node, ast.Attribute):
                assert node.attr != "undos", "gate must not reference .undos"

    def test_bare_gated_set_opens_no_group(self, cat):
        node = _RecNode(live_parms={"kernelcode"})
        gated_set(node, {"kernelcode": "x"}, catalog=cat)
        assert node.rec.groups == []                     # gate opened none
        assert node.rec.mutations == [("kernelcode", 0)]  # set at depth 0

    def test_set_lands_in_the_single_caller_group(self, cat):
        # The load-bearing invariant: inside one caller-opened group, a gated
        # set writes at depth 1 and adds no group of its own -> exactly one
        # undo group wraps the whole thing.
        node = _RecNode(live_parms={"kernelcode"})
        with node.rec.group("caller"):
            gated_set(node, {"kernelcode": "x"}, catalog=cat)
        assert node.rec.groups == ["caller"]             # exactly one
        assert node.rec.mutations == [("kernelcode", 1)]  # inside it


# ── Never a false reject: multiparm + permissive degrade ────────────────────

class TestNoFalseReject:
    def test_multiparm_instance_matches_template(self, cat):
        # 'input#_name' is the catalog template; 'input5_name' is a live
        # instance and must NOT be rejected.
        node = _RecNode(live_parms={"input5_name"})
        result = gated_set(node, {"input5_name": "foo"}, catalog=cat)
        assert result["set"] == ["input5_name"]

    def test_no_catalog_signature_degrades_to_safe_set(self):
        # Empty catalog -> permissive: write live parms, skip absent ones,
        # NEVER raise on an unknown name (no authority to call it bad).
        empty = Catalog(None)
        node = _RecNode(live_parms={"kernelcode"})
        result = gated_set(node, {"kernelcode": "x", "bogus": 1}, catalog=empty)
        assert result["authority"] == "none"
        assert result["set"] == ["kernelcode"]
        assert result["skipped"] == ["bogus"]

    def test_uncatalogued_type_degrades_not_rejects(self, cat):
        # Real catalog, but a type it does not know -> permissive, no raise.
        node = _RecNode(live_parms={"whatever"}, type_name="mystery_node")
        result = gated_set(node, {"whatever": 1, "alsobogus": 2}, catalog=cat)
        assert result["authority"] == "none"
        assert result["set"] == ["whatever"]
        assert result["skipped"] == ["alsobogus"]

    def test_empty_values_noop(self, cat):
        node = _RecNode(live_parms={"kernelcode"})
        result = gated_set(node, {}, catalog=cat)
        assert result["set"] == [] and result["skipped"] == []
