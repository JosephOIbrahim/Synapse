"""test_memory_seam_defects.py — pins the memory-seam review's reproduced defects.

Source: ``Claude outputs/memory-seam-review-2026-09-16.md`` (1,800 lines). Every
"fails today" verdict in that document was a *prediction* — the review ran no
tests. A probe pass then executed seven of them and refuted two. This file
converts the survivors from prose into executable claims.

Two families, deliberately different:

``Group A`` — strict-xfail tripwires. Deterministic, fail at HEAD, and XPASS the
moment someone fixes the defect, which turns the suite red and forces the fix to
delete the marker. That is the point: a defect that can be fixed silently is a
defect that will regress. Per ``AGENTS.md`` §4 ("a test not seen fail is a
decoration"), each of these was run and observed failing before commit.

``Group B`` — permanent green guards. These pin facts that are currently *true*
and that two independent agents disagreed about. They are the reason this file
exists even after every Group A defect is fixed.

Scope note: several probe verdicts self-qualify, and the tests say what the probe
said. P2 is a *latent, ungated API hazard*, not a live production failure — zero
of 33 call sites pass a ``str``. P7's id instability is a deliberate, test-pinned
FU-1 decision (``tests/test_memory_models.py``). Neither test below claims a live
production bug; both assert the hazard is reachable and ungated.

No network, no Houdini, no writes outside ``tmp_path``.
"""

from __future__ import annotations

import inspect
import os
import re
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(package_root, "python") not in sys.path:
    sys.path.insert(0, os.path.join(package_root, "python"))

from synapse.loop import mapper, ports  # noqa: E402
from synapse.loop.ports import MONETA_URI_SCHEME, MemoryPort  # noqa: E402

URI_A = MONETA_URI_SCHEME + "/tmp/synapse_seam_defects_a"
URI_B = MONETA_URI_SCHEME + "/tmp/synapse_seam_defects_b"


@pytest.fixture(autouse=True)
def clean_registry():
    """Every test starts and ends with an empty handle registry."""
    MemoryPort.release()
    yield
    MemoryPort.release()


class _LayerStore:
    """A Moneta-shaped stand-in whose ``_handle.ecs`` is the memory layer.

    Never touches disk, never imports Moneta. Mirrors the fixture in
    ``tests/test_memory_recall_honesty.py``.
    """

    def __init__(self, ecs):
        self._handle = SimpleNamespace(ecs=ecs)


def _bind(store, uri=URI_A):
    MemoryPort._handles[uri] = store
    return MemoryPort(uri)


