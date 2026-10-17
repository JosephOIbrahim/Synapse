"""PRUNE-AUDIT-ON-FAILURE: a sleep pass that RAISES still leaves its prune record.

``MonetaBackedStore.run_sleep_pass`` is the one destructive memory op. It
enumerates the live rows, runs Moneta's pass, then diffs the survivors to build
the lossless :class:`PruneAudit`. Moneta's ``consolidation.run_pass`` prunes
(``ecs.remove`` + ``vector_index.delete``) BEFORE it stages, authors and
snapshots, so a pass can raise after rows are already gone from the ECS, and
the next ``save()`` persists them as gone. Unguarded, the survivor diff never
ran on that path: no audit, no log line, the pruned payloads unrecorded.

The guard: on any exception from the pass (KeyboardInterrupt and SystemExit
excepted), diff the survivors exactly as the success path does, log the same
record marked FAILED (with the payloads, since there is no return value to
carry them), and re-raise the ORIGINAL exception unchanged.

THE BITE: on the unguarded code the failing-pass cases raise as expected but
log no ``lossless-audit`` record, so they fail on the audit assertion. The
success-path and interrupt controls pass on both.

Fakes only. Nothing here imports ``moneta``: the handle is a double whose
``durability`` is None, so ``save()`` is a no-op and nothing touches disk. The
two failure shapes are a plain ``ValueError`` and a stand-in for pyo3's
``PanicException``, which derives from ``BaseException`` and so slips past any
``except Exception``.
"""

import json
import logging
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import moneta_store  # noqa: E402
from synapse.memory.models import Memory, MemoryType  # noqa: E402
from synapse.memory.moneta_store import MonetaBackedStore, PruneAudit  # noqa: E402


class PanicException(BaseException):
    """Stand-in for ``pyo3_runtime.PanicException`` (a native Rust panic).

    pyo3 derives it from ``BaseException`` on purpose, so ``except Exception``
    does not catch it. That is exactly the shape a native pass would raise.
    """


PanicException.__module__ = "pyo3_runtime"


# --------------------------------------------------------------------------- #
# Fakes: an ECS the pass can prune, and a handle whose pass prunes then raises
# --------------------------------------------------------------------------- #

class _FakeRow:
    """One ECS row: the two attributes the prune audit reads."""

    def __init__(self, entity_id, payload):
        self.entity_id = entity_id
        self.payload = payload


class _FakeECS:
    """Rows keyed by entity id, removable the way Moneta's run_pass prunes."""

    def __init__(self, rows):
        self._rows = {row.entity_id: row for row in rows}  # insertion-ordered
        self.poisoned = None  # once set, iter_rows raises it (an unreadable ECS)

    @property
    def n(self):
        return len(self._rows)

    def iter_rows(self):
        if self.poisoned is not None:
            raise self.poisoned
        return list(self._rows.values())

    def remove(self, entity_id):
        del self._rows[entity_id]


class _FakeHandle:
    """A Moneta handle double whose sleep pass prunes FIRST, then may raise.

    Mirrors the order in ``moneta.consolidation.run_pass``: the doomed rows
    leave the ECS, and whatever follows the prune (staging, authoring, the
    snapshot) is where ``raise_after_prune`` fires. ``durability = None``
    keeps ``save()`` a no-op.
    """

    durability = None

    def __init__(self, rows, doomed, *, raise_after_prune=None,
                 poison_after_prune=None, result=None):
        self.ecs = _FakeECS(rows)
        self._doomed = list(doomed)
        self._raise = raise_after_prune
        self._poison = poison_after_prune
        self._result = result

    def run_sleep_pass(self):
        for eid in self._doomed:
            self.ecs.remove(eid)
        if self._poison is not None:
            self.ecs.poisoned = self._poison
        if self._raise is not None:
            raise self._raise
        return self._result


# Three live rows; the pass removes the first and the last. The kept row sits
# between them so the audit's ordering is checked too.
_STAMP = "2026-10-01T00:00:00Z"
DOOMED_A = Memory(id="mem_doomed_a", created_at=_STAMP,
                  content="scratch note: try a cooler key", memory_type=MemoryType.NOTE)
