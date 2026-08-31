"""test_memory_recall_honesty.py — BP1-HONESTY goalpost (docs/BATTLEPLAN.md §5).

MemoryPort recall (``query_and_filter``) can never return empty-success. Same
failure class as BASTION B1 (cook success-noop): a green light that cannot
report failure. Silent-empty recall was observed by Joe in the GUI on
2026-08-31; this file pins the honest envelope so that lie is unshippable:

* cannot OBSERVE the substrate -> UNAVAILABLE, ``error_message`` a gate name
  (env_unset | plugin_unregistered | layer_uncomposed);
* observed the layer, kept nothing -> SUCCESS, ``payload["hit"] is False`` with
  a ``reason`` (predicate_nomatch | quota_pruned) and ``candidates_seen``;
* kept results -> SUCCESS, ``payload["hit"] is True``.

Pure Python, stock pytest, no ``hou`` — the layer is driven through the
documented seams, never a live Moneta. A store that carries a ``_handle`` whose
``.ecs`` is None models a bound-but-uncomposed layer; overriding
``_fetch_raw_memories`` supplies the observed rows. The ratified §4 surface
(``query_and_filter(relation_keys, task_context_tokens)`` and ``STATUS``) is
untouched — the honesty rides in the envelope, not in a new surface.

TRIAGE's bucket, consumed via the BATTLEPLAN bus (finding n=18d0f229ca7d5418,
2026-08-31T12:55:13, body.bucket="env"), is a launch-path defect: the code side
is the honesty envelope only; the env remedy is
harness/battleplan/notes/LAUNCH_PATH_FIX.md.
"""

import inspect
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from synapse.loop import ports  # noqa: E402
from synapse.loop.ports import MONETA_URI_SCHEME, MemoryPort  # noqa: E402


URI = MONETA_URI_SCHEME + "/tmp/synapse_recall_honesty"


@pytest.fixture(autouse=True)
def clean_registry():
    """Every test starts and ends with an empty handle registry."""
    MemoryPort.release()
    yield
    MemoryPort.release()


class _LayerStore:
    """A Moneta-shaped store stand-in: carries a ``_handle`` whose ``.ecs`` is
    the memory layer. ``ecs=None`` models a bound store whose layer is not
    composed (the layer_uncomposed gate); a truthy ``ecs`` models an observable
    layer. Never touches disk, never imports Moneta."""

    def __init__(self, ecs):
        self._handle = types.SimpleNamespace(ecs=ecs)


def _bind(store):
    """A port bound to ``store`` for ``URI`` without opening a real substrate."""
    MemoryPort._handles[URI] = store
    return MemoryPort(URI)


# ---------------------------------------------------------------------------
# (a) memory layer deliberately absent -> UNAVAILABLE, layer_uncomposed
# ---------------------------------------------------------------------------

def test_layer_absent_is_unavailable():
    """A bound store whose ECS memory layer is not composed cannot be observed.
    Recall says so — UNAVAILABLE naming the gate — instead of shipping an empty
    list as if it were a real 'nothing recalled'. This exercises the real gate
    (_layer_observable reading _handle.ecs is None), not an override."""
    port = _bind(_LayerStore(ecs=None))
    result = port.query_and_filter(["rel"], ["tok"])

    assert result.status == "UNAVAILABLE"
    assert result.error_message == "layer_uncomposed"
    assert result.error_message in ports.RECALL_UNOBSERVABLE_REASONS
    # the defect it replaces: a SUCCESS carrying an empty list
    assert result.status != "SUCCESS"


# ---------------------------------------------------------------------------
# (b) non-matching predicate -> SUCCESS, hit False, predicate_nomatch
# ---------------------------------------------------------------------------

def test_nomatch_is_explicit():
    """The layer is observable and ran, but no candidate matched the relation
    keys. That is a real SUCCESS carrying hit=False and an explicit reason — not
    an empty list under a bare SUCCESS."""
    port = _bind(_LayerStore(ecs=object()))
    port._fetch_raw_memories = lambda keys: []  # predicate matched nothing

    result = port.query_and_filter(["absent-rel"], [])

    assert result.status == "SUCCESS"
    assert result.payload["hit"] is False
    assert result.payload["reason"] == "predicate_nomatch"
    assert result.payload["reason"] in ports.RECALL_NOMATCH_REASONS
    assert result.payload["candidates_seen"] == 0
    assert result.payload["candidates_seen"] >= 0
    assert result.payload["filtered_memories"] == []  # explicit, not a lie


def test_nomatch_quota_pruned_when_candidates_are_all_dropped():
    """Candidates matched the relation-key predicate, but PG-DRM dropped every
    one (here: exhausted at the utility floor). The reason distinguishes this
    from predicate_nomatch, and candidates_seen proves recall looked."""
    port = _bind(_LayerStore(ecs=object()))
    port._fetch_raw_memories = lambda keys: [
        {"id": "spent", "utility": 0.0, "protected_floor": 0.0, "blocked_tokens": []},
    ]  # utility 0.0 <= utility_floor 0.0 -> exhausted

    result = port.query_and_filter(["rel"], [])

    assert result.status == "SUCCESS"
    assert result.payload["hit"] is False
    assert result.payload["reason"] == "quota_pruned"
    assert result.payload["candidates_seen"] == 1
    assert result.payload["dropped"]["exhausted"] == 1
    assert result.payload["filtered_memories"] == []


