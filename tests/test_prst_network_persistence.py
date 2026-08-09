"""PRST relay -- the network-persistence repro, as an executable experiment.

THE REPORTED BEHAVIOUR (Joe, 2026-08-08)
    "Create a Solaris Network" by prompt -> tell SYNAPSE to remember it keyed to
    that prompt -> restart Houdini/SYNAPSE -> ask the same prompt again -> the
    result should be the SAME network. Today it is NOT the same network.

This module localizes that report across three seams. It asserts what SHOULD be
true where a contract exists (A, B) and PINS AN ABSENCE where no mechanism
exists at all (C). Reds here are findings, not failures (Constitution Law 7).

    SEAM A  SAVE durability   -- does the deposit survive a restart?
    SEAM B  RECALL keying     -- does the same prompt retrieve the same record?
    SEAM C  REGENERATE        -- can a recalled record rebuild the network?

WHY THIS IS THE PRODUCTION PATH, NOT A SHORTCUT
    Every deposit and every recall below goes through the real command handlers
    the MCP tools are bound to:

        synapse_decide     -> "decide"     -> SynapseBridge.handle_memory_decide
        synapse_add_memory -> "add_memory" -> SynapseBridge.handle_memory_add
        synapse_recall     -> "recall"     -> SynapseBridge.handle_memory_recall

    (registry: python/synapse/server/handlers.py:790-798; tools:
    python/synapse/mcp/_tool_registry.py:1013/1021/1030)

    No private internal is called to make a test pass. The one layer skipped is
    the websocket transport, which only marshals the same payload dict.

HOW THE STORE IS KEPT OFF THE USER'S REAL DATA
    SynapseMemory takes no injectable storage path and the global accessor
    get_synapse_memory() constructs it with project_path=None
    (python/synapse/memory/store.py:1300-1305). Headless, the address resolver
    falls back to ``Path.cwd() / "untitled.hip"``
    (python/synapse/memory/store.py:988-989), so the child's CWD *is* the
    production address knob. Every child below runs with cwd=<tmp_path>/proj.
    test_store_address_is_redirected_into_tmp is the guard that proves it --
    if the resolver ever changes, that test goes red BEFORE any test writes.

HOUDINI IS NOT RUNNING in this session. Nothing here needs it: every path
exercised is pure Python. No mock ``hou`` is planted (Constitution Article III
bans mock-hou for host-behaviour assertions), so nothing here claims host
coverage. The seam-C engine (apply_fixture) DOES need Houdini to execute; this
module only asserts what its pure-Python validator does, never that a network
was built.

RESTART FIDELITY
    A "restart" here is a genuinely fresh OS process via subprocess +
    sys.executable. Two objects inside one interpreter is not a restart and is
    never presented as one. Both shutdown shapes are tested because they are
    materially different in this store:

        graceful  sys.exit(0)      -> interpreter shutdown -> atexit -> save()
        abrupt    os._exit(0)      -> no atexit, no flush (the crash class)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import moneta_runtime as mr  # noqa: E402

# The operator's literal prompt. Recall matches by case-insensitive substring
# containment (python/synapse/session/tracker.py:568), so this string must
# appear verbatim inside the stored content for anything to be found.
PROMPT = "Create a Solaris Network"

# A network-shaped description: the node types a basic Solaris setup needs.
# It is PROSE -- that is the seam-C finding, not an oversight of this test.
NETWORK_DESC = (
    "domelight + karmarendersettings + usdrender_rop wired under /stage"
)

_SENTINEL = "@@PRST@@"

_PREAMBLE = """
import json, os, sys
sys.path.insert(0, {root!r})

def emit(obj):
    sys.stdout.write({sentinel!r} + json.dumps(obj) + "\\n")
    sys.stdout.flush()

