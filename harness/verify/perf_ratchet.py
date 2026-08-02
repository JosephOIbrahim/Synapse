#!/usr/bin/env python3
"""perf_ratchet — the ONE comparator for the perf ratchet (I2 design, R304).

Imported by BOTH tests/test_perf_ratchet.py and (a future)
harness/verify/checks.py::check_perf_ratchet so the two callers cannot drift.

THE DISCIPLINE (same as the suite ratchet, checks.py::check_suite_baseline):
the floor is read at merge-base(master, HEAD) — never the worktree — so a
branch cannot lower its own bar. Inside a harness sprint the agent has
already made its atomic commit, so HEAD is the agent's tip and reading the
worktree (or HEAD) would let a sprint commit a lowered floor and green its
own regression.

ANCHOR POLICY (three tiers, the anchor used is ALWAYS reported — no silent
fallback path exists):
  1. merge-base resolves            → use it (normal case; CI fetch-depth: 0).
  2. `master` ref absent entirely   → fall back to HEAD-COMMITTED (never the
     worktree) and SAY SO — weaker: blocks only an uncommitted lowering.
  3. merge-base fails with master present → HARD FAIL (RatchetAnchorError):
     a guard that cannot resolve its own baseline is not guarding.

DIRECTION RULE: counts may FALL freely (an improvement never fails); they may
only RISE via a human-promoted floor (per-cell _why) or an unexpired waiver.
Counter-set evolution is asymmetric on purpose: a counter present in the run
but absent from the floor is NEW (reported, never fails — promote before it
gates); a counter present in the floor but absent from the run FAILS
("instrument deleted").

STATED FAILURE CONDITIONS for parse_perf_baseline (Law 1 — this parser can
fail, and here is exactly how; model: checks.py::parse_tuple_baseline):
  1. raw is not valid JSON, or the root is not a JSON object      -> raise
  2. "schema" != "perf_baseline/counts-v1"                        -> raise
  3. the "pinned_constants" block is absent or empty              -> raise
     (every count cell pins its OWN env, so reverting a SHIPPED default —
      e.g. _DEFAULT_STAGE_HASH_PRIM_THRESHOLD back to 1 << 62 — would leave
      every count green while restoring the pre-98b556f production regime;
      this block is the ONLY closure of that hole. I2 §5 rule 5: not optional.)
  4. "scenarios" is absent or empty                               -> raise
  5. a measured cell is missing any of producer / harness / env_pins /
     scale_term / _why, or its intercept carries no counters      -> raise
     (Law 2: no number without a producer path beside it)
  6. an UNPINNED stub cell is missing its "_what"                 -> raise
     (the gap must be visible in the artifact, not absent from it)
  7. a waiver is missing reason / expires / granted_by            -> raise
  8. the floor is neither PROPOSED (proposed=true) nor PROMOTED
     (promoted_by set)                                            -> raise

PROMOTION SHAPE (validate_promotion, runs BEFORE any number comparison):
a cell whose floor numbers ROSE relative to the anchor floor must carry a
_why that differs from the anchor cell's _why, or a valid waiver — otherwise
the SHAPE check raises. Rubber-stamping is still possible (I2 risk #4 —
same weakness the suite baseline carries); this raises its cost, no more.

Wall-clock is out of scope by ruling: a timer cannot gate this repo (CI has
no pxr) and belongs to Tier B (ratio, advisory) / Tier C (live) only.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent          # harness/verify
REPO = HERE.parent.parent
FLOOR_RELPATH = "harness/verify/perf_baseline.json"
REGISTRY_RELPATH = "harness/latency/REGISTRY.json"
SCHEMA = "perf_baseline/counts-v1"

_SLOPE_EPS = 1e-9


class PerfBaselineShapeError(ValueError):
    """The floor file violates the stated shape. Never recoverable in-run."""


class RatchetAnchorError(RuntimeError):
    """merge-base failed while master exists — the guard cannot resolve its
    own baseline, which is a FAIL, not a fallback."""


# ── floor parsing ────────────────────────────────────────────────────────────

_CELL_REQUIRED = ("producer", "harness", "env_pins", "scale_term", "_why")
_WAIVER_REQUIRED = ("reason", "expires", "granted_by")


def parse_perf_baseline(raw):
    """Parse + shape-check the floor. Accepts a JSON string or an already
    loaded dict; returns the validated dict. Raises PerfBaselineShapeError
    per the module docstring's stated failure conditions."""
    if isinstance(raw, (str, bytes)):
        try:
            doc = json.loads(raw)
        except Exception as e:
            raise PerfBaselineShapeError(
                f"floor is not valid JSON: {type(e).__name__}: {str(e)[:160]}")
    else:
        doc = raw
    if not isinstance(doc, dict):
        raise PerfBaselineShapeError(
            f"floor root is {type(doc).__name__}, expected a JSON object")
    if doc.get("schema") != SCHEMA:
        raise PerfBaselineShapeError(
            f"floor schema is {doc.get('schema')!r}, expected {SCHEMA!r}")
    pinned = doc.get("pinned_constants")
    if not isinstance(pinned, dict) or not any(
            not k.startswith("_") for k in pinned):
        raise PerfBaselineShapeError(
            "pinned_constants block absent/empty — every count cell pins its "
            "own env, so a shipped-default revert (e.g. threshold back to "
            "1 << 62) would leave all counts green; the block is the only "
            "closure of that hole (I2 §5 rule 5)")
    scenarios = doc.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        raise PerfBaselineShapeError("scenarios block absent or empty")
    if not doc.get("proposed") and not (doc.get("promoted_by") or "").strip():
        raise PerfBaselineShapeError(
            "floor is neither PROPOSED (proposed=true) nor PROMOTED "
            "(promoted_by set) — a floor with no provenance is not a floor")
    for name, cell in scenarios.items():
        if not isinstance(cell, dict):
            raise PerfBaselineShapeError(
                f"cell {name!r} is {type(cell).__name__}, expected an object")
        if cell.get("status") == "UNPINNED":
            if not str(cell.get("_what", "")).strip():
                raise PerfBaselineShapeError(
                    f"UNPINNED stub {name!r} carries no _what — the gap must "
                    f"be visible in the artifact, not absent from it")
            continue
        missing = [k for k in _CELL_REQUIRED if not cell.get(k)]
        if missing:
            raise PerfBaselineShapeError(
                f"cell {name!r} missing {', '.join(missing)} — Law 2: no "
                f"number without a producer path beside it")
        icounters = (cell.get("intercept") or {}).get("counters")
        if not isinstance(icounters, dict) or not icounters:
            raise PerfBaselineShapeError(
                f"cell {name!r} intercept carries no counters")
        for cname, v in icounters.items():
            if not isinstance(v, int):
                raise PerfBaselineShapeError(
                    f"cell {name!r} intercept counter {cname!r} is not an "
                    f"integer: {v!r}")
        w = cell.get("waiver")
        if w is not None:
            missing_w = [k for k in _WAIVER_REQUIRED if not w.get(k)]
            if missing_w:
                raise PerfBaselineShapeError(
                    f"cell {name!r} waiver missing {', '.join(missing_w)}")
    return doc


