"""test_memory_port_v51.py — pins MemoryPort against the Moneta substrate laws.

THE LOOP v5.1 §1 states Moneta's prohibitions as: no LLM calls, no background
threads, no implicit config, **max 1 handle per storage_uri**, no 4th decay
point. This file pins each of those at the seam, plus the §4 contract surface
and the honest-seam rule (absent substrate reports UNAVAILABLE/BLOCKED, never a
fabricated SUCCESS).

Hermetic: nothing here requires a live Moneta. Handle-cache identity is proved
by injecting a sentinel into the registry, and PG-DRM is proved by overriding
the one documented fetch seam. Tests that would need the real substrate are
skipped, never faked.
"""

import inspect
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from synapse.loop import ports  # noqa: E402
from synapse.loop.ports import MONETA_URI_SCHEME, MemoryPort  # noqa: E402


URI_A = MONETA_URI_SCHEME + "/tmp/synapse_memory_a"
URI_B = MONETA_URI_SCHEME + "/tmp/synapse_memory_b"


@pytest.fixture(autouse=True)
def clean_registry():
    """Every test starts and ends with an empty handle registry."""
    MemoryPort.release()
    yield
    MemoryPort.release()


class _FakeStore:
    """Stand-in handle. Never touches disk, never imports Moneta."""

    def __init__(self, name="fake"):
        self.name = name
        self.closed = False
        self.added = []
        self._protected_floor = 0.9

    def add(self, memory):
        self.added.append(memory)
        return "mem-1"

    def close(self):
        self.closed = True


def _bound_port(store=None, **kwargs):
    """A port bound to `store` for URI_A without opening a real substrate."""
    store = store or _FakeStore()
    MemoryPort._handles[URI_A] = store
    return MemoryPort(URI_A, **kwargs), store


# ---------------------------------------------------------------------------
# §4 contract surface — the signature is pinned VERBATIM
# ---------------------------------------------------------------------------

def test_query_and_filter_signature_is_verbatim():
    """§4 pins (relation_keys, task_context_tokens). Filter tuning lives on the
    constructor precisely so this surface cannot drift."""
    params = [p for p in inspect.signature(MemoryPort.query_and_filter).parameters
              if p not in ("self", "cls")]
    assert params == ["relation_keys", "task_context_tokens"]


def test_constructor_stays_zero_arg_constructible():
    """The contract surface must remain constructible with no arguments;
    storage_uri is optional binding, never an implicit default store."""
    port = MemoryPort()
    assert port.storage_uri is None
    assert port.handle is None


# ---------------------------------------------------------------------------
# Moneta law: max 1 handle per storage_uri
# ---------------------------------------------------------------------------

def test_same_uri_yields_the_same_handle():
    """Two ports on one URI share ONE handle — that is the law, expressed as
    idempotence rather than as an exception."""
    first, store = _bound_port()
    second = MemoryPort(URI_A)
    assert first.handle is store
    assert second.handle is store


def test_distinct_uris_are_independent_handles():
    """The law bounds handles PER storage_uri, not stores per process. Project
    memory and scene memory legitimately coexist."""
    a_store, b_store = _FakeStore("a"), _FakeStore("b")
    MemoryPort._handles[URI_A] = a_store
    MemoryPort._handles[URI_B] = b_store
    assert MemoryPort(URI_A).handle is a_store
    assert MemoryPort(URI_B).handle is b_store
    assert a_store is not b_store


def test_release_closes_and_evicts_the_handle():
    _, store = _bound_port()
    MemoryPort.release(URI_A)
    assert store.closed is True
    assert URI_A not in MemoryPort._handles


# ---------------------------------------------------------------------------
# Host law: the main thread owns store initialization
# ---------------------------------------------------------------------------

def test_off_main_thread_binding_is_refused():
    """Panel and worker threads must read over the observation channel, never
    bind a second owner for the store."""
    captured = {}

    def worker():
        port = MemoryPort(URI_A)
        captured["result"] = port.query_and_filter(["rel"], ["tok"])

    t = threading.Thread(target=worker, name="panel-worker")
    t.start()
    t.join()

    result = captured["result"]
    assert result.status == "BLOCKED"
    assert "main-thread only" in result.error_message
    assert "panel-worker" in result.error_message


# ---------------------------------------------------------------------------
# Honest seam: absence is reported, never fabricated as SUCCESS
# ---------------------------------------------------------------------------

