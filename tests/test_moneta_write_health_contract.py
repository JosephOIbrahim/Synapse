"""R-030 — a Moneta primary that is refusing writes must never read green.

The B6 write-health surfaces (``write_plane.read_store_write_health``,
``synapse_memory_status`` and the panel health strip) ask the LIVE store whether
it is accepting writes. ``MemoryStore`` answers through the pinned
``is_degraded`` / ``degraded_reason`` / ``health()`` contract; ``MonetaBackedStore``
— the PRIMARY substrate whenever ``SYNAPSE_MEMORY_BACKEND=moneta`` — had no such
contract, so every reader fell through to the JSONL dual-write safety net. A
healthy mirror then vouched for a primary that refused checked writes:

  * ``_load_issue`` — a quarantined snapshot / unreplayable WAL: every
    ``_require_durable`` write raises;
  * ``_strict_deposit_failed`` — a partial backend deposit; the store refuses
    checked writes "until restart";
  * duplicate identities — the primary's own strict consumers
    (``memory_lifecycle._records``, ``add_durable_if_absent``) refuse the WHOLE
    store while one id sits on two rows.

None of the three moved a health surface. Each degraded primary below is
constructed on a FAKE handle (Moneta is not importable on the stock
interpreter, and the adapter is pure logic over an injected handle — the same
shape ``test_memory_identity_convergence.py`` uses), and every surface is
asserted non-ok. The healthy control proves the guards are not vacuous: the same
surfaces can say ok.
"""

import sys
import types
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory.embedding import HashEmbedder  # noqa: E402
from synapse.memory.models import Memory, MemoryType  # noqa: E402
from synapse.memory.moneta_store import MonetaBackedStore  # noqa: E402
from synapse.panel import health_strip as hs  # noqa: E402
from synapse.server import write_plane as wp  # noqa: E402

STAMP = "2026-11-20T00:00:00Z"
LOAD_ISSUE = "A quarantined snapshot needs recovery before checked recall"


# ---------------------------------------------------------------------------
# Fakes: the adapter's documented handle surface, no moneta import
# ---------------------------------------------------------------------------

class _FakeRow:
    def __init__(self, entity_id, payload):
        self.entity_id = entity_id
        self.payload = payload


class _FakeECS:
    def __init__(self):
        self._rows = {}
        self._next = 0

    @property
    def n(self):
        return len(self._rows)

    def iter_rows(self):
        return list(self._rows.values())

    def deposit(self, payload, embedding, protected_floor=0.0):
        self._next += 1
        entity_id = "eid-%03d" % self._next
        self._rows[entity_id] = _FakeRow(entity_id, payload)

    def remove(self, entity_id):
        del self._rows[entity_id]


class _Durability:
    def __init__(self):
        self.snapshots = 0

    def snapshot_ecs(self, ecs):
        self.snapshots += 1


class _FakeHandle:
    def __init__(self, rows=(), *, durable=True):
        self.ecs = _FakeECS()
        for row in rows:
            self.ecs._rows[row.entity_id] = row
        self.durability = _Durability() if durable else None

    def deposit(self, payload, embedding, protected_floor=0.0):
        self.ecs.deposit(payload, embedding, protected_floor=protected_floor)


class _HealthyContract:
    """A second store that carries the pinned contract and says it is fine."""

    def health(self):
        return {"degraded": False, "reason": "", "writable": True,
                "records": 3, "rejected_writes": 0, "overwrote_prior": 0}

    @property
    def is_degraded(self):
        return False

    @property
    def degraded_reason(self):
        return ""


class _SilentMonetaFacade:
    """A Moneta-shaped facade with a healthy mirror and NO health contract.

    This is the pre-repair shape of ``MonetaBackedStore``: the primary cannot
    answer, and the JSONL safety net can. A net is not the primary.
    """

    _handle = types.SimpleNamespace(durability=object())

    def __init__(self, jsonl_net):
        self._jsonl_net = jsonl_net

    def count(self):
        return 3