KEPT = Memory(id="mem_keep", created_at=_STAMP,
              content="Decision: keep the rim light warm", memory_type=MemoryType.DECISION)
DOOMED_B = Memory(id="mem_doomed_b", created_at=_STAMP,
                  content="created /stage/key_light", memory_type=MemoryType.ACTION)
EID = {DOOMED_A.id: uuid.UUID(int=1), KEPT.id: uuid.UUID(int=2), DOOMED_B.id: uuid.UUID(int=3)}
DOOMED_IDS = [DOOMED_A.id, DOOMED_B.id]


def _store(doomed=tuple(DOOMED_IDS), **handle_kwargs):
    rows = [_FakeRow(EID[m.id], m.to_json()) for m in (DOOMED_A, KEPT, DOOMED_B)]
    handle = _FakeHandle(rows, [EID[m_id] for m_id in doomed], **handle_kwargs)
    # run_sleep_pass never embeds; the store only reads the embedder's id.
    return MonetaBackedStore(handle, SimpleNamespace(id="stub-embedder", dim=8))


def _result(attention_updated=0, staged=0):
    return SimpleNamespace(attention_updated=attention_updated, staged=staged)


@pytest.fixture
def audit_log():
    """Every record the store's module logger emits during the test.

    Attached to that logger directly, so the capture does not depend on how
    the rest of the session configured propagation.
    """
    log = logging.getLogger("synapse.memory.moneta_store")
    records = []

    class _Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = _Capture(level=logging.DEBUG)
    previous_level = log.level
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        log.removeHandler(handler)
        log.setLevel(previous_level)


@pytest.fixture
def success_yardstick():
    """What the SUCCESS path records for exactly the removal the failing
    passes perform. Built in setup, so its own log line is not mistaken for
    one the failing pass wrote."""
    expected = _store(result=_result()).run_sleep_pass()
    assert expected.pruned_ids == DOOMED_IDS  # the twin really pruned both
    return expected


def _lossless_audit_records(records):
    return [r for r in records if "lossless-audit" in r.getMessage()]


# --------------------------------------------------------------------------- #
# Binding: the bite is only evidence against THIS checkout's module
# --------------------------------------------------------------------------- #

def test_module_under_test_is_this_checkouts_copy():
    """An editable install can shadow the tree under test. Prove it does not."""
    bound = Path(moneta_store.__file__).resolve()
    print(f"moneta_store bound from: {bound}")
    assert bound.is_relative_to((_ROOT / "python").resolve()), (
        f"synapse.memory.moneta_store loaded from {bound}, not from "
        f"{_ROOT / 'python'}: any pass/fail here describes another tree"
    )


# --------------------------------------------------------------------------- #
# Controls: the success path is unchanged
# --------------------------------------------------------------------------- #

def test_success_path_audit_is_unchanged(audit_log):
    store = _store(result=_result(attention_updated=4, staged=1))

    audit = store.run_sleep_pass()

    assert type(audit) is PruneAudit
    assert audit.pruned_ids == DOOMED_IDS
    assert audit.pruned_entity_ids == [str(EID[m_id]) for m_id in DOOMED_IDS]
    assert audit.pruned_payloads == {
        str(EID[DOOMED_A.id]): DOOMED_A.to_json(),
        str(EID[DOOMED_B.id]): DOOMED_B.to_json(),
    }
    assert audit.pruned_types == {DOOMED_A.id: "note", DOOMED_B.id: "action"}
    assert (audit.count_before, audit.count_after) == (3, 1)
    assert (audit.attention_updated, audit.staged) == (4, 1)
    assert audit.pruned == 2
    assert getattr(audit, "failed", False) is False
    # The success record, byte for byte as it was logged before the guard.
    assert [(r.levelno, r.getMessage()) for r in _lossless_audit_records(audit_log)] == [
        (logging.WARNING,
         "moneta.prune lossless-audit pruned=2 staged=1 before=3 after=1 "
         "ids=['mem_doomed_a', 'mem_doomed_b']"),
    ]


