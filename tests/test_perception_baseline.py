"""Tests for ``synapse.host.perception_baseline`` (Mile-5 perception baseline).

Scope: the PURE envelope builder ``build_perception_baseline``. Pure, headless,
zero-``hou`` — verifies envelope shape, deterministic (passed-in) timestamp,
deep-equal event preservation, snapshot independence, and JSON-serializability.

Import strategy
---------------
``synapse`` is an editable install whose ``synapse.host`` package may resolve to
a checkout OTHER than this worktree (the editable ``.pth`` points at one tree).
To guarantee we exercise THIS tree's ``perception_baseline.py`` — and to stay
robust whether run pre- or post-merge — the module is loaded directly from its
file path (sibling ``python/`` tree of this ``tests/`` dir). The module is pure
and self-contained (no intra-package runtime imports), so file-path loading
under a neutral name is faithful. Mirrors the ``importlib.util`` convention in
``tests/test_tops.py``.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

# ── Load the pure module directly from the worktree file ────────────────────
_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "python" / "synapse" / "host" / "perception_baseline.py"
)
_spec = importlib.util.spec_from_file_location(
    "perception_baseline_under_test", _MODULE_PATH
)
assert _spec is not None and _spec.loader is not None, (
    f"could not build import spec for {_MODULE_PATH}"
)
perception_baseline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(perception_baseline)

build_perception_baseline = perception_baseline.build_perception_baseline
SCHEMA = perception_baseline.SCHEMA


# A realistic captured event dict, matching tops_bridge.TopsEvent.to_dict()'s
# fixed schema (tops_bridge.py:156). work_item_outputs is a list so we can also
# prove the envelope is a value SNAPSHOT (deep copy), not an alias.
def _fake_event(event_type: str, work_item_id: int) -> dict:
    return {
        "event_type": event_type,
        "pdg_event_type_int": 14,
        "top_node_path": "/obj/topnet1/ropfetch1",
        "timestamp": 123.5,
        "work_item_id": work_item_id,
        "work_item_frame": 1.0,
        "work_item_state": "cooked_success",
        "work_item_outputs": ["/tmp/out.0001.exr"],
        "work_item_cook_duration_seconds": 0.42,
        "node_path": "/obj/topnet1/ropfetch1",
        "error_message": None,
    }


# ── (a) empty capture → well-formed EMPTY baseline ──────────────────────────

def test_empty_baseline_is_valid_envelope():
    env = build_perception_baseline(
        [], runtime="H21.0.671", captured_at="2026-07-14T00:00:00Z"
    )
    assert env["schema"] == "perception_baseline/v1"
    assert env["schema"] == SCHEMA
    assert env["captured_at"] == "2026-07-14T00:00:00Z"
    assert env["runtime"] == "H21.0.671"
    assert env["count"] == 0
    assert env["events"] == []
    # exact key set — no drift in the frozen envelope shape
    assert set(env) == {"schema", "captured_at", "runtime", "count", "events"}
    # json round-trips losslessly
    assert json.loads(json.dumps(env)) == env


def test_none_events_is_treated_as_empty():
    env = build_perception_baseline(
        None, runtime="headless", captured_at="2026-07-14T00:00:00Z"
    )
    assert env["count"] == 0
    assert env["events"] == []


# ── (b) two event dicts → count 2, events preserved deep-equal ──────────────

def test_two_events_preserved_deep_equal():
    e1 = _fake_event("tops.cook.start", 1)
    e2 = _fake_event("tops.cook.complete", 2)
    env = build_perception_baseline(
        [e1, e2], runtime="H21.0.671", captured_at="2026-07-14T00:00:00Z"
    )
    assert env["count"] == 2
    assert len(env["events"]) == 2
    assert env["count"] == len(env["events"])
    # deep-equal preservation of every event dict, in order
    assert env["events"] == [e1, e2]


def test_envelope_is_a_snapshot_not_an_alias():
    """Mutating the caller's originals must not change the built envelope."""
    e1 = _fake_event("tops.cook.start", 1)
    env = build_perception_baseline(
        [e1], runtime="H21.0.671", captured_at="2026-07-14T00:00:00Z"
    )
    baseline_snapshot = copy.deepcopy(env)
    # mutate original scalar AND nested list after the fact
    e1["work_item_state"] = "cooked_fail"
    e1["work_item_outputs"].append("/tmp/injected.exr")
    assert env == baseline_snapshot  # envelope unaffected by post-hoc mutation


def test_topsevent_like_object_is_normalized_via_to_dict():
    """Duck-typed TopsEvent (host path): .to_dict() is used, no hou needed."""
    payload = _fake_event("tops.workitem.result", 7)

    class _DuckEvent:
        def to_dict(self):
            return dict(payload)

    env = build_perception_baseline(
        [_DuckEvent()], runtime="H21.0.671", captured_at="2026-07-14T00:00:00Z"
    )
    assert env["count"] == 1
    assert env["events"] == [payload]


def test_non_event_input_raises_typeerror():
    with pytest.raises(TypeError):
        build_perception_baseline(
            [42], runtime="H21.0.671", captured_at="2026-07-14T00:00:00Z"
        )


# ── (c) the envelope is JSON-serializable ───────────────────────────────────

def test_full_baseline_is_json_serializable():
    env = build_perception_baseline(
        [_fake_event("tops.cook.start", 1), _fake_event("tops.cook.complete", 2)],
        runtime="H21.0.671",
        captured_at="2026-07-14T00:00:00Z",
    )
    encoded = json.dumps(env)  # must not raise
    assert isinstance(encoded, str)
    assert json.loads(encoded) == env


# ── runtime purity guard: module imports with zero hou/pdg ──────────────────

def test_module_imports_without_hou_or_pdg():
    src = _MODULE_PATH.read_text(encoding="utf-8")
    # No hou/pdg import anywhere in the source — not even guarded.
    assert "import hou" not in src
    assert "import pdg" not in src
    # The only TopsEvent reference is under TYPE_CHECKING (never imported at
    # runtime): the tops_bridge import line must sit after `if TYPE_CHECKING`.
    assert "if TYPE_CHECKING" in src
    tb_import = "from synapse.host.tops_bridge import"
    assert tb_import in src
    assert src.index("if TYPE_CHECKING") < src.index(tb_import)
    # Module loaded headless (no hou present) and never bound hou/pdg globals.
    assert callable(build_perception_baseline)
    assert not hasattr(perception_baseline, "hou")
    assert not hasattr(perception_baseline, "pdg")