from synapse.session.tracker import get_bridge
from synapse.memory.store import get_synapse_memory
PROMPT = {prompt!r}
NETWORK_DESC = {desc!r}
bridge = get_bridge()
"""


def _child(project_dir, body, backend="moneta", hashseed=None, expect_rc=0):
    """Run ``body`` in a genuinely fresh OS process rooted at ``project_dir``.

    Returns the list of objects the child emitted via ``emit()``. Child stdout
    is parsed by sentinel prefix because the store logs freely to stderr and
    (on a moneta fallback) to stdout-adjacent handlers.
    """
    src = _PREAMBLE.format(
        root=str(_ROOT / "python"), sentinel=_SENTINEL,
        prompt=PROMPT, desc=NETWORK_DESC,
    ) + body
    env = dict(os.environ)
    env["SYNAPSE_MEMORY_BACKEND"] = backend
    if hashseed is None:
        env.pop("PYTHONHASHSEED", None)
    else:
        env["PYTHONHASHSEED"] = str(hashseed)
    proc = subprocess.run(
        [sys.executable, "-c", src], cwd=str(project_dir),
        capture_output=True, text=True, timeout=300, env=env,
    )
    assert proc.returncode == expect_rc, (
        "child exited %r (expected %r)\nSTDOUT:\n%s\nSTDERR:\n%s"
        % (proc.returncode, expect_rc, proc.stdout, proc.stderr[-4000:])
    )
    return [
        json.loads(line[len(_SENTINEL):])
        for line in proc.stdout.splitlines()
        if line.startswith(_SENTINEL)
    ]


@pytest.fixture
def project(tmp_path):
    """A throwaway project directory. The store lands at <it>/untitled.hip/.synapse."""
    p = tmp_path / "proj"
    p.mkdir()
    return p


# --- child bodies ----------------------------------------------------------

_DEPOSIT = """
r = bridge.handle_memory_decide({"decision": PROMPT, "reasoning": NETWORK_DESC,
                                 "tags": ["solaris"]})
stored = bridge.handle_memory_recall({"query": PROMPT})
emit({"deposit": r, "stored": stored["matches"][0] if stored["matches"] else None})
"""

_RECALL = """
sm = get_synapse_memory()
rr = bridge.handle_memory_recall({"query": PROMPT})
emit({"store": type(sm.store).__name__, "storage_dir": str(sm.storage_dir),
      "found": rr["found"], "count": rr["count"], "matches": rr["matches"]})