def test_unbound_port_reports_unavailable_naming_pg_drm():
    result = MemoryPort().query_and_filter(["rel"], ["tok"])
    assert result.status == "UNAVAILABLE"
    assert "PG-DRM" in result.error_message
    assert result.payload is None


def test_malformed_uri_is_blocked_and_named():
    port = MemoryPort("file:///tmp/not-a-moneta-uri")
    result = port.query_and_filter(["rel"], ["tok"])
    assert result.status == "BLOCKED"
    assert "not a Moneta URI" in result.error_message


def test_unbound_wake_and_settlement_never_fabricate_success():
    port = MemoryPort()
    assert port.wake_scene_relations(["/stage/geo1"]).status == "UNAVAILABLE"
    assert port.deposit_settlement("claim-1", "HIT").status == "UNAVAILABLE"


# ---------------------------------------------------------------------------
# PG-DRM: deterministic, zero-LLM context filtering
# ---------------------------------------------------------------------------

def test_pg_drm_drops_contaminated_context_deterministically():
    """Cross-task contamination is decided by exact token-set intersection.
    No inference, no scoring model, no network."""
    port, _ = _bound_port()
    port._fetch_raw_memories = lambda keys: [
        {"id": 1, "utility": 0.9, "protected_floor": 0.0,
         "blocked_tokens": ["stale_context"]},
        {"id": 2, "utility": 0.9, "protected_floor": 0.0,
         "blocked_tokens": []},
    ]

    result = port.query_and_filter(
        relation_keys=["/stage/geo1"],
        task_context_tokens=["stale_context"],
    )

    assert result.status == "SUCCESS"
    assert result.payload["count"] == 1
    assert result.payload["filtered_memories"][0]["id"] == 2
    assert result.payload["dropped"]["contaminated"] == 1


def test_pg_drm_is_deterministic_across_repeated_calls():
    port, _ = _bound_port()
    port._fetch_raw_memories = lambda keys: [
        {"id": i, "utility": 0.5, "protected_floor": 0.0,
         "blocked_tokens": ["x"] if i % 2 else []}
        for i in range(10)
    ]
    runs = [port.query_and_filter(["k"], ["x"]).payload["filtered_memories"]
            for _ in range(5)]
    ids = [[m["id"] for m in r] for r in runs]
    assert all(run == ids[0] for run in ids), "PG-DRM output is not deterministic"


def test_pg_drm_drops_exhausted_entries_at_the_utility_floor():
    port, _ = _bound_port(utility_floor=0.25)
    port._fetch_raw_memories = lambda keys: [
        {"id": "alive", "utility": 0.30, "protected_floor": 0.0, "blocked_tokens": []},
        {"id": "spent", "utility": 0.10, "protected_floor": 0.0, "blocked_tokens": []},
    ]
    payload = port.query_and_filter([], []).payload
    assert [m["id"] for m in payload["filtered_memories"]] == ["alive"]
    assert payload["dropped"]["exhausted"] == 1


def test_pg_drm_drops_unevaluable_rather_than_passing_it():
    """A utility that cannot be read is not 'fine'. Mirrors GATE_POLICY: an
    unevaluable value blocks rather than passing silently."""
    port, _ = _bound_port()
    port._fetch_raw_memories = lambda keys: [
        {"id": "no-utility", "protected_floor": 0.0, "blocked_tokens": []},
        {"id": "bad-utility", "utility": "high", "protected_floor": 0.0,
         "blocked_tokens": []},
        {"id": "ok", "utility": 0.5, "protected_floor": 0.0, "blocked_tokens": []},
    ]
    payload = port.query_and_filter([], []).payload
    assert [m["id"] for m in payload["filtered_memories"]] == ["ok"]
    assert payload["dropped"]["unevaluable"] == 2


# ---------------------------------------------------------------------------
# Moneta law: no 4th decay point
# ---------------------------------------------------------------------------

def _code_names(module):
    """Identifiers in a module's EXECUTABLE source.

    Tokenizing and keeping only NAME tokens drops comments and string
    literals, so a structural guard tests what the code does and never trips
    on prose that merely describes it (a docstring may quote the decay
    formula; the code may not implement it).
    """
    import io
    import tokenize

    reader = io.StringIO(inspect.getsource(module)).readline
    return {tok.string for tok in tokenize.generate_tokens(reader)
            if tok.type == tokenize.NAME}


