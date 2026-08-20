# probes.py - LOOP probe library (pure-python for V0.0).
#
# The only module that resolves loop probe kinds against the live seam
# (python/synapse/loop/). Cloned in spirit from harness/autoresearch/probes.py,
# with V0.0 being deliberately PURE-PYTHON: no hou import, no hython, no Houdini.
#
# Evidence discipline (recycled from the autoresearch family):
#     - Probes ask the live runtime (the imported seam), never answer from memory.
#     - An absent port/substrate is an answer (status: UNAVAILABLE), not an exception.
#     - Probe-internal exceptions become evidence entries via the runner, never crashes.
#     - UNKNOWN posture: an unmeasurable value is the string "UNKNOWN", never a guess.
#     - A missing seam (import error) is a measured fact: the probe returns
#       {"error": <traceback>}, recorded as evidence. Never fabricated SUCCESS.
#
# hou is imported guarded so a later needs_hou rung (V0.1+, SALUS path evaluation)
# can reuse this module under hython without breaking plain-python validation.
from __future__ import annotations

import itertools
import os
import sys
from pathlib import Path

try:  # guarded: V0.0 never needs it, a needs_hou rung will
    import hou  # noqa: F401
    HOU_AVAILABLE = True
except ImportError:
    hou = None
    HOU_AVAILABLE = False

# Repo root = harness/loop/ -> harness -> <repo>.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Loop probe kinds resolve against python/synapse/loop/. The seam is imported
# lazily INSIDE each probe so a missing seam is an evidence entry, not a crash.
sys.path.insert(0, str(_REPO_ROOT / "python"))


# ---------------------------------------------------------------- runner surface

def get_build() -> str:
    """The probed build. V0.0 is pure-python: the evidence is true to the python
    seam, so the build token is 'pure-python' unless we happen to be under hython."""
    if HOU_AVAILABLE and hou is not None:
        try:
            return hou.applicationVersionString()
        except Exception:
            pass
    return "pure-python"


def seam_version() -> str:
    """The seam's own version stamp (python/synapse/loop/__init__.py __version__).
    UNKNOWN if the seam is not importable yet - honest, never a guess."""
    try:
        from synapse.loop import __version__
        return __version__
    except Exception:
        return "UNKNOWN"


def require_hou() -> None:
    """Raise if hou is unavailable. Only called when the mission sets needs_hou."""
    if not HOU_AVAILABLE:
        raise RuntimeError(
            "mission requires hou (needs_hou: true) but no Houdini runtime is "
            "reachable; run under hython, or set needs_hou: false for a pure-python rung")


# ---------------------------------------------------------------- probe helpers

def _ledger_path():
    """Ask the seam for its ledger path - one oracle, not two."""
    from synapse.loop.ports import LedgerPort
    return LedgerPort.ledger_path()


def _snapshot_files(root: Path) -> list:
    """Deterministic snapshot of a tree: sorted relative paths + sizes."""
    if not root.exists():
        return []
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            try:
                out.append(f"{p.relative_to(root)}:{p.stat().st_size}")
            except OSError:
                out.append(f"{p.relative_to(root)}:UNKNOWN")
    return out