"""

_EXIT_GRACEFUL = "\nsys.exit(0)\n"
_EXIT_ABRUPT = "\nsys.stdout.flush()\nos._exit(0)\n"


# ---------------------------------------------------------------------------
# GUARD -- must hold before any other test is trusted
# ---------------------------------------------------------------------------

def test_store_address_is_redirected_into_tmp(project):
    """The safety interlock: prove the child's store is inside tmp, not the
    user's real store.

    FAILS IF the headless address resolver stops honouring CWD -- at which
    point every other test in this file would be writing to the operator's
    actual memory. This test exists so that failure is loud and first.
    """
    out = _child(project, _RECALL)[0]
    storage = Path(out["storage_dir"]).resolve()
    assert storage.is_relative_to(project.resolve()), (
        "store escaped the tmp project dir: %s" % storage)
    assert not storage.is_relative_to(Path.home().resolve() / ".synapse")


# ---------------------------------------------------------------------------
# SEAM A -- save durability across a real restart
# ---------------------------------------------------------------------------

def test_first_deposit_survives_graceful_restart(project):
    """Deposit -> graceful exit -> fresh process -> recall the SAME record.

    Steps 1-4 of the repro, easiest shutdown shape. Compares CONTENT and ID,
    not merely "a record came back".

    FAILS IF the record is absent, or its id or content differ from what was
    stored.
    """
    dep = _child(project, _DEPOSIT + _EXIT_GRACEFUL)[0]
    stored = dep["stored"]
    assert stored is not None, "deposit was not even visible in its own process"

    rec = _child(project, _RECALL)[0]
    assert rec["found"] is True, (
        "graceful restart lost the deposit: %r" % (rec,))
    assert rec["count"] == 1
    assert rec["matches"][0]["id"] == stored["id"]
    assert rec["matches"][0]["content"] == stored["content"]
    assert PROMPT.lower() in rec["matches"][0]["content"].lower()


def test_first_deposit_survives_abrupt_restart(project):
    """Deposit -> os._exit(0) (no atexit, the crash class) -> recall.

    FAILS IF the deposit is lost when the process dies without running
    interpreter shutdown.

    NOTE for the reader: this passes today only because the FIRST deposit of a
    process is force-saved -- ``_last_save`` is initialised to 0.0 while
    ``time.monotonic()`` at process start is the system uptime
    (python/synapse/memory/moneta_store.py:205-206, gate at :379). That is
    R-CI0-1's shipped option A. See the next two tests for what happens to
    deposit #2. Durability POSTURE is a pending human ruling and is untouched
    here.
    """
    dep = _child(project, _DEPOSIT + _EXIT_ABRUPT)[0]
    stored = dep["stored"]
    assert stored is not None

    rec = _child(project, _RECALL)[0]
    assert rec["found"] is True, (
        "abrupt restart lost the deposit: %r" % (rec,))
    assert rec["matches"][0]["id"] == stored["id"]
    assert rec["matches"][0]["content"] == stored["content"]


_DEPOSIT_NOT_FIRST = """
# Deposit #1 of the session: an ordinary session note. Any real session has one
# of these (a session_start note, an earlier decision, a scene-memory
# dual-write) before the operator says "remember this".
bridge.handle_memory_add({"content": "session started", "type": "note"})
""" + _DEPOSIT


def test_second_deposit_of_a_session_survives_graceful_restart(project):
    """CONTROL for the test below: same deposit ordinal, graceful shutdown.

    FAILS IF a non-first deposit is lost even on a clean exit. Its job is to
    isolate the variable: if this is green and the abrupt twin is red, the
    difference is the SHUTDOWN SHAPE and not the deposit ordinal.
    """
    dep = _child(project, _DEPOSIT_NOT_FIRST + _EXIT_GRACEFUL)[0]
    stored = dep["stored"]
    assert stored is not None

    rec = _child(project, _RECALL)[0]
    assert rec["found"] is True, (
        "graceful restart lost the second deposit: %r" % (rec,))
    assert rec["matches"][0]["id"] == stored["id"]
    assert rec["matches"][0]["content"] == stored["content"]


@pytest.mark.xfail(
    reason="W1 pending: abrupt-restart persistence is blueprint W1's acceptance "
    "gate (PRST receipts, red on master since <= 2026-08-08); un-xfail lands "
    "with fix/memory-store-recovery", strict=True)
def test_second_deposit_of_a_session_survives_abrupt_restart(project):
    """THE REPRO. A deposit that is not the first of its session, then a crash.

    This is the operator's actual sequence: a session does some work, THEN he
    says "remember this network", THEN Houdini goes away. If the exit is not
    clean, the deposit is acknowledged to the caller and never reaches disk --
    ``add()`` returns ``memory.id`` after only the in-memory ECS write whenever
    ``now - _last_save < 30.0`` (python/synapse/memory/moneta_store.py:379,
    :399).

    FAILS IF the record the operator asked to remember is missing after the
    restart, or comes back with a different id/content.

    ADDRESSED TO R-CI0-1 (pending human ruling, Article I). This leg changed no
    durability posture and proposes none. It reports the reachability.
    """
    dep = _child(project, _DEPOSIT_NOT_FIRST + _EXIT_ABRUPT)[0]
    stored = dep["stored"]
    assert stored is not None, "deposit was not visible in its own process"

    rec = _child(project, _RECALL)[0]
    assert rec["found"] is True, (
        "SEAM A REPRO: the deposit the operator asked to remember did not "
        "survive an abrupt restart. stored=%r recall=%r" % (stored, rec))
    assert rec["matches"][0]["id"] == stored["id"]
    assert rec["matches"][0]["content"] == stored["content"]


_DEPOSIT_THEN_SEARCH = _DEPOSIT.rstrip() + """
# A text SEARCH -- the production vector-recall path, reached by synapse_search
# and by any semantic lookup. This is what an operator does when he "asks the
# same prompt again".
get_synapse_memory().search(PROMPT)
"""


@pytest.mark.xfail(
    reason="W1 pending: abrupt-restart persistence is blueprint W1's acceptance "
    "gate (PRST receipts, red on master since <= 2026-08-08); un-xfail lands "
    "with fix/memory-store-recovery", strict=True)
def test_store_still_opens_after_a_search_then_abrupt_restart(project):
    """Deposit -> text search -> crash -> reopen.

    A text search boosts the top-5 hits via ``signal_attention`` with SYNAPSE's
    own string ids (python/synapse/memory/moneta_store.py:494-495), which
    Moneta appends verbatim to its write-ahead log. On the next cold start the
    WAL replay parses that field as a UUID with no guard. If it raises,
    ``_make_store`` swallows the exception and silently serves an EMPTY jsonl
    store (python/synapse/memory/store.py:911, :967) -- so the operator is
    never told his backend changed under him.

    Two assertions, deliberately separate:
      1. the requested backend is still serving  (the SILENCE)
      2. the record is still recallable          (the LOSS)

    FAILS IF the store cannot be reopened after a crash that followed a search,
    or if the backend silently downgrades.
    """
    dep = _child(project, _DEPOSIT_THEN_SEARCH + _EXIT_ABRUPT)[0]
    stored = dep["stored"]
    assert stored is not None

    rec = _child(project, _RECALL)[0]
    assert rec["store"] == "MonetaBackedStore", (
        "backend silently downgraded to %s after a search-then-crash; the "
        "requested backend is no longer serving and nothing told the operator"
        % rec["store"])
    assert rec["found"] is True, (
        "record unrecallable after a search-then-crash: %r" % (rec,))
    assert rec["matches"][0]["id"] == stored["id"]


# ---------------------------------------------------------------------------
# SEAM B -- recall keying and determinism
# ---------------------------------------------------------------------------

_DEPOSIT_MANY = """
ids = []
for i in range(12):
    r = bridge.handle_memory_decide({
        "decision": PROMPT,
        "reasoning": NETWORK_DESC + " variant %d" % i,
        "tags": ["solaris"]})
    ids.append(r["id"])