def test_success_path_without_prunes_is_unchanged(audit_log):
    store = _store(doomed=(), result=_result(attention_updated=2, staged=0))

    audit = store.run_sleep_pass()

    assert type(audit) is PruneAudit
    assert audit.pruned == 0 and audit.pruned_ids == [] and audit.pruned_payloads == {}
    assert (audit.count_before, audit.count_after) == (3, 3)
    assert _lossless_audit_records(audit_log) == []
    assert [r.getMessage() for r in audit_log if r.levelno == logging.INFO] == [
        "moneta.sleep_pass pruned=0 staged=0 attended=2 n=3",
    ]


# --------------------------------------------------------------------------- #
# The bite: a pass that raises after pruning still leaves the lossless record
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "make_exc",
    [
        lambda: ValueError("USD authoring failed after the prune"),
        lambda: PanicException("ecs.rs: index out of bounds"),
    ],
    ids=["ValueError", "pyo3-PanicException"],
)
def test_failed_pass_records_the_prune_audit_and_reraises_unchanged(
        success_yardstick, audit_log, make_exc):
    expected = success_yardstick
    boom = make_exc()
    original_args = boom.args
    store = _store(raise_after_prune=boom)

    with pytest.raises(type(boom)) as excinfo:
        store.run_sleep_pass()

    # 1. The ORIGINAL exception propagates, unchanged and unwrapped.
    assert excinfo.value is boom
    assert excinfo.value.args == original_args
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None

    # 2. The rows really are gone: this is the loss the record must cover.
    assert store.count() == 1

    # 3. The lossless record exists, marked failed, and says what the success
    #    path would have said about the same two rows.
    records = _lossless_audit_records(audit_log)
    assert records, (
        "a sleep pass that raised AFTER pruning logged no lossless-audit record: "
        "the two pruned memories (ids and payloads) are unrecorded"
    )
    assert len(records) == 1
    record = records[0]
    msg = record.getMessage()
    assert record.levelno >= logging.WARNING
    assert "FAILED" in msg
    assert type(boom).__name__ in msg
    assert f"pruned={expected.pruned} " in msg
    assert f"before={expected.count_before} after={expected.count_after} " in msg
    assert f"ids={expected.pruned_ids!r}" in msg
    # No return value carries them, so the record carries the payloads.
    assert json.loads(msg.split(" payloads=", 1)[1]) == expected.pruned_payloads


@pytest.mark.parametrize(
    "secondary",
    [RuntimeError("ECS desync after a partial prune"), PanicException("ECS poisoned")],
    ids=["RuntimeError", "pyo3-PanicException"],
)
def test_unreadable_ecs_after_a_failed_pass_never_masks_the_original(audit_log, secondary):
    boom = ValueError("USD authoring failed after the prune")
    store = _store(raise_after_prune=boom, poison_after_prune=secondary)

    with pytest.raises(ValueError) as excinfo:
        store.run_sleep_pass()

    # The diff failed too; the caller must still get the pass's own exception.
    assert excinfo.value is boom
    assert excinfo.value.__context__ is None
    # Which rows went is unknowable now, so the record says that and keeps the
    # whole pre-pass id set for forensics.
    records = [r for r in _lossless_audit_records(audit_log) if r.levelno >= logging.ERROR]
    assert records, "the undiffable failed pass left no lossless-audit record"
    msg = records[-1].getMessage()
    assert "FAILED" in msg and "UNKNOWN" in msg
    for mem_id in (DOOMED_A.id, KEPT.id, DOOMED_B.id):
        assert mem_id in msg


# --------------------------------------------------------------------------- #
# Control: an operator interrupt is not swallowed or transformed
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "make_exc", [KeyboardInterrupt, lambda: SystemExit(3)],
    ids=["KeyboardInterrupt", "SystemExit"],
)
def test_interrupts_from_the_pass_propagate_untouched(make_exc):
    boom = make_exc()
    store = _store(raise_after_prune=boom)

    with pytest.raises(type(boom)) as excinfo:
        store.run_sleep_pass()

    assert excinfo.value is boom
    assert excinfo.value.__context__ is None