# ---------------------------------------------------------------------------
# (c) known deposit -> SUCCESS, hit True, deposit in payload
# ---------------------------------------------------------------------------

def test_hit_is_explicit():
    """A recall that kept a deposit is SUCCESS with hit=True and the deposit in
    the payload."""
    port = _bind(_LayerStore(ecs=object()))
    port._fetch_raw_memories = lambda keys: [
        {"id": "known", "utility": 0.9, "protected_floor": 0.0, "blocked_tokens": []},
    ]

    result = port.query_and_filter(["rel"], [])

    assert result.status == "SUCCESS"
    assert result.payload["hit"] is True
    assert result.payload["count"] == 1
    assert result.payload["candidates_seen"] == 1
    assert [m["id"] for m in result.payload["filtered_memories"]] == ["known"]


# ---------------------------------------------------------------------------
# The crucible criterion: an empty list under a bare SUCCESS is impossible
# ---------------------------------------------------------------------------

def test_empty_list_under_bare_success_is_impossible():
    """No input makes recall return SUCCESS with an empty filtered_memories and
    no hit/reason. Empty is either UNAVAILABLE (could not observe) or SUCCESS
    with hit=False + a reason (observed, matched nothing) — never a bare empty
    SUCCESS that reads like a find of nothing."""
    # could-not-observe -> UNAVAILABLE, not SUCCESS
    p1 = _bind(_LayerStore(ecs=None))
    r1 = p1.query_and_filter([], [])
    assert not (r1.status == "SUCCESS" and not r1.payload.get("filtered_memories")
                and "hit" not in r1.payload)
    MemoryPort.release()

    # observed, kept nothing -> SUCCESS, but always hit=False + reason present
    p2 = _bind(_LayerStore(ecs=object()))
    p2._fetch_raw_memories = lambda keys: []
    r2 = p2.query_and_filter([], [])
    assert r2.status == "SUCCESS"
    assert r2.payload["filtered_memories"] == []
    assert r2.payload["hit"] is False
    assert "reason" in r2.payload


# ---------------------------------------------------------------------------
# The env/plugin gate is named too — the full §5 unobservable vocabulary
# ---------------------------------------------------------------------------

def test_moneta_env_gate_classifies_env_vs_plugin(monkeypatch):
    """env_unset when the package env never registered (neither knob present);
    plugin_unregistered when a knob is present but import still failed."""
    monkeypatch.delenv("MONETA_SRC", raising=False)
    monkeypatch.delenv("PXR_PLUGINPATH_NAME", raising=False)
    assert ports._moneta_env_gate() == "env_unset"

    monkeypatch.setenv("PXR_PLUGINPATH_NAME", "/some/schema")
    assert ports._moneta_env_gate() == "plugin_unregistered"


def test_bound_but_moneta_unimportable_names_the_env_gate(monkeypatch):
    """A bound port whose Moneta substrate would not import reports the canonical
    gate token (env_unset here), not a descriptive string and not empty-success.
    Drives the _guard classifier against the real bind-failure attributes,
    hermetically (no real _open)."""
    monkeypatch.delenv("MONETA_SRC", raising=False)
    monkeypatch.delenv("PXR_PLUGINPATH_NAME", raising=False)

    port = MemoryPort()  # start unbound, then set the bind-failure state _open would
    port._storage_uri = URI
    port._store = None
    port._bind_blocked = False
    port._bind_error = ("Moneta substrate not importable: <no moneta>; install "
                        "the moneta package or point $MONETA_SRC at its source root")

    result = port.query_and_filter(["rel"], ["tok"])

    assert result.status == "UNAVAILABLE"
    assert result.error_message == "env_unset"
    assert result.error_message in ports.RECALL_UNOBSERVABLE_REASONS


# ---------------------------------------------------------------------------
# The ratified §4 surface is byte-identical: signature + STATUS unchanged
# ---------------------------------------------------------------------------

def test_query_and_filter_signature_is_still_verbatim():
    """The honesty must not have drifted the pinned §4 signature."""
    params = [p for p in inspect.signature(MemoryPort.query_and_filter).parameters
              if p not in ("self", "cls")]
    assert params == ["relation_keys", "task_context_tokens"]


def test_status_set_is_still_the_ratified_three():
    assert set(ports.STATUS) == {"SUCCESS", "UNAVAILABLE", "BLOCKED"}
    # every honest recall result stays inside that set
    for r in (
        _bind(_LayerStore(ecs=None)).query_and_filter([], []),
    ):
        assert r.status in ports.STATUS