# ---------------------------------------------------------------------------
# Group A — strict-xfail tripwires. Each fails at HEAD.
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "P1/AC-2: the recall receipt cannot distinguish 'contamination rule ran "
        "and found nothing' from 'contamination rule never ran'. Fix = echo the "
        "token set (or a checked flag) in the payload; then delete this marker."
    ),
)
def test_p1_recall_receipt_can_distinguish_checked_from_unchecked():
    """PROBE P1 — FAILS_TODAY.

    The single production caller (``python/synapse/host/memory_loop.py:75``)
    passes an empty token list, and ``query_and_filter`` emits
    ``dropped.contaminated: 0`` with no key separating *checked, found none* from
    *never checked*. A live probe showed the identical payload key set for ``[]``
    and for a non-empty token list.

    Law A: a degradation nobody can measure is indistinguishable from a bug.
    This asserts the measurement is *possible* — it names three acceptable
    spellings and requires at least one.
    """
    store = _LayerStore(ecs=object())
    port = _bind(store)
    port._fetch_raw_memories = lambda keys: []

    empty = port.query_and_filter([], [])
    full = port.query_and_filter(["alpha"], [])

    # Precondition, not the claim: the payload assertion below must be read off a
    # real envelope, not an error result. "SUCCESS" is the literal PortResult
    # emits (ports.py:34) and the one _require_status enforces (ports.py:49-55).
    assert empty.status == "SUCCESS", (
        "query_and_filter([], []) must return a success envelope, or the payload "
        f"claim below is read off an error result; got status={empty.status!r} "
        f"error={empty.error_message!r}"
    )

    echo_keys = {"task_context_tokens", "contamination_checked", "tokens_checked"}
    assert isinstance(empty.payload, dict)
    assert echo_keys & set(empty.payload), (
        "query_and_filter's payload must carry a key that proves the contamination "
        f"rule was given a token set. Present keys: {sorted(empty.payload)}"
    )
    # And the two calls must be distinguishable from the payload alone.
    assert set(empty.payload) != set(full.payload) or (
        empty.payload.get("task_context_tokens") != full.payload.get("task_context_tokens")
    ), "an empty token list and a populated one produce indistinguishable receipts"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "P2/AC-3: a bare str at ports.py:494 is exploded into a character set and "
        "drives the contamination drop rule. Fix = refuse a non-list token "
        "argument (the file's own posture at :549 and :671-679); then delete this."
    ),
)
def test_p2_bare_string_is_not_silently_exploded_into_a_token_set():
    """PROBE P2 — FAILS_TODAY, latent.

    ``query_and_filter(["k"], "hello")`` returns SUCCESS with the token set
    ``{'h','e','l','l','o'}``. ``int`` raises TypeError; ``str`` silently
    succeeds — the one wrong type that does not announce itself.

    ``docs/THE_LOOP_v5.1.md:126`` declares ``task_context_tokens: List[str]``.
    Zero of the 33 call sites in the repo pass a ``str``, so this is an ungated
    hazard rather than a live failure — which is exactly why it needs a gate.
    """
    store = _LayerStore(ecs=object())
    port = _bind(store)
    port._fetch_raw_memories = lambda keys: []

    result = port.query_and_filter(["k"], "hello")

    # A port refusal is "BLOCKED" (ports.PortResult.blocked), never mapper.BLOCK —
    # mapper's ALLOW/BLOCK are GATE_POLICY() verdicts over predicates (mapper.py:13-14)
    # and can never equal a PortResult.status. The review named the wrong symbol.
    assert result.status == "BLOCKED", (
        "a bare str must be refused, not exploded into a character set; got "
        f"status={result.status!r}"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "P2b: the same element-wise guard is reachable through wake_scene_relations "
        "at ports.py:446 — the review wrongly prescribed :446 as the shape to copy. "
        "It is an instance of the hazard, not a remedy for it."
    ),
)
def test_p2_bare_string_is_not_silently_exploded_in_wake_scene_relations():
    """PROBE P2, second reachable site — FAILS_TODAY.

    The review prescribed ``ports.py:446`` as the guard shape to copy. It is not:
    ``[k for k in (usd_relation_keys or []) if isinstance(k, str)]`` is the same
    element-wise iteration, producing a list instead of a set. A bare ``str``
    survives it intact as characters.

    This test exists because the correction matters more than the defect: a fix
    copied from ``:446`` would look like a fix and change nothing.
    """
    store = _LayerStore(ecs=object())
    port = _bind(store)
    seen = []

    def spy(keys):
        seen.append(list(keys))
        return []

    port._fetch_raw_memories = spy
    port.wake_scene_relations("hello")

    assert seen, "wake_scene_relations must reach the relation lookup"
    assert seen[0] == ["hello"], (
        "a bare str relation key must arrive whole; it arrived as "
        f"{seen[0]!r} — i.e. as a character set"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "P7/AC-12,13: _write_settlement calls plain append-style add() with no id "
        "and no only_if_missing, so a retried settlement deposits a second row. "
        "Fix = inject the stable id the way coordinator.py:169 does; then delete."
    ),
)
def test_p7_repeated_settlement_deposit_carries_a_stable_id():
    """PROBE P7 — FAILS_TODAY, qualified.

    Both halves are literally true at HEAD: two constructions a second apart get
    different ``mem_`` ids, and ``_write_settlement`` (``ports.py:619-636``) calls
    ``self._store.add(memory)`` at ``:635`` with no id and no ``only_if_missing``
    — while ``:263`` (``add_durable_if_absent``) is the id-guarded path it does
    not use.

    Two qualifications, both load-bearing:

    * The id instability is a *deliberate, test-pinned FU-1 decision*
      (``tests/test_memory_models.py:22-44``, commit ``3c4f07f9``). It is not an
      oversight.
    * ``moneta_store.py:666`` keys its idempotence boundary on ``memory.id``, so
      supplying a stable id is what makes the existing boundary able to dedupe —
      the remedy is "use the id you already have", not "build a new mechanism".

    This asserts the *hazard*: two deposits of the same claim produce two
    distinct ids, so nothing downstream can recognise the retry. It does not
    claim a live production bug — the one site that would hit it has no
    production callers.

    The store is bound by its real type, ``MonetaBackedStore``, not by a bare
    handle: the deposit runs the production path end to end, so the failure
    below is the id claim and nothing upstream of it.

    The 1.1s sleep is the defect's own mechanism, not padding: the id folds
    ``created_at`` at second granularity, so two deposits inside one second
    collide into the *same* id and the test would pass spuriously.
    """
    moneta_runtime = pytest.importorskip("synapse.memory.moneta_runtime")
    if not moneta_runtime.moneta_available():
        pytest.skip("Moneta is not importable here — the deposit path is unreachable")

    from synapse.memory.embedding import HashEmbedder
    from synapse.memory.moneta_store import MonetaBackedStore

    class _Spy:
        """Proxies the real store, recording what the port deposits."""

        def __init__(self, wrapped):
            self._wrapped = wrapped
            self.seen = []

        def __getattr__(self, name):
            return getattr(self._wrapped, name)

        def add(self, memory):
            self.seen.append(memory)
            return self._wrapped.add(memory)

    # Bind the type the port is contracted against, not a bare handle.
    # ``_write_settlement`` calls ``self._store.add(memory)`` (ports.py:635) and
    # ``add`` is defined by ``MonetaBackedStore`` (moneta_store.py:687) — the store
    # ``from_owner`` enforces with isinstance (ports.py:246-248), and the one
    # ``_write_settlement``'s own docstring calls "the ONE authority". Binding an
    # unwrapped ``make_ephemeral()`` handle dies at :266 on AttributeError one rung
    # before the id claim, which is the defect this file exists to remove.
    # HashEmbedder is the deterministic, no-network embedder and the same fallback
    # ``from_storage_dir`` reaches for (moneta_store.py:260); the handle's
    # ``embedding_dim`` is matched to it so ``deposit`` cannot reject the vector.
    embedder = HashEmbedder()
    store = MonetaBackedStore(
        moneta_runtime.make_ephemeral(embedding_dim=embedder.dim), embedder
    )
    spy = _Spy(store)
    port = _bind(spy, uri=URI_B)

    outcome = sorted(ports.SETTLEMENT_OUTCOMES)[0]
    first = port.deposit_settlement("claim-seam-p7", outcome)
    time.sleep(1.1)
    second = port.deposit_settlement("claim-seam-p7", outcome)

    assert first.status == "SUCCESS" and second.status == "SUCCESS", (
        "the deposit itself must succeed for the identity claim to be meaningful; "
        f"got {first.status!r} ({first.error_message!r}) / "
        f"{second.status!r} ({second.error_message!r})"
    )
    assert len(spy.seen) == 2, f"expected two deposits, saw {len(spy.seen)}"
    assert spy.seen[0].id == spy.seen[1].id, (
        "a retry of the same claim must carry the same id, so Moneta's "
        "idempotence boundary (moneta_store.py:666, keyed on memory.id) can "
        f"dedupe it. Got {spy.seen[0].id!r} then {spy.seen[1].id!r}."
    )