# Deliberate explicit save so this test isolates ORDERING, not durability.
# Without it only deposit #1 would be force-saved and the corpus would be
# trivially size-1 -- the determinism question would not even be asked.
get_synapse_memory().save()
emit({"ids": ids})
""" + _EXIT_GRACEFUL


@pytest.mark.parametrize("backend", ["moneta", "jsonl"])
def test_recall_is_deterministic_across_fresh_processes(project, backend):
    """Ask the identical prompt from N separate fresh processes; demand the
    identical answer.

    12 decisions all contain the prompt verbatim, so all 12 match, and recall
    truncates to ``matches[:5]`` with NO sort of any kind
    (python/synapse/session/tracker.py:576-581). Which five you get is decided
    by backend iteration order. PYTHONHASHSEED is varied across the children on
    purpose: under the jsonl backend ``get_by_type`` iterates a ``set`` of id
    strings (python/synapse/memory/store.py:706-711, set built at :407-412),
    and CPython salts str hashing per process.

    FAILS IF any two of the six fresh processes return a different id sequence
    for the same prompt against a byte-identical store.
    """
    deposited = _child(project, _DEPOSIT_MANY, backend=backend)[0]["ids"]
    assert len(set(deposited)) == 12, "deposits collided on id"

    answers = []
    for seed in range(6):
        out = _child(project, _RECALL, backend=backend, hashseed=seed)[0]
        assert out["found"] is True, "corpus vanished before determinism ran"
        answers.append([m["id"] for m in out["matches"]])

    first = answers[0]
    assert all(a == first for a in answers), (
        "SEAM B: the same prompt returned different records across fresh "
        "processes (backend=%s). per-process answers=%r" % (backend, answers))


# INTERLEAVED on purpose, and the interleaving is load-bearing. Moneta's ECS
# removal is swap-and-pop: it moves the LAST row into the freed slot. If all 12
# decisions were deposited first they would occupy rows 0-11, every pruned note
# would be back-filled by another note, and the decision order would never move
# -- the test would pass unfixed and prove nothing (verified: it did exactly
# that before this comment existed). Alternating note/decision, ending on a
# DECISION, is both the realistic session shape and the arrangement that lets a
# note prune actually permute the decisions.
_DEPOSIT_MIXED = """
dids = []
nids = []
for i in range(12):
    r = bridge.handle_memory_add({
        "content": "unrelated housekeeping note %d" % i,
        "type": "note"})
    nids.append(r["id"])
    r = bridge.handle_memory_decide({
        "decision": PROMPT,
        "reasoning": NETWORK_DESC + " variant %d" % i,
        "tags": ["solaris"]})
    dids.append(r["id"])