def _waiver_state(cell, today: _dt.date) -> str:
    """'none' | 'valid' | 'expired' (expiry is enforced by the gate, not by
    memory — the mechanic that stops 'temporary' from becoming permanent)."""
    w = cell.get("waiver")
    if not w:
        return "none"
    try:
        expires = _dt.date.fromisoformat(str(w.get("expires")))
    except ValueError:
        return "expired"  # unparseable expiry never extends a waiver
    return "valid" if today <= expires else "expired"


# ── the anchor: merge-base read ──────────────────────────────────────────────

def _git(repo: Path, *args) -> tuple[int, str]:
    p = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").strip()


def read_floor(repo: Path = REPO, rel: str = FLOOR_RELPATH):
    """Read the floor at the ratchet anchor. Returns (raw_or_None,
    anchor_used, note). anchor_used is ALWAYS meaningful — printed by every
    caller in every pass and every failure; there is no silent fallback."""
    # Tier 1 candidates, in order. origin/master is NOT optional politeness:
    # the standard GitHub PR checkout (actions/checkout) fetches the PR ref and
    # leaves NO local master, so a local-only lookup silently degraded to
    # HEAD-committed and a branch's own doctored floor became its bar — a
    # demonstrated hole (R304 crucible, severity 3/5). A ratchet whose anchor
    # weakens exactly in CI is not a ratchet.
    baseline_ref = None
    for cand in ("master", "origin/master", "refs/remotes/origin/master"):
        rc_c, _ = _git(repo, "rev-parse", "--verify", "--quiet", cand)
        if rc_c == 0:
            baseline_ref = cand
            break
    if baseline_ref is None:
        # Tier 2: no baseline ref anywhere (tag checkout, fork with no remote) —
        # HEAD-committed, never the worktree. Weaker guarantee, said out loud.
        rc, raw = _git(repo, "show", f"HEAD:{rel}")
        note = ("anchor=HEAD-committed (no master/origin-master ref — weaker: "
                "blocks only an uncommitted lowering)")
        return (raw if rc == 0 and raw.strip() else None, "HEAD-committed", note)
    rc_mb, anchor = _git(repo, "merge-base", baseline_ref, "HEAD")
    if rc_mb != 0 or not anchor:
        # Tier 3: a baseline ref exists but merge-base failed.
        raise RatchetAnchorError(
            f"git merge-base {baseline_ref} HEAD failed with {baseline_ref} "
            f"present — a guard that cannot resolve its own baseline is not "
            f"guarding")
    rc, raw = _git(repo, "show", f"{anchor}:{rel}")
    if rc != 0 or not raw.strip():
        return None, anchor, (f"floor absent at anchor {anchor[:12]} "
                             f"(via {baseline_ref})")
    return raw, anchor, f"anchor=merge-base({baseline_ref}) {anchor[:12]}"


