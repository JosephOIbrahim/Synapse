"""INC-2026-09-17 — the regression gate for the two-day DEGRADED memory store.

WHAT HAPPENED
-------------
Between 2026-09-15 15:09 and 2026-09-17 15:53 a live ``MemoryStore`` sat
DEGRADED and refused EVERY write. The only symptom was one ERROR line in a log
nobody reads. Two days of session memory were never recorded.

The chain, end to end:

1. ``MemoryStore.add`` REPLACES ``_memories[id]`` in RAM but APPENDS an
   unconditional new line to the write buffer. Adding the same id twice with
   different content therefore leaves TWO lines on disk carrying one identity.
2. Nothing is visibly wrong yet — the running process is fine. That is what made
   this so expensive: the damage only lands on the NEXT load.
3. ``MemoryStore._load`` (store.py:355-362) canonicalizes each record and raises
   ``conflicting duplicate memory identity`` the moment a repeated id arrives
   with a different canonical form.
4. That ValueError is caught per-line into ``unreadable``, and store.py:396-401
   degrades the WHOLE store on a non-empty ``unreadable`` list. The C1 guard is
   doing exactly what it was built to do — refuse to let a partial read
   authorize a rewrite that would destroy still-recoverable bytes.
5. ``_require_writable_load`` then raises on every subsequent write, forever,
   until a human edits the file.

ONE bad line is enough. The guard is correct. The write that fed it was not.

WHY THIS FILE EXISTS
--------------------
The post-incident audit found ZERO coverage for the entire failure class::

    grep -rn "conflicting duplicate memory identity" --include=*.py tests/  -> no hits
    grep -rln _match_memory tests/                                          -> empty

A guard whose TRIGGER is never exercised is a guard nobody can regress safely.
That absence is why a one-write defect cost two days. This file is the gate that
should have existed: it drives the real write path, reloads in a second store
object (the reload is the whole point — the original bug is invisible in the
process that caused it), and pins the operator-visible contract that would have
surfaced the outage in seconds instead of days.

WHAT EACH LANE IS PINNED FOR
----------------------------
B1/B2  the write that produced the duplicate line, and the reload that must
       survive it (:func:`test_add_twice_with_differing_payload_does_not_degrade_on_reload`)
B1     the automatic consolidation prune must be OFF by default
       (:func:`test_automatic_consolidation_prune_does_not_run_by_default`)
B3/B6  the ``health()`` contract both lanes build to, in BOTH states
B4     ``knowledge._match_memory`` calls ``SynapseMemory.search`` with a
       signature that actually exists — today it does not, and the fallback
       swallows the TypeError so the operator sees a silent "no memory"

MEASURED: EVERY TEST HERE WAS CONFIRMED RED AGAINST THE UNFIXED CODE
--------------------------------------------------------------------
A regression test that passes both before and after the repair is worthless, and
these were written while the repair lanes were already editing the same checkout
— so "it is green" proves nothing on its own. Each assertion was therefore run
against ``git show HEAD:`` copies of the three modules, loaded side by side with
the working tree and never replacing it (2026-09-17)::

    HEAD store.py     two adds of one id  -> 2 lines on disk
                      reload              -> _degraded_load True
                                             "line 2: conflicting duplicate memory identity"
                      write after reload  -> RuntimeError: Refusing to write ... DEGRADED
                      health()/is_degraded-> absent
    HEAD knowledge.py _match_memory(...)  -> None, swallowing
                                             "TypeError: SynapseMemory.search() got an
                                              unexpected keyword argument 'text'"
                      lookup().found      -> False
    HEAD moneta_store the 100th add       -> run_sleep_pass() RAN (prune fired unasked)

That is this file failing, for exactly the reasons its test names claim.

IMPORT IDIOM
------------
``MemoryStore`` is loaded via ``importlib`` spec into a PRIVATE module object,
mirroring ``tests/test_store_degraded_load.py`` (the closest sibling — it pins
the other half of the same guard). Two reasons, both load-bearing here:

* it avoids the package ``__init__`` eager-``hou`` import, and
* it gives this file its own ``_crypto_instance`` cache, so the fixture can pin
  crypto OFF without touching the shared ``synapse.memory.store`` module other
  tests bind to. Plaintext on disk is a PRECONDITION of these tests: an active
  ``SYNAPSE_ENCRYPTION_KEY`` would degrade the hand-written fixtures for the
  wrong reason and turn a real assertion into a coincidence.

The knowledge/``SynapseMemory`` tests use the ordinary package import (the
``tests/test_w3_store_contract.py`` idiom) because they span modules and need
the REAL ``SynapseMemory.search`` signature as the authority.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_BASE = _ROOT / "python" / "synapse"
if str(_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(_ROOT / "python"))


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def store_mod():
    """A private copy of ``synapse.memory.store`` with crypto pinned OFF.

    ``_get_crypto()`` caches into the module global ``_crypto_instance``; setting
    it to ``None`` (rather than the ``_CRYPTO_NOT_CHECKED`` sentinel) means every
    read and write in this file is plaintext regardless of whether the developer
    or CI runner has ``SYNAPSE_ENCRYPTION_KEY`` set. Without this, a machine with
    a key would degrade the hand-written JSONL fixtures below for an encryption
    reason and the identity-conflict assertions would pass for the wrong cause.
    """
    spec = importlib.util.spec_from_file_location(
        "synapse.memory.store", _BASE / "memory" / "store.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._crypto_instance = None
    return mod


def _mem_dict(mid, content, created="2026-09-15T15:09:00Z"):
    """One COMPLETE on-disk record.

    Every key ``_load`` treats as required (``id`` / ``created_at`` /
    ``content`` / ``memory_type``, all non-empty strings) is present, so the only
    thing that can make a pair of these unreadable is the identity conflict the
    incident was made of — not an incidental schema miss. Field set mirrors
    ``tests/test_store_degraded_load.py::_mem_dict``, which is known to load.
    """
    return {
        "id": mid, "memory_type": "note", "content": content,
        "summary": content[:60], "tags": [], "keywords": [], "source": "user",
        "tier": "shot", "created_at": created, "updated_at": created,
        "hip_file": "", "hip_version": 0, "frame": None, "node_paths": [],
        "links": [], "access_count": 0, "is_consolidated": False, "metadata": {},
    }


def _write_conflicting_jsonl(tmp_path):
    """Lay down the EXACT on-disk shape the incident left behind.

    Two well-formed records, one id, different content — which is what
    ``add()`` produced on 2026-09-15 and what the next ``_load`` refused. Written
    directly rather than through ``add()`` so the degraded-state tests below
    describe a store that is ALREADY broken on disk (the real-world shape an
    operator meets: the damaging process is long gone).
    """
    source = tmp_path / "memory.jsonl"
    source.write_text(
        json.dumps(_mem_dict("mem_incident", "the first write")) + "\n"
        + json.dumps(_mem_dict("mem_incident", "the second, differing write")) + "\n",
        encoding="utf-8",
    )
    return source


#: The five keys the pinned B3 <-> B6 contract requires from ``health()``, in
#: BOTH states. B6 reads this dict to render store health in the panel; a key
#: that is present when healthy and absent when degraded is worse than useless,
#: because the degraded case is the only one anybody looks at.
_HEALTH_KEYS = frozenset(
    {"degraded", "reason", "writable", "records", "rejected_writes"}
)


def _health(store):
    """Read ``store.health()`` through the pinned contract, or fail by name.

    ``health()`` is implemented by Lane B3 and consumed by Lane B6. If it is
    absent this fails LOUDLY with the contract spelled out, rather than skipping
    — a skipped contract test reads as covered, which is the exact species of
    false comfort that let the incident run for two days.
    """
    fn = getattr(store, "health", None)
    if not callable(fn):
        pytest.fail(
            "MemoryStore.health() is missing. It is the pinned B3 -> B6 contract: "
            "health() -> {'degraded': bool, 'reason': str, 'writable': bool, "
            "'records': int, 'rejected_writes': int}, always all five keys, "
            "never raising."
        )
    report = fn()
    assert isinstance(report, dict), f"health() must return a dict, got {type(report)!r}"
    missing = _HEALTH_KEYS - set(report)
    assert not missing, (
        f"health() dropped contract key(s) {sorted(missing)}; B6 reads all five "
        f"unconditionally. Got: {sorted(report)}"
    )
    return report


# ---------------------------------------------------------------------------
# B1/B2 — THE HEADLINE REGRESSION. This is the test whose absence cost two days.
# ---------------------------------------------------------------------------

def test_add_twice_with_differing_payload_does_not_degrade_on_reload(tmp_path, store_mod):
    """Writing one id twice with different content must not poison the NEXT load.

    This is the incident, reproduced through the public write path and nothing
    else. The second ``MemoryStore`` over the same directory is the point: the
    process that wrote the bad line never sees a problem, so any test that stays
    in one store object would have passed straight through the outage.

    WHY THIS FAILS WITHOUT THE FIX — measured against ``git show HEAD:``
    (2 lines on disk; ``_degraded_load`` True; the write after reload raises),
    and here is the chain that produces it:

      * ``add()`` puts ``memory.to_json() + "\\n"`` into ``_write_buffer``
        unconditionally — there is no "does this id already exist on disk"
        branch. Two adds, two buffered lines.
      * ``flush()`` -> ``_flush_writes()`` takes the non-rewrite path
        (``_needs_rewrite`` is only set by ``update``/``delete``, never by
        ``add``) and APPENDS both lines to memory.jsonl.
      * The second store's ``_load`` reads line 1, stores
        ``seen["mem_incident"] = canonical_1``; reads line 2, finds
        ``prior is not None`` and ``prior != canonical`` (the content differs),
        and raises ``conflicting duplicate memory identity`` (store.py:355-362).
      * The per-line handler appends that to ``unreadable``; store.py:396-401
        sees a non-empty list and sets ``_degraded_load = True``.
      * ``_require_writable_load`` then raises RuntimeError on the write below.

    So without the fix this test fails twice over: the ``_degraded_load``
    assertion is False-vs-True, and the ``add()`` raises before the read-back.
    """
    first = store_mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)
    first.add(store_mod.Memory(
        id="mem_incident", content="the first write",
        memory_type=store_mod.MemoryType.NOTE, created_at="2026-09-15T15:09:00Z",
    ))
    first.add(store_mod.Memory(
        id="mem_incident", content="the second, differing write",
        memory_type=store_mod.MemoryType.NOTE, created_at="2026-09-15T15:09:00Z",
    ))
    first.flush()

    # The next process. Everything up to here looked healthy from inside `first`.
    second = store_mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)

    assert second._degraded_load is False, (
        "reloading after two adds of one id degraded the store — this is the "
        f"2026-09-17 outage: {second._degraded_reason}"
    )

    # "Refused EVERY write for two days" is the damage. Prove writes still land.
    second.add(store_mod.Memory(
        id="mem_after_reload", content="the session that must not be lost",
        memory_type=store_mod.MemoryType.NOTE, created_at="2026-09-17T16:00:00Z",
    ))
    assert second.get("mem_after_reload") is not None, (
        "the reloaded store accepted add() but the memory is not readable back"
    )


def test_reload_after_same_id_rewrite_keeps_the_latest_content(tmp_path, store_mod):
    """The surviving record must be the SECOND write, not the first.

    Separate from the headline test on purpose: "did not degrade" and "kept the
    right bytes" are two different failures, and a merged assertion would not say
    which one broke. ``add()`` already overwrites ``_memories[id]`` in RAM, so
    last-write-wins is the semantic the in-memory store has always had; a repair
    that silences the conflict by keeping the FIRST line would make disk and RAM
    disagree — a quieter version of the same bug.
    """
    store = store_mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)
    for content in ("the first write", "the second, differing write"):
        store.add(store_mod.Memory(
            id="mem_incident", content=content,
            memory_type=store_mod.MemoryType.NOTE,
            created_at="2026-09-15T15:09:00Z",
        ))
    store.flush()

    reloaded = store_mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)
    survivor = reloaded.get("mem_incident")
    assert survivor is not None, "the identity vanished entirely across the reload"
    assert survivor.content == "the second, differing write"
    assert reloaded.count() == 1, (
        "one identity must resolve to one memory after reload, not a duplicate pair"
    )


def test_hand_written_conflicting_lines_still_degrade_the_store(tmp_path, store_mod):
    """The C1 guard itself must NOT be weakened by the B1/B2 repair.

    The repair belongs on the write side. If a conflicting pair reaches disk by
    some other route — a hand edit, a crashed half-write, a third-party tool —
    refusing to write is still the correct, data-preserving answer, because a
    partial read must never authorize a rewrite that destroys recoverable bytes.

    This is the control for the headline test: it proves the identity-conflict
    trigger is still live and reachable, so a green headline test means "the
    write path stopped producing conflicts", not "the detector stopped looking".
    """
    _write_conflicting_jsonl(tmp_path)
    store = store_mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)

    assert store._degraded_load is True
    assert "conflicting duplicate memory identity" in store._degraded_reason, (
        "degraded for some other reason than the identity conflict — this test "
        f"is no longer exercising the incident trigger: {store._degraded_reason}"
    )
    with pytest.raises(RuntimeError, match="DEGRADED"):
        store.add(store_mod.Memory(
            id="mem_new", content="should be refused",
            memory_type=store_mod.MemoryType.NOTE,
        ))


# ---------------------------------------------------------------------------
# B3 -> B6 — the health contract. The outage was invisible because nothing asked.
# ---------------------------------------------------------------------------

def test_health_reports_degraded_and_unwritable_when_the_store_is_broken(tmp_path, store_mod):
    """A degraded store must SAY SO, in the five words B6 renders.

    The whole cost of this incident was observability: the store knew it was
    degraded from the first millisecond and told only a log file. ``health()``
    is the surface that turns that into something the panel can show.
    """
    _write_conflicting_jsonl(tmp_path)
    store = store_mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)

    report = _health(store)
    assert report["degraded"] is True
    assert report["writable"] is False, (
        "a degraded store refuses every write; reporting writable=True would "
        "tell the operator the opposite of the truth"
    )
    assert report["reason"], "degraded with an empty reason is an unactionable alarm"
    assert store.is_degraded is True
    assert store.degraded_reason == report["reason"], (
        "is_degraded/degraded_reason and health() must read the same state, not "
        "two drifting copies of it"
    )


def test_health_reports_healthy_and_writable_on_a_clean_store(tmp_path, store_mod):
    """The inverse case — without it, ``health()`` could hardcode 'degraded'.

    A one-sided health check is a dead gate: it would pass this file's degraded
    test while being wrong about every healthy store in production.
    """
    store = store_mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)
    store.add(store_mod.Memory(
        id="mem_ok", content="a perfectly ordinary note",
        memory_type=store_mod.MemoryType.NOTE, created_at="2026-09-17T16:00:00Z",
    ))

    report = _health(store)
    assert report["degraded"] is False
    assert report["writable"] is True
    assert report["reason"] == "", (
        "the contract is: reason is the empty string when healthy — B6 renders "
        f"it verbatim. Got {report['reason']!r}"
    )
    assert report["records"] == 1, (
        "records must count what the store actually holds; a constant would make "
        "the panel's row count fiction"
    )
    assert store.is_degraded is False
    assert store.degraded_reason == ""


def test_health_never_raises_in_either_state(tmp_path, store_mod):
    """``health()`` is called by a status renderer; raising there blanks the panel.

    B6 must be able to call this on any store it is handed, including one that is
    mid-failure, without wrapping it in a try/except that would hide the very
    state it exists to report.
    """
    healthy_dir = tmp_path / "healthy"
    broken_dir = tmp_path / "broken"
    broken_dir.mkdir(parents=True, exist_ok=True)
    _write_conflicting_jsonl(broken_dir)

    healthy = store_mod.MemoryStore(storage_dir=str(healthy_dir), background_load=False)
    broken = store_mod.MemoryStore(storage_dir=str(broken_dir), background_load=False)
    assert broken._degraded_load is True, "the 'degraded' half of this test is not degraded"

    for store, label in ((healthy, "healthy"), (broken, "degraded")):
        for attempt in (1, 2):  # idempotent: reading health must not mutate it
            # pytest's own failure exception derives from BaseException, so a
            # missing-contract fail() from _health propagates; only a genuine
            # implementation error is caught and renamed here.
            try:
                report = _health(store)
            except Exception as exc:  # noqa: BLE001 -- raising IS the defect
                pytest.fail(
                    f"health() raised on the {label} store (attempt {attempt}): "
                    f"{type(exc).__name__}: {exc}"
                )
            assert set(report) >= _HEALTH_KEYS


def test_rejected_writes_increments_when_a_write_is_refused(tmp_path, store_mod):
    """Count the refusals, so "nothing is being saved" is a number, not a vibe.

    During the incident every write raised and the counter that would have said
    "4,000 writes refused" did not exist. This pins the counter to actual refusal
    events: it moves when — and only when — a write is turned away.
    """
    _write_conflicting_jsonl(tmp_path)
    store = store_mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)

    before = _health(store)["rejected_writes"]
    assert isinstance(before, int)

    with pytest.raises(RuntimeError):
        store.add(store_mod.Memory(
            id="mem_refused_1", content="refused once",
            memory_type=store_mod.MemoryType.NOTE,
        ))
    after_one = _health(store)["rejected_writes"]
    assert after_one == before + 1, (
        f"one refused write must move rejected_writes by exactly 1 "
        f"({before} -> {after_one})"
    )

    with pytest.raises(RuntimeError):
        store.add(store_mod.Memory(
            id="mem_refused_2", content="refused twice",
            memory_type=store_mod.MemoryType.NOTE,
        ))
    assert _health(store)["rejected_writes"] == before + 2, (
        "the counter must accumulate; a boolean dressed as a count cannot tell "
        "a one-off from a two-day outage"
    )


# NOT TESTED HERE, deliberately: B6's "tolerate a store without health()" rule.
# A version of it was written and then deleted — it built a bare local class,
# called getattr on it, and asserted the literal "unknown" the test itself had
# just computed. That is a tautology: it re-asserts Python's attribute lookup,
# cannot fail for the reason its name claims, and would read as coverage of a
# consumer this file never calls. The rule belongs to whoever owns the panel
# code path that actually does the getattr.


# ---------------------------------------------------------------------------
# B4 defect 2 — the memory fallback that has been silently dead
# ---------------------------------------------------------------------------

class _SearchSpy:
    """Forwards to the REAL ``SynapseMemory.search`` and remembers the call.

    ``KnowledgeIndex._match_memory`` wraps its search in a bare
    ``except Exception: return None`` (knowledge.py, around :790). A signature
    error there is therefore invisible: the fallback simply reports "no memory"
    and the operator concludes the store is empty. This spy keeps the exception
    so the assertion can name the real cause instead of a bare ``None``.

    It deliberately does NOT normalize the call — forwarding ``*args/**kwargs``
    straight through keeps the real ``SynapseMemory.search`` signature as the
    authority, which is the whole point of the test.
    """

    def __init__(self, real):
        self._real = real
        self.calls = []
        self.error = None

    def search(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        try:
            return self._real.search(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 -- captured, then re-raised
            self.error = exc
            raise


@pytest.fixture()
def seeded_memory(tmp_path):
    """A real ``SynapseMemory`` over a throwaway project dir, holding one memory.

    Real, not a double: the defect being pinned is a SIGNATURE mismatch, and a
    permissive stub that accepted ``**kwargs`` would pass against the broken call
    and prove nothing. ``project_path`` is a tmp dir, so no live store on this
    machine is opened, read, or written.
    """
    from synapse.memory.store import SynapseMemory

    mem = SynapseMemory(project_path=str(tmp_path / "project"))
    mem.note("Jaime prefers the review link posted before lunch")
    return mem


def test_match_memory_returns_a_hit_for_a_stored_memory(seeded_memory):
    """The memory fallback must actually reach the store.

    WHY THIS FAILS WITHOUT THE FIX (measured against ``git show HEAD:``, which
    returned ``None`` with the TypeError below captured by the spy):
    ``_match_memory`` calls ``self._memory.search(text=query, limit=3)``, but
    ``SynapseMemory.search``'s first parameter is named ``query``
    (store.py:1509) — there is no ``text`` keyword. Every call raises
    ``TypeError: SynapseMemory.search() got an unexpected keyword argument
    'text'``, the blanket ``except Exception`` eats it, and the fallback returns
    ``None`` for every query ever asked. The memory tier has been dead,
    silently, for as long as that call has existed.
    """
    from synapse.routing.knowledge import KnowledgeIndex

    spy = _SearchSpy(seeded_memory)
    index = KnowledgeIndex(rag_root=None, memory=spy)

    result = index._match_memory("review link posted before lunch")

    assert spy.calls, "_match_memory never reached the memory store at all"
    assert result is not None, (
        "the memory fallback returned no hit for a memory that is definitely "
        "stored. The swallowed error was: "
        + (f"{type(spy.error).__name__}: {spy.error}" if spy.error
           else "none — the call succeeded but scored below the 0.4 floor")
    )
    assert result.found is True
    assert "review link posted before lunch" in result.answer
    assert result.sources and result.sources[0].startswith("memory:")


def test_lookup_serves_the_memory_tier_end_to_end(seeded_memory):
    """The operator-facing surface, not just the private matcher.

    ``lookup()`` is what the knowledge tool calls. With an empty corpus every
    earlier strategy declines, so this asserts the memory tier is reachable
    THROUGH the public entry point and clears the DENSE_MATCH_FLOOR — a matcher
    that returns a hit too weak to be served is still a dead tier.
    """
    from synapse.routing.knowledge import DENSE_MATCH_FLOOR, KnowledgeIndex

    index = KnowledgeIndex(rag_root=None, memory=seeded_memory)
    result = index.lookup("review link posted before lunch")

    assert result.found is True, (
        "lookup() fell through to not-found with a matching memory in the store"
    )
    assert result.topic == "memory"
    assert result.confidence >= DENSE_MATCH_FLOOR


# ---------------------------------------------------------------------------
# B1 — the automatic consolidation prune must be OFF by default
# ---------------------------------------------------------------------------

class _FakeRow:
    """One ECS row: the two attributes the adapter's prune audit reads."""

    def __init__(self, entity_id, payload):
        self.entity_id = entity_id
        self.payload = payload


class _FakeECS:
    def __init__(self, n, rows):
        self.n = n
        self._rows = rows

    def iter_rows(self):
        return list(self._rows)


class _FakeHandle:
    """A Moneta handle double, sized to ARM the opportunistic-prune trigger.

    ``moneta_store.py`` fires ``run_sleep_pass()`` when
    ``_add_count % 100 == 0 and self._handle.ecs.n > 1000``. Reaching that
    honestly needs 1,001 real deposits with an O(n) snapshot on each — an O(n^2)
    test nobody would keep. So the handle REPORTS a populated engine and the
    counter is pre-positioned; the assertion itself stays purely behavioural:
    did the one destructive memory op run, or not.

    ``durability = None`` makes ``save()`` a no-op, so nothing touches disk.
    """

    durability = None

    def __init__(self, payload):
        self.ecs = _FakeECS(n=1001, rows=[_FakeRow("entity-0", payload)])
        self.deposits = []
        self.sleep_passes = 0

    def deposit(self, payload, embedding, protected_floor=0.0):
        self.deposits.append(payload)

    def run_sleep_pass(self):
        self.sleep_passes += 1
        return type("_Result", (), {"attention_updated": 0, "staged": 0})()


def test_automatic_consolidation_prune_does_not_run_by_default():
    """A routine ``add()`` must never silently trigger the destructive prune.

    ``run_sleep_pass()`` is the one memory op that PERMANENTLY removes
    unprotected memories (moneta_store.py's own words). Today it is reached from
    inside ``add()`` on every hundredth write once the engine passes 1,000
    entities — no consent, no gate, no artist in the loop, and audited only into
    a log line of the same kind nobody read for two days.

    This pins the default-off behaviour, not the mechanism: whether B1 gates it
    behind an opt-in or removes the call outright, a default ``add()`` must not
    prune.

    ANTI-VACUITY CONTROL: the first half calls ``run_sleep_pass()`` directly and
    asserts the fake observes it. Without that, "the prune did not run" would
    also pass if the double were mis-wired and the channel could never fire at
    all — a check that cannot fail, which is worse than no check.

    Measured against ``git show HEAD:python/synapse/memory/moneta_store.py``:
    the control fired (1 direct pass observed) AND the hundredth ``add()`` ran
    the prune unasked (``sleep_passes == 1``), so the final assertion below was
    genuinely red before the repair.
    """
    from synapse.memory.embedding import HashEmbedder
    from synapse.memory.models import Memory, MemoryType
    from synapse.memory.moneta_store import MonetaBackedStore

    resident = Memory(
        id="mem_resident", content="already in the engine",
        memory_type=MemoryType.NOTE, created_at="2026-09-01T00:00:00Z",
    )
    handle = _FakeHandle(resident.to_json())
    store = MonetaBackedStore(handle, HashEmbedder(dim=32))

    # --- control: the observation channel really can fire ---
    store.run_sleep_pass()
    assert handle.sleep_passes == 1, (
        "the fake handle never observed a direct run_sleep_pass() — the negative "
        "assertion below would be meaningless"
    )
    handle.sleep_passes = 0

    # --- the trigger, armed: make the add under test the 100th ---
    store._add_count = 99
    store.add(Memory(
        id="mem_hundredth", content="the hundredth write of the session",
        memory_type=MemoryType.NOTE, created_at="2026-09-17T16:00:00Z",
    ))

    # The trigger's own preconditions really were met — proof the test is live.
    assert store._add_count == 100
    assert handle.ecs.n > 1000
    assert handle.deposits, "add() did not reach the engine; the path never ran"

    assert handle.sleep_passes == 0, (
        "a routine add() ran the destructive consolidation prune. It must be "
        "opt-in: pruning user memory is an artist decision, not a side effect of "
        "the hundredth note of the day."
    )