get_synapse_memory().save()
emit({"decisions": dids, "notes": nids})
""" + _EXIT_GRACEFUL

# The real production prune -- synapse_sleep_pass -> "sleep_pass" ->
# store.run_sleep_pass(). Unprotected notes only become prunable once utility
# decays below PRUNE_UTILITY_THRESHOLD, which at the library-default 6h
# half-life takes ~19.9h. Rather than wait, we move ONLY the clock that
# run_sleep_pass reads for `now` (moneta/api.py: `now = time.time()`); every
# other time function delegates to the real module, and the decay mechanism,
# the classifier and the ECS removal are entirely untouched.
_PRUNE = """
import time as _t
import moneta.api as _mapi


class _AgedClock:
    _OFFSET = 10 * 365 * 24 * 3600

    def __getattr__(self, name):
        return getattr(_t, name)

    def time(self):
        return _t.time() + self._OFFSET


_mapi.time = _AgedClock()

sm = get_synapse_memory()
audit = sm.store.run_sleep_pass()
sm.save()
emit({"pruned": audit.pruned,
      "pruned_types": sorted(set(audit.pruned_types.values())),
      "surviving_ids": [m.id for m in sm.store.all()]})
""" + _EXIT_GRACEFUL


def test_recall_survives_an_unrelated_prune(project):
    """PRST/FIX-B1 regression pin: pruning UNRELATED memories must not change
    which records the same prompt returns.

    This is the production failure mode the parametrized determinism test above
    cannot see: on moneta that test passes even unfixed, because within one
    unchanging store the row order is stable. It is *removal* that permutes it
    -- moneta's ECS is swap-and-pop, so deleting any row moves the LAST row into
    the freed slot (moneta/ecs.py:110-134), and ``get_by_type`` is raw row order
    (python/synapse/memory/moneta_store.py:445, :403-423).

    Reachability, so this is not a synthetic worry: ``synapse_sleep_pass`` is a
    registered MCP tool (python/synapse/mcp/_tool_registry.py:1079), and the
    pass ALSO fires by itself every 100th add once the store exceeds 1000
    entities (moneta_store.py:383-398).

    FAILS IF recall's answer to an unchanged prompt moves when memories it never
    matched are pruned -- i.e. if the ordering fix at
    python/synapse/session/tracker.py:558-570 is removed. Verified red with that
    fix reverted.
    """
    dep = _child(project, _DEPOSIT_MIXED)[0]
    decisions, notes = dep["decisions"], dep["notes"]
    assert len(set(decisions)) == 12, "decision deposits collided on id"
    assert len(set(notes)) == 12, "note deposits collided on id"

    before = _child(project, _RECALL)[0]
    assert before["found"] is True, "corpus vanished before the prune ran"

    pr = _child(project, _PRUNE)[0]
    assert pr["pruned"] > 0, (
        "the sleep pass pruned nothing, so this test proves nothing about "
        "removal-induced reordering; audit=%r" % (pr,))
    assert pr["pruned_types"] == ["note"], (
        "the prune removed something other than the unrelated notes, so any "
        "recall change would be legitimate data loss rather than reordering; "
        "pruned types=%r" % (pr["pruned_types"],))

    survivors = set(pr["surviving_ids"])
    missing = [d for d in decisions if d not in survivors]
    assert not missing, (
        "protected decisions were pruned (%d of 12) -- this test can no longer "
        "isolate ordering from loss: %r" % (len(missing), missing))

    after = _child(project, _RECALL)[0]
    assert [m["id"] for m in after["matches"]] == [
        m["id"] for m in before["matches"]], (
        "SEAM B: pruning %d UNRELATED notes changed which records the same "
        "prompt returns, while every matching decision survived.\n"
        "  before=%r\n  after =%r"
        % (pr["pruned"], [m["id"] for m in before["matches"]],
           [m["id"] for m in after["matches"]]))


def test_a_remembered_note_is_invisible_to_recall(project):
    """The keying mismatch between the two documented 'remember' surfaces.

    ``synapse_add_memory`` defaults to MemoryType.NOTE
    (python/synapse/session/tracker.py:432-447) while recall reads DECISION
    exclusively (:558). So the most natural reading of "tell SYNAPSE to
    remember it" deposits something recall can never return.

    This PINS PRESENT BEHAVIOUR -- it is a finding, not an endorsement. FAILS
    the day add_memory and recall compose, which is a change that should be
    noticed deliberately rather than discovered.
    """
    _child(project, """