def _ledger_lines(ledger: Path) -> list:
    if not ledger.exists():
        return []
    return [ln for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ---------------------------------------------------------------- probe kinds

def probe_port_contract(port: str, methods: list) -> dict:
    """Verify ports.py matches blueprint §4: PortResult NamedTuple with
    status/payload/error_message and status ∈ {SUCCESS, UNAVAILABLE, BLOCKED},
    and each named port class exposing the §4 method signature."""
    import inspect

    from synapse.loop import ports as _ports

    if port == "PortResult":
        pr = getattr(_ports, "PortResult", None)
        if pr is None:
            return {"port": "PortResult", "exists": False,
                    "reason": "no PortResult in synapse.loop.ports"}
        fields = list(getattr(pr, "_fields", [])) if hasattr(pr, "_fields") else []
        statuses = _ports.STATUS if hasattr(_ports, "STATUS") else None
        return {
            "port": "PortResult",
            "exists": True,
            "is_namedtuple": hasattr(pr, "_fields"),
            "fields": fields,
            "has_status": "status" in fields,
            "has_payload": "payload" in fields,
            "has_error_message": "error_message" in fields,
            "valid_statuses": sorted(statuses) if statuses else None,
            "contract_holds": (
                hasattr(pr, "_fields")
                and "status" in fields
                and "payload" in fields
                and "error_message" in fields
                and statuses is not None
                and {"SUCCESS", "UNAVAILABLE", "BLOCKED"} <= set(statuses)
            ),
        }

    cls = getattr(_ports, port, None)
    if cls is None:
        return {"port": port, "exists": False,
                "reason": f"no class named {port} in synapse.loop.ports"}

    per_method = {}
    for m in methods:
        fn = getattr(cls, m, None)
        if fn is None:
            per_method[m] = {"present": False}
            continue
        try:
            sig = inspect.signature(fn)
            params = [p for p in sig.parameters if p not in ("self", "cls")]
            ret = sig.return_annotation
            per_method[m] = {
                "present": True,
                "params": params,
                "return_annotation": None if ret is inspect.Parameter.empty else str(ret),
            }
        except (TypeError, ValueError):
            per_method[m] = {"present": True, "signature": "uninspectable"}

    return {
        "port": port,
        "exists": True,
        "methods": per_method,
        "all_methods_present": all(v["present"] for v in per_method.values()),
        "contract_holds": all(v["present"] for v in per_method.values()),
    }


def probe_mapper_green(name: str) -> dict:
    """Exercise the deterministic mapper truth table. Contract: GATE_POLICY returns
    ALLOW only when every predicate is True; any False or None (unevaluable) is
    BLOCK. The expected column is the contract interpretation, hardcoded here -
    NOT read back from the seam - so a drifting mapper fails loudly."""
    from synapse.loop.mapper import ALLOW, BLOCK, GATE_POLICY

    rows = []
    all_hold = True
    for combo in itertools.product([True, False, None], repeat=3):
        expected = ALLOW if all(v is True for v in combo) else BLOCK
        try:
            got = GATE_POLICY(list(combo))
        except Exception as e:  # a mapper that throws is a failing row, not a crash
            got = f"RAISED: {type(e).__name__}"
        ok = got == expected
        all_hold = all_hold and ok
        rows.append({"predicates": list(combo), "expected": expected,
                     "got": got, "pass": ok})

    unevaluable_blocks = all(
        r["got"] == BLOCK for r in rows if None in r["predicates"])
    return {
        "name": name,
        "total": len(rows),
        "passed": sum(1 for r in rows if r["pass"]),
        "truth_table_holds": all_hold,
        "unevaluable_blocks": unevaluable_blocks,
        "rows": rows,
    }


def probe_precommit_order(turns: int) -> dict:
    """Build `turns` recipe turns and verify the V0.0 invariant: every turn's
    precommit is authored in the ledger (real, durable) BEFORE the mutating act,
    and every turn lands EXPOSED (settlement honest-UNAVAILABLE until Hanish)."""
    from synapse.loop.recipe import build_recipe, run_recipe
    from synapse.loop.ports import LedgerPort

    ledger = _ledger_path()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    n_before = len(_ledger_lines(ledger))

    recipe = build_recipe("precommit-order", turns=turns)
    results = run_recipe(recipe, ledger_dir=ledger.parent)

    n_after = len(_ledger_lines(ledger))
    new_precommits = n_after - n_before

    turn_checks = []
    invariant_holds = True
    for t in results:
        kinds = [s.kind for s in t.steps]
        first_is_precommit = bool(kinds) and kinds[0] == "precommit"
        one_precommit = kinds.count("precommit") == 1
        precommit_before_mutation = (
            one_precommit and "mutation" in kinds
            and kinds.index("precommit") < kinds.index("mutation"))
        exposed = t.verdict == "EXPOSED"
        ok = first_is_precommit and one_precommit and precommit_before_mutation and exposed
        invariant_holds = invariant_holds and ok
        turn_checks.append({
            "turn": t.id,
            "verdict": t.verdict,
            "step_kinds": kinds,
            "first_step_is_precommit": first_is_precommit,
            "precommit_before_mutation": precommit_before_mutation,
            "exposed": exposed,
            "pass": ok,
        })

    return {
        "turns": turns,
        "ledger": str(ledger),
        "lines_before": n_before,
        "lines_after": n_after,
        "new_precommits": new_precommits,
        "precommit_per_turn": new_precommits == turns,
        "all_turns_exposed": all(t["verdict"] == "EXPOSED" for t in turn_checks),
        "invariant_holds": invariant_holds and new_precommits == turns,
        "turns": turn_checks,
    }


def probe_stageport_cow(stage_identifier: str) -> dict:
    """StagePort must report UNAVAILABLE (Octavius absent) with ZERO side effects -
    no writes under harness/loop/, no ledger growth, nothing. This is the V0.0
    gate's 'closes without Octavius stage present'."""
    from synapse.loop.ports import StagePort

    scope = _REPO_ROOT / "harness" / "loop"
    before = _snapshot_files(scope)
    before_ledger = _ledger_lines(_ledger_path())

    result = StagePort().compose_sanitized_stage(stage_identifier)

    after = _snapshot_files(scope)
    after_ledger = _ledger_lines(_ledger_path())

    zero_disk_writes = after == before
    return {
        "stage_identifier": stage_identifier,
        "status": result.status,
        "unavailable": result.status == "UNAVAILABLE",
        "error_message": result.error_message,
        "payload": result.payload,
        "ledger_unchanged": before_ledger == after_ledger,
        "zero_disk_writes": zero_disk_writes,
        "closes_without_octavius": (
            result.status == "UNAVAILABLE"
            and zero_disk_writes
            and before_ledger == after_ledger
        ),
    }


def probe_closure_rate(turns: int) -> dict:
    """Run `turns` recipe turns; V0.0 requires closure_rate = 1.0 with zero
    HIT/MISS. closure_rate = terminal-honest-verdicts / total. EXPOSED is terminal;
    settlement is honest-UNAVAILABLE until Hanish lands, so every turn is EXPOSED."""
    from synapse.loop.recipe import build_recipe, run_recipe

    recipe = build_recipe("closure-rate", turns=turns)
    results = run_recipe(recipe)

    verdicts = [t.verdict for t in results]
    counts = {v: verdicts.count(v) for v in ("HIT", "MISS", "EXPOSED", "UNRESOLVABLE")}
    terminal = sum(counts.values())
    closure_rate = (terminal / turns) if turns else None

    return {
        "turns": turns,
        "verdicts": verdicts,
        "counts": counts,
        "terminal_total": terminal,
        "closure_rate": closure_rate,
        "closure_rate_1_0": closure_rate == 1.0,
        "zero_hit_miss": counts["HIT"] == 0 and counts["MISS"] == 0,
        "all_exposed": counts["EXPOSED"] == turns,
        "goalpost_holds": (
            closure_rate == 1.0
            and counts["HIT"] == 0
            and counts["MISS"] == 0
            and counts["EXPOSED"] == turns
        ),
    }