# ---------------------------------------------------------------------------
# Group B — permanent green guards
# ---------------------------------------------------------------------------


def test_gate_policy_truth_table_including_the_documented_empty_vacuity():
    """The real truth table, plus the one edge already routed to V0.1.

    ``mapper.GATE_POLICY`` is a pure spec and — per its own docstring — "never a
    live gate." Its edge case is not a discovery: ``loop-v00.yaml:27`` already
    carries it forward by name.

        "Known edge (spec-only, unreachable in V0.0): GATE_POLICY([]) returns
         ALLOW by vacuous truth — carried to the V0.1 live-gate leg to resolve,
         not a V0.0 blocker."

    This test pins the *behaviour* (so a silent change to the vacuity fails
    loud), the *unevaluable-blocks* rule, and the *wrong-type-raises* rule. It
    deliberately does not assert the vacuity is correct — it asserts it is the
    documented, tracked shape. If V0.1 resolves it, this test changes with it.
    """
    assert mapper.GATE_POLICY([True, True]) == mapper.ALLOW
    assert mapper.GATE_POLICY([True, False]) == mapper.BLOCK
    # A None predicate is unevaluable, and unevaluable blocks.
    assert mapper.GATE_POLICY([True, None]) == mapper.BLOCK
    assert mapper.GATE_POLICY([None, None]) == mapper.BLOCK
    # False short-circuits ahead of a later None.
    assert mapper.GATE_POLICY([False, None]) == mapper.BLOCK
    # The documented spec-only edge, carried to V0.1 by loop-v00.yaml:27.
    assert mapper.GATE_POLICY([]) == mapper.ALLOW
    # A non-bool predicate is a programming error, not a silent block.
    with pytest.raises(TypeError):
        mapper.GATE_POLICY([1])


def test_fetch_raw_memories_is_an_exact_set_intersection_with_no_distance_path():
    """Pins the resolution of the review's highest-severity contradiction.

    S4-F1 ("the recall receipt names a filter axis that never ran") rested on two
    agents disagreeing: one said it never read ``_fetch_raw_memories``; the other
    said it read it end to end and the escape hatch was closed. If a distance
    comparison lived in that method, the finding would evaporate.

    Resolution: it does not. ``_fetch_raw_memories`` (``ports.py:583``) is an
    exact set-intersection predicate over Moneta ECS rows — no embeddings, no
    vectors, no similarity, no distance. The contrast is exact and is the whole
    finding:

    * ``utility_floor`` maps to a comparison that *ran* (``ports.py:509``).
    * ``distance_threshold`` maps to nothing.

    This is asserted against the function's own source rather than a line number,
    so it survives reformatting and fails only if the property actually changes.
    """
    source = inspect.getsource(ports.MemoryPort._fetch_raw_memories)
    forbidden = (
        "embedding",
        "vector",
        "similarity",
        "cosine",
        "distance",
        "distance_threshold",
        "nearest",
    )
    hits = [token for token in forbidden if re.search(token, source, re.IGNORECASE)]
    assert not hits, (
        "S4-F1 STANDS only while _fetch_raw_memories performs no vector or "
        f"distance matching. Found {hits} in its source — if this is a real "
        "addition, the review's top finding must be re-opened."
    )