def _store(rows=(), *, durable=True):
    handle = _FakeHandle(rows, durable=durable)
    return MonetaBackedStore(handle, HashEmbedder(dim=8)), handle


def _row(entity_id, memory):
    return _FakeRow(entity_id, memory.to_json())


def _duplicated_store():
    """One identity on two rows (the strict consumers refuse this store)."""
    dupe = Memory(id="mem_dup", content="Decision: keep the warm rim light",
                  memory_type=MemoryType.DECISION, created_at=STAMP,
                  tags=["decision", "lighting"], source="user")
    dupe_stripped = Memory(id="mem_dup", content="Decision: keep the warm rim light",
                           memory_type=MemoryType.DECISION, created_at=STAMP,
                           tags=[], source="auto")
    single = Memory(id="mem_single", content="a note with one row",
                    memory_type=MemoryType.NOTE, created_at=STAMP)
    return _store([_row("eid-rich", dupe), _row("eid-stripped", dupe_stripped),
                   _row("eid-single", single)])


def _with_load_issue(store, _handle):
    store._load_issue = LOAD_ISSUE


def _with_strict_deposit_failed(store, _handle):
    store._strict_deposit_failed = True


def _with_duplicates(store, _handle):
    """Swap in the two-row duplicate store built by ``_duplicated_store``."""
    dupe, _ = _duplicated_store()
    store._handle = dupe._handle


DEGRADED_PRIMARIES = [
    pytest.param(_with_load_issue, id="load-issue"),
    pytest.param(_with_strict_deposit_failed, id="strict-deposit-failed"),
    pytest.param(_with_duplicates, id="duplicate-identities"),
]


# ---------------------------------------------------------------------------
# The three surfaces, driven the way production drives them
# ---------------------------------------------------------------------------

def _memory_status(monkeypatch, store):
    """``synapse_memory_status`` through its real handler."""
    from synapse.memory import scene_memory
    from synapse.server.handlers_memory import MemoryHandlerMixin

    monkeypatch.setattr(scene_memory, "get_memory_status", lambda scene_dir, project_dir: {
        "project": {"evolution": "none"},
        "scene": {"evolution": "none"},
        "agent": {"status": "idle"},
    })

    class _Handler(MemoryHandlerMixin):
        def __init__(self, bridge):
            self._bridge_obj = bridge

        @staticmethod
        def _scene_paths():
            return {"hip_path": "scene.hip", "hip_dir": "scene",
                    "job_path": "job", "job_root": "job"}

        def _memory_on_main(self, callback):
            return callback(self._bridge_obj)

    bridge = types.SimpleNamespace(_synapse=types.SimpleNamespace(store=store))
    return _Handler(bridge)._handle_memory_status({})


def _panel_fact(monkeypatch, store):
    """The panel strip's memory fact, read off the live singleton."""
    from synapse.memory import store as store_mod

    monkeypatch.setattr(store_mod, "_global_synapse",
                        types.SimpleNamespace(store=store), raising=False)
    monkeypatch.setattr(store_mod, "backend_fallback", lambda: None)
    return hs._gather_memory()


# ---------------------------------------------------------------------------
# 1. Every degraded primary reads non-ok on every surface
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("degrade", DEGRADED_PRIMARIES)
def test_degraded_primary_reads_non_ok_on_every_surface(
        monkeypatch, degrade):
    store, handle = _store()
    degrade(store, handle)

    # The store answers, and it says it is degraded/unwritable.
    health = store.health()
    assert health["degraded"] is True
    assert health["writable"] is False
    assert health["reason"], "a degraded store must say why"
    assert store.is_degraded is True
    assert store.degraded_reason == health["reason"]

    # write_plane's shared reader — the source of synapse_memory_status.
    reading = wp.read_store_write_health(store)
    assert reading["status"] != "ok"
    assert reading["accepting_writes"] is False

    # synapse_memory_status, through its real handler.
    status = _memory_status(monkeypatch, store)
    assert status["health"]["status"] != "ok"
    assert status["health"]["accepting_writes"] is False

    # The panel health strip.
    fact = _panel_fact(monkeypatch, store)
    assert isinstance(fact["write_health"], dict), fact
    assert fact["write_health"]["sick"] is True
    assert hs.cell_memory(fact).verdict != hs.Verdict.OK