# ── pinned shipped-default constants ────────────────────────────────────────

def _read_large_mode_default(bridge_mod):
    """The shipped default of _stage_hash_large_mode() — read with the env
    var absent so an operator shell cannot fake it."""
    key = "SYNAPSE_STAGE_HASH_LARGE_MODE"
    saved = os.environ.pop(key, None)
    try:
        return bridge_mod._stage_hash_large_mode()
    finally:
        if saved is not None:
            os.environ[key] = saved


_LIVE_CONSTANT_READERS = {
    "shared/bridge.py:_DEFAULT_STAGE_HASH_PRIM_THRESHOLD":
        lambda m: m._DEFAULT_STAGE_HASH_PRIM_THRESHOLD,
    "shared/bridge.py:_STAGE_HASH_UNBOUNDED":
        lambda m: m._STAGE_HASH_UNBOUNDED,
    "shared/bridge.py:_stage_hash_large_mode()_default":
        _read_large_mode_default,
    "shared/bridge.py:_DEFAULT_STAGE_HASH_VOLUME_THRESHOLD":
        lambda m: m._DEFAULT_STAGE_HASH_VOLUME_THRESHOLD,
    "shared/bridge.py:_STAGE_HASH_VOLUME_ATTR_BUDGET":
        lambda m: m._STAGE_HASH_VOLUME_ATTR_BUDGET,
    "shared/bridge.py:_SCENE_HASH_BUCKETS_MS[-1]":
        lambda m: m._SCENE_HASH_BUCKETS_MS[-1],
}


def check_pinned_constants(pinned: dict, bridge_mod=None) -> list[str]:
    """EQUALITY check on shipped defaults — ANY drift (up or down) is a
    promotion event, because the count cells pin their own env and cannot see
    it. Returns a list of failure strings (empty = ok)."""
    if bridge_mod is None:
        _ensure_repo_on_path()
        import shared.bridge as bridge_mod  # noqa: PLC0415
    fails = []
    for key, want in pinned.items():
        if key.startswith("_"):
            continue
        reader = _LIVE_CONSTANT_READERS.get(key)
        if reader is None:
            fails.append(f"pinned constant {key!r} has no live reader — "
                         f"unverifiable pin is a shape defect")
            continue
        try:
            live = reader(bridge_mod)
        except Exception as e:
            fails.append(f"pinned constant {key!r} unreadable: "
                         f"{type(e).__name__}: {e}")
            continue
        if live != want:
            fails.append(
                f"pinned constant DRIFTED: {key} live={live!r} floor={want!r} "
                f"— a shipped-default change is a promotion event (the count "
                f"cells pin their own env and cannot see this)")
    return fails


# ── promotion shape ──────────────────────────────────────────────────────────

def _cell_numbers(cell) -> dict[str, float]:
    out = {}
    for cname, v in ((cell.get("intercept") or {}).get("counters") or {}).items():
        out[f"intercept.{cname}"] = v
    for cname, v in ((cell.get("slope") or {}).get("per_unit") or {}).items():
        out[f"slope.{cname}"] = v
    if "passes_per_op" in cell:
        out["passes_per_op"] = cell["passes_per_op"]
    return out