r = bridge.handle_memory_add({"content": PROMPT + " -- " + NETWORK_DESC,
                              "type": "note"})
get_synapse_memory().save()
emit({"id": r["id"]})
""" + _EXIT_GRACEFUL)

    rec = _child(project, _RECALL)[0]
    assert rec["found"] is False, (
        "add_memory now composes with recall -- update this pin deliberately; "
        "recall=%r" % (rec,))


# ---------------------------------------------------------------------------
# SEAM C -- regeneration. Pinning an ABSENCE honestly.
# ---------------------------------------------------------------------------

def test_recall_returns_prose_not_a_network(project):
    """What recall hands back is TEXT. It cannot rebuild anything.

    A recall match is exactly {id, summary, content, date}
    (python/synapse/session/tracker.py:569-574). There is no node list, no
    wiring, no parameters -- so even with seams A and B perfect, whatever
    builds the network next is a fresh model generation, and sameness is
    impossible by construction.

    FAILS IF a match ever carries structure, which is precisely the change
    that would make prompt->network replay possible. Then this pin should be
    rewritten to assert the structure round-trips.
    """
    dep = _child(project, _DEPOSIT + _EXIT_GRACEFUL)[0]
    assert dep["stored"] is not None

    rec = _child(project, _RECALL)[0]
    assert rec["found"] is True
    match = rec["matches"][0]
    assert set(match) == {"id", "summary", "content", "date"}, (
        "recall payload shape changed: %r" % sorted(match))
    for key in ("nodes", "wires", "parms", "fixture", "graph", "network"):
        assert key not in match
    assert isinstance(match["content"], str)
    # The stored 'network' is a sentence, not a graph.
    assert "domelight" in match["content"]
    assert not match["content"].lstrip().startswith(("{", "["))


# Names M6 would plausibly introduce. This tripwire is NOT exhaustive -- M6
# could land under a name not listed here, in which case this test stays green
# while being wrong. Stated so the limitation travels with the assertion.
_M6_RESOLVER_NAMES = (
    "phrase_table", "phrase_map", "prompt_to_fixture", "fixture_for_prompt",
    "resolve_prompt", "fixture_alias", "alias_table",
)


def test_no_prompt_to_fixture_resolution_exists():
    """The deterministic engine exists, is oracle-pinned, and is UNREACHABLE
    from a plain-English prompt.

    ``apply_fixture`` is keyed by a filesystem identifier. Its validator
    rejects anything with a space or a capital before any work happens
    (python/synapse/cognitive/tools/apply_fixture.py:48, :143-156), so the
    operator's prompt cannot address it. Nothing maps one to the other: that
    mapping is M6, which is HELD. No phrase table is built here.

    FAILS IF the prompt becomes a valid fixture name, or a prompt->fixture
    resolver appears under one of the names below -- i.e. the day M6 lands,
    this test asks to be rewritten to assert the mapping instead of its
    absence.
    """
    import importlib

    from synapse.blocks import fixtures as fx

    # NOT `from synapse.cognitive.tools import apply_fixture` -- the package
    # re-exports a FUNCTION of that name, which shadows the submodule and
    # yields a function object with no BlocksToolError attribute. Resolve the
    # module by dotted path instead.
    af = importlib.import_module("synapse.cognitive.tools.apply_fixture")

    # 1. the prompt cannot address the engine
    with pytest.raises(af.BlocksToolError):
        af._validate(PROMPT, "/stage")

    # 2. negative control -- the validator is not simply rejecting everything
    assert af._validate("solaris.basic", "/stage") is None

    # 3. a Solaris fixture DOES exist; the gap is the address, not the engine
    available = fx.list_fixtures()
    assert "solaris.basic" in available

    # 4. no fixture is prompt-shaped
    assert not any(" " in name for name in available)
    assert PROMPT not in available and PROMPT.lower() not in available

    # 5. no prompt->fixture resolver is wired anywhere on the blocks surface
    from synapse.blocks import runtime as rt
    for module in (fx, af, rt):
        for name in _M6_RESOLVER_NAMES:
            assert not hasattr(module, name), (
                "%s.%s exists -- M6 may have landed; rewrite this pin to "
                "assert the mapping, not its absence" % (module.__name__, name))