def test_ports_module_contains_no_decay_arithmetic():
    """Decay is evaluated at exactly three places inside Moneta over one pure
    function. A second implementation here would be the 4th decay point the
    blueprint forbids, so the seam must READ utility, never recompute it."""
    names = _code_names(ports)
    for forbidden in ("math", "exp", "expm1", "log", "pow", "half_life"):
        assert forbidden not in names, \
            f"ports.py computes decay ({forbidden!r}) — that is a 4th decay point"


def test_protected_floor_is_a_floor_not_a_drop_threshold():
    """U_now = max(protected_floor, U_last * exp(-λΔt)), so utility can never
    fall below the floor. A protected entry must survive filtering."""
    port, _ = _bound_port(utility_floor=0.5)
    port._fetch_raw_memories = lambda keys: [
        {"id": "protected", "utility": 0.9, "protected_floor": 0.9,
         "blocked_tokens": []},
    ]
    payload = port.query_and_filter([], []).payload
    assert payload["count"] == 1, "a floored (protected) entry was dropped"
    assert payload["dropped"]["exhausted"] == 0


# ---------------------------------------------------------------------------
# Settlement deposits (blueprint §3 step 9)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("outcome", ["HIT", "MISS", "UNRESOLVABLE"])
def test_settlement_accepts_the_three_blueprint_outcomes(outcome):
    port, store = _bound_port()
    result = port.deposit_settlement("claim-7", outcome)
    assert result.status == "SUCCESS"
    assert result.payload["deposited"]["outcome"] == outcome
    assert len(store.added) == 1


@pytest.mark.parametrize("outcome", ["hit", "PASS", "", None, "PENDING"])
def test_settlement_refuses_invented_outcomes(outcome):
    """Never coerce an unknown verdict into a known one."""
    port, store = _bound_port()
    result = port.deposit_settlement("claim-7", outcome)
    assert result.status == "BLOCKED"
    assert store.added == []


def test_settlement_validates_claim_id_and_floor():
    port, _ = _bound_port()
    assert port.deposit_settlement("", "HIT").status == "BLOCKED"
    assert port.deposit_settlement("c", "HIT", protected_floor=1.5).status == "BLOCKED"
    assert port.deposit_settlement("c", "HIT", protected_floor=True).status == "BLOCKED"


def test_settlement_reports_the_floor_the_store_actually_applied():
    """The requested floor is recorded, the effective floor is reported. One
    authority owns the rule (moneta_store), and the port does not shadow it."""
    port, store = _bound_port()
    payload = port.deposit_settlement("claim-7", "HIT", protected_floor=0.2).payload
    assert payload["deposited"]["requested_protected_floor"] == 0.2
    assert payload["effective_protected_floor"] == store._protected_floor


# ---------------------------------------------------------------------------
# Wake (blueprint §3 step 2)
# ---------------------------------------------------------------------------

def test_wake_with_no_matching_relations_is_success_not_failure():
    """Step 2's declared fallback is 'proceed with flat prompt', so an empty
    woken set is a real answer, not an error."""
    port, _ = _bound_port()
    port._fetch_raw_memories = lambda keys: []
    result = port.wake_scene_relations(["/stage/nothing_here"])
    assert result.status == "SUCCESS"
    assert result.payload["woken_keys"] == []
    assert result.payload["count"] == 0


def test_wake_returns_ids_for_matching_relations():
    port, _ = _bound_port()
    port._fetch_raw_memories = lambda keys: [{"id": "m1"}, {"id": "m2"}]
    payload = port.wake_scene_relations(["/stage/geo1"]).payload
    assert payload["woken_keys"] == ["m1", "m2"]
    assert payload["requested_keys"] == ["/stage/geo1"]


# ---------------------------------------------------------------------------
# Zero-LLM guarantee, structurally
# ---------------------------------------------------------------------------

def test_memory_seam_imports_no_model_client():
    names = _code_names(ports)
    for forbidden in ("anthropic", "openai", "requests", "httpx", "urllib", "socket"):
        assert forbidden not in names, \
            f"ports.py references {forbidden!r} — Moneta's zero-LLM rule forbids it"


def test_memory_seam_spawns_no_background_thread():
    """Moneta forbids background threads. A lock guards re-entrancy on the
    handle cache; nothing here starts a thread."""
    names = _code_names(ports)
    for forbidden in ("Thread", "Timer", "ThreadPoolExecutor", "Process"):
        assert forbidden not in names, \
            f"ports.py references {forbidden!r} — Moneta's no-background-threads rule forbids it"