def validate_promotion(old_doc: dict, new_doc: dict,
                       today: _dt.date | None = None) -> None:
    """Raise PerfBaselineShapeError if any cell's numbers ROSE without a
    changed _why or a valid waiver. Runs BEFORE number comparison."""
    today = today or _dt.date.today()
    old_cells = old_doc.get("scenarios") or {}
    for name, new_cell in (new_doc.get("scenarios") or {}).items():
        old_cell = old_cells.get(name)
        if old_cell is None or new_cell.get("status") == "UNPINNED" \
                or old_cell.get("status") == "UNPINNED":
            continue
        old_nums, new_nums = _cell_numbers(old_cell), _cell_numbers(new_cell)
        rose = [k for k, v in new_nums.items()
                if k in old_nums and v > old_nums[k] + _SLOPE_EPS]
        if not rose:
            continue
        why_changed = (str(new_cell.get("_why", "")).strip()
                       and new_cell.get("_why") != old_cell.get("_why"))
        if why_changed or _waiver_state(new_cell, today) == "valid":
            continue
        raise PerfBaselineShapeError(
            f"cell {name!r} numbers ROSE ({', '.join(rose[:4])}) with no new "
            f"_why and no valid waiver — a raised floor must say why "
            f"(direction rule: counts fall freely, rise only via promotion)")


# ── comparison ───────────────────────────────────────────────────────────────

@dataclass
class Verdict:
    ok: bool
    rows: list = field(default_factory=list)
    detail: str = ""

    def to_rows(self):
        return list(self.rows)


def _row(rid, label, status, detail, producer):
    return {"id": rid, "label": label, "status": status,
            "detail": detail, "producer": producer}


def compare(measured: dict, floor_doc: dict, *, today: _dt.date | None = None,
            producer: str = "tests/perf_counters.py::measure") -> Verdict:
    """Compare measured counter dicts against a parsed floor.

    measured: {scenario_name: {counter: int}} — from perf_counters.measure_all()
    floor_doc: parse_perf_baseline() output.
    """
    today = today or _dt.date.today()
    rows: list = []
    scenarios = floor_doc["scenarios"]

    for name in sorted(scenarios):
        cell = scenarios[name]
        rid = f"PR:{name}"
        if cell.get("status") == "UNPINNED":
            rows.append(_row(rid, name, "PENDING",
                             f"UNPINNED stub — {cell.get('_what', '')[:180]}",
                             producer))
            continue
        got = measured.get(name)
        if got is None:
            rows.append(_row(rid, name, "FAIL",
                             "scenario not measured — instrument deleted",
                             producer))
            continue
        waiver = _waiver_state(cell, today)
        fails, notes = [], []
        icounters = cell["intercept"]["counters"]
        for cname, floor_v in icounters.items():
            if cname not in got:
                fails.append(f"{cname}: counter absent from run — "
                             f"instrument deleted")
                continue
            live = got[cname]
            if live > floor_v:
                msg = f"{cname} {live} > floor {floor_v}"
                if waiver == "valid":
                    notes.append(f"WAIVED {msg} (until "
                                 f"{cell['waiver']['expires']})")
                elif waiver == "expired":
                    fails.append(f"expired waiver: {msg} (waiver expired "
                                 f"{cell['waiver']['expires']})")
                else:
                    fails.append(msg)
            elif live < floor_v:
                notes.append(f"{cname} improved {floor_v} -> {live}")
        new_counters = sorted(set(got) - set(icounters))
        if new_counters:
            notes.append(f"NEW (not gating until promoted): "
                         f"{', '.join(new_counters)}")

        slope = cell.get("slope")
        if slope:
            pair = slope.get("pair")
            m2 = measured.get(pair)
            at = slope.get("measured_at") or []
            if m2 is None or len(at) != 2 or at[1] <= at[0]:
                fails.append(f"slope pair {pair!r} not measured / bad "
                             f"measured_at {at!r} — instrument deleted")
            else:
                denom = at[1] - at[0]
                for cname, floor_slope in (slope.get("per_unit") or {}).items():
                    if cname not in got or cname not in m2:
                        fails.append(f"slope counter {cname!r} absent — "
                                     f"instrument deleted")
                        continue
                    live_slope = (m2[cname] - got[cname]) / denom
                    if live_slope > floor_slope + _SLOPE_EPS:
                        msg = (f"slope({cname}) {live_slope:.4f}/unit > floor "
                               f"{floor_slope}/unit over {at}")
                        if waiver == "valid":
                            notes.append(f"WAIVED {msg}")
                        else:
                            fails.append(msg)
                if "passes_per_op" in cell and "prim_visits" in got \
                        and "prim_visits" in m2:
                    live_ppo = round((m2["prim_visits"] - got["prim_visits"])
                                     / denom)
                    if live_ppo > cell["passes_per_op"]:
                        msg = (f"passes_per_op {live_ppo} > floor "
                               f"{cell['passes_per_op']} — a full-stage "
                               f"traversal was added")
                        if waiver == "valid":
                            notes.append(f"WAIVED {msg}")
                        else:
                            fails.append(msg)

        if fails:
            rows.append(_row(rid, name, "FAIL",
                             "; ".join(fails)[:460], producer))
        else:
            rows.append(_row(rid, name, "PASS",
                             ("; ".join(notes) or "at/below floor")[:460],
                             producer))

    pin_fails = check_pinned_constants(floor_doc["pinned_constants"])
    rows.append(_row("PR:pinned_constants", "shipped-default constants",
                     "FAIL" if pin_fails else "PASS",
                     "; ".join(pin_fails)[:460] if pin_fails
                     else "all pinned shipped defaults match the floor",
                     "shared/bridge.py module constants vs floor "
                     "pinned_constants"))

    n_fail = sum(1 for r in rows if r["status"] == "FAIL")
    ok = n_fail == 0
    detail = (f"{sum(1 for r in rows if r['status'] == 'PASS')} PASS / "
              f"{n_fail} FAIL / "
              f"{sum(1 for r in rows if r['status'] == 'PENDING')} PENDING")
    return Verdict(ok=ok, rows=rows, detail=detail)