def test_healthy_primary_reads_ok_on_every_surface(monkeypatch):
    """The control: the same surfaces CAN say ok, so the guards are not vacuous."""
    store, _handle = _store()

    health = store.health()
    assert health["degraded"] is False
    assert health["writable"] is True
    assert health["reason"] == ""
    assert store.is_degraded is False

    reading = wp.read_store_write_health(store)
    assert reading["status"] == "ok"
    assert reading["accepting_writes"] is True

    status = _memory_status(monkeypatch, store)
    assert status["health"]["status"] == "ok"
    assert status["health"]["accepting_writes"] is True

    fact = _panel_fact(monkeypatch, store)
    assert fact["write_health"] == {"sick": False, "reason": ""}
    assert hs.cell_memory(fact).verdict == hs.Verdict.OK


# ---------------------------------------------------------------------------
# 2. The incident shape: a healthy JSONL net must not vouch for the primary
# ---------------------------------------------------------------------------

def test_degraded_primary_outranks_a_healthy_jsonl_net(monkeypatch):
    store, _handle = _store()
    store._load_issue = LOAD_ISSUE
    store._jsonl_net = _HealthyContract()   # the mirror is fine; the primary is not

    reading = wp.read_store_write_health(store)
    assert reading["status"] == "degraded"
    assert reading["accepting_writes"] is False
    assert "MonetaBackedStore" in reading["sources"]


def test_a_silent_primary_never_resolves_to_ok(monkeypatch):
    """No health contract on the serving object, a healthy net behind it."""
    facade = _SilentMonetaFacade(jsonl_net=_HealthyContract())

    reading = wp.read_store_write_health(facade)
    assert reading["status"] != "ok"
    assert reading["accepting_writes"] is not True

    # The mirror answered, but the primary did not: the panel must go UNKNOWN,
    # not green on the net's say-so.
    assert hs._read_write_health(facade) is None

    fact = {"fallback": None, "backend": "MonetaBackedStore",
            "moneta_live": True, "write_health": hs._read_write_health(facade)}
    assert hs.cell_memory(fact).verdict == hs.Verdict.UNKNOWN


# ---------------------------------------------------------------------------
# 3. The contract itself: shape, fail-closed probe, and a clearable verdict
# ---------------------------------------------------------------------------

def test_health_contract_shape_and_fail_closed_probe():
    class _PoisonedECS:
        @property
        def n(self):
            raise RuntimeError("ecs corrupt")

        def iter_rows(self):
            raise RuntimeError("ecs corrupt")

    handle = types.SimpleNamespace(ecs=_PoisonedECS(), durability=None)
    store = MonetaBackedStore(handle, HashEmbedder(dim=8))

    health = store.health()
    assert set(health) >= {"degraded", "reason", "writable", "records",
                           "rejected_writes", "overwrote_prior"}
    # A probe that cannot complete is sick and unwritable — never a green blank.
    assert health["degraded"] is True
    assert health["writable"] is False
    assert "health probe failed" in health["reason"]
    assert health["records"] == -1

    reading = wp.read_store_write_health(store)
    assert reading["status"] == "degraded"
    assert reading["accepting_writes"] is False


def test_repairing_duplicates_clears_the_degraded_verdict(monkeypatch):
    """Degraded is a read of live state, not a latch: converge and it is ok."""
    store, _handle = _duplicated_store()
    assert store.is_degraded is True

    report = store.repair_duplicate_identities(apply=True)
    assert report["applied"] is True
    assert report["remaining_duplicate_ids"] == []

    assert store.health()["degraded"] is False
    reading = wp.read_store_write_health(store)
    assert reading["status"] == "ok"
    assert reading["accepting_writes"] is True