def test_distance_threshold_is_emitted_but_never_compared():
    """The receipt advertises an axis the code never evaluates.

    ``query_and_filter`` emits ``distance_threshold`` into its payload, but no
    comparison against it exists anywhere in ``python/synapse/loop/``. This is
    the mechanism behind S4-F1, pinned separately from the finding itself so a
    future "just add the comparison" change is a deliberate act with a failing
    test in front of it.

    Two arms: the value is emitted (so the receipt does not change silently), and
    the identifier is never used in a comparison on either side.
    """
    source = inspect.getsource(ports.MemoryPort.query_and_filter)
    assert "distance_threshold" in source, (
        "query_and_filter must still emit distance_threshold into its payload — "
        "removing it is a receipt-shape change, not a cleanup"
    )

    comparison = re.compile(
        r"distance_threshold\s*(?:<|>|<=|>=|==|!=)"
        r"|(?:<|>|<=|>=|==|!=)\s*[A-Za-z_][\w.]*\s*(?:<|>)?\s*distance_threshold"
        r"|distance_threshold\s*\)\s*[<>]"
    )
    assert not comparison.search(source), (
        "distance_threshold is emitted but never compared; if a comparison has "
        "appeared, the payload key is now load-bearing and the review's S4-F1 "
        "disposition must be revisited rather than left standing"
    )


@pytest.mark.xfail(
    strict=False,
    reason=(
        "P6: agent_state.py holds no lock across 15 bare Usd.Stage.Open→Save() "
        "sites, so concurrent writers clobber each other. Non-strict because the "
        "race is thread-based and therefore probabilistic — a strict xfail would "
        "risk a spurious XPASS turning CI red. See the PR body for the measured "
        "rate (6 of 8 concurrent writers raised ErrorException; 2 of 8 decisions "
        "survived)."
    ),
)
def test_p6_concurrent_decision_writes_do_not_lose_rows(tmp_path):
    """PROBE P6 — FAILS_TODAY, probabilistic.

    ``agent_state.py`` holds no lock across 15 ``Usd.Stage.Open`` → ``Save()``
    sites; a grep for any lock primitive exits 1 ('lock' matches only
    ``IntegrityBlock``). The sibling ``scene_memory.py:85`` has ``_get_file_lock``
    and uses it at four sites.

    A deterministic single-threaded framing was attempted and **empirically
    refuted** during the probe pass: USD caches ``SdfLayer`` by identifier within
    a process, so two ``Usd.Stage.Open`` calls on one path share a layer and
    nothing is clobbered. The failure is genuinely thread-based, which is why this
    test is threaded and why its marker is non-strict.

    Skips loudly where ``pxr`` is absent: without real USD the module falls back
    to its USDA stub and there is no race to run. That skip is a loss of
    coverage, stated rather than hidden.
    """
    from synapse.memory import agent_state

    if not getattr(agent_state, "PXR_AVAILABLE", False):
        pytest.skip(
            "pxr unavailable — agent_state falls back to a stub and the "
            "concurrent-Save race does not exist. Run under hython for coverage."
        )

    stage_path = str(tmp_path / "agent.usd")
    writers = 8
    start = threading.Barrier(writers)
    errors: list[BaseException] = []

    def write(index: int) -> None:
        start.wait()
        try:
            agent_state.log_decision(
                stage_path,
                {"decision": f"decision_{index}", "reasoning": "concurrency probe"},
            )
        except BaseException as exc:  # noqa: BLE001 - the probe records the class
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(i,)) for i in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, (
        f"{len(errors)} of {writers} concurrent writers raised — the first was "
        f"{type(errors[0]).__name__}: {errors[0]}"
    )

    stage = agent_state._open_stage(stage_path) if hasattr(
        agent_state, "_open_stage"
    ) else None
    assert stage is not None, "agent_state exposes no stage opener to verify with"

    decisions = [
        child
        for child in stage.GetPrimAtPath("/SYNAPSE/memory/decisions").GetChildren()
    ]
    assert len(decisions) == writers, (
        f"{writers} concurrent writers, {len(decisions)} rows survived — "
        "concurrent writers clobbered one another"
    )