# ── wiring: measure via tests/perf_counters, gate via the anchor ────────────

def _ensure_repo_on_path():
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))


def _load_perf_counters(repo: Path = REPO):
    mod = sys.modules.get("perf_counters")
    if mod is not None:
        return mod
    path = repo / "tests" / "perf_counters.py"
    spec = importlib.util.spec_from_file_location("perf_counters", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["perf_counters"] = mod
    spec.loader.exec_module(mod)
    return mod


def _registry_armed(repo: Path) -> bool:
    try:
        reg = json.loads((repo / REGISTRY_RELPATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool((reg.get("ratchet") or {}).get("armed"))


def run_gate(repo: Path = REPO, today: _dt.date | None = None) -> Verdict:
    """The full anchored gate: read floor at merge-base, validate promotion
    shape if the worktree floor differs, measure live, compare against the
    ANCHOR floor. Not-armed + no floor at anchor => PENDING (honest, loud),
    never PASS."""
    armed = _registry_armed(repo)
    try:
        raw, anchor, note = read_floor(repo)
    except RatchetAnchorError as e:
        return Verdict(False, [_row("PR:anchor", "ratchet anchor", "FAIL",
                                    str(e), "git merge-base master HEAD")],
                       "anchor FAIL")
    producer = (f"tests/perf_counters.py::measure vs {FLOOR_RELPATH}@{anchor}")

    if raw is None:
        wt_floor = repo / FLOOR_RELPATH
        status = "FAIL" if armed else "PENDING"
        detail = (f"{note}; armed={armed}"
                  + ("; worktree floor exists (PROPOSED — advisory only, "
                     "not the ratchet anchor)" if wt_floor.is_file() else ""))
        return Verdict(not armed,
                       [_row("PR:floor", "perf floor at anchor", status,
                             detail, producer)],
                       f"floor missing at anchor ({'FAIL' if armed else 'PENDING'})")

    try:
        floor_doc = parse_perf_baseline(raw)
        wt_path = repo / FLOOR_RELPATH
        if wt_path.is_file():
            wt_raw = wt_path.read_text(encoding="utf-8")
            if wt_raw.strip() != raw.strip():
                validate_promotion(floor_doc, parse_perf_baseline(wt_raw),
                                   today=today)
    except PerfBaselineShapeError as e:
        return Verdict(False, [_row("PR:shape", "floor shape", "FAIL",
                                    f"{e} [{note}]", producer)],
                       "shape FAIL")

    pc = _load_perf_counters(repo)
    measured = pc.measure_all()
    verdict = compare(measured, floor_doc, today=today, producer=producer)
    verdict.rows.insert(0, _row("PR:anchor", "ratchet anchor", "PASS",
                                note, "git merge-base master HEAD"))
    return verdict


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Perf ratchet — counted proxy, floor at merge-base.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--repo", default=str(REPO))
    args = ap.parse_args(argv)

    verdict = run_gate(Path(args.repo))
    if args.json:
        print(json.dumps(verdict.rows, indent=2))
    else:
        for r in verdict.rows:
            print(f"  {r['status']:<8} {r['id']:<32} {r['detail']}")
        print(f"\n  {verdict.detail}")
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    sys.exit(main())
