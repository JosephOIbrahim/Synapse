# PROPOSED-P5.1 — production code phantom-clean across hou/pdg/pxr

> **Status: PROPOSED — surfaced for Joe's ratification.** Not ratified. Do NOT edit
> `harness/clear/SPEC.md` or `harness/clear/verify.py` until Joe flips this to ratified.
> This file is the ratification packet: the predicate, the SPEC.md amendment diff (not
> applied), the verify.py snippet (not applied), and the ask.
>
> **Author:** FORGE leg, CLEAR L5 (2026-07-31).
> **Builds on:** the ratified P3.x phantom guardrail (`harness/verify/checks.py::
> _hou_phantoms_in_source` + `check_phantom_clean`), pinned by
> `tests/test_phantom_guardrail.py`.

---

## 1. The gap (why this predicate exists)

SYNAPSE's #1 failure class is phantom APIs (`hou.pdg.*`, `hou.secure`,
`hou.lopNetworks()`, `pdg.PyEventHandler`, `pdg.EventType`). The membership
AUTHORITY — `python/synapse/cognitive/tools/data/h22_symbol_table.json`, built by
`host/introspect_runtime.py` — already authoritatively covers **hou, pdg, AND pxr**:
its self-check asserts `pdg.EventType` and `pxr.Usd` are in the table (it dir()-walks
`hou` depth 2, `pdg` depth 2, AND `pxr` depth 1).

The LINT — `harness/verify/checks.py::_hou_phantoms_in_source` — is **hou-ONLY**: it
collects only `import hou` aliases and flags only `hou.<attr>` depth-1 accesses. It
does NOT scan `pdg.*` or `pxr.*` accesses. So a bare `pdg.PyEventHandler(fn)` or
`pdg.EventType.CookComplete` slips through `check_phantom_clean` TODAY even though the
table knows `pdg.EventType` is real and `pdg.PyEventHandler` is a phantom (no constructor
on H21.0.671 / H22.0.368).

**The authority covers pdg/pxr; the scanner does not. The gap is real.**

### CTO verdict on the depth asymmetry (advisory — VERIFIED 2026-07-30)

- **pdg — SOUND.** `host/introspect_runtime.py:94-97` does
  `_walk(pdg, "pdg", 0, DEPTH_HOU_PDG=2, ...)`, iterating `dir(pdg)` at depth 0. Every
  top-level pdg name is enumerated by the same mechanism hou uses. 235 pdg depth-1 names
  in the H22 table; `pdg.EventType`, `pdg.PyEventHandler`, `pdg.GraphContext`,
  `pdg.Scheduler`, `pdg.WorkItem` all present. A depth-1 lint on `pdg.<attr>` carries
  the same proof-by-absence guarantee as hou. Production code (`shared/bridge.py:1581-
  1593`) uses `import pdg as _pdg` then `_pdg.EventType.CookComplete`, so the lint MUST
  resolve `import pdg as <alias>` exactly as the hou lint resolves `import hou as X`.
- **pxr — NOT SOUND as-is for arbitrary `pxr.<attr>`.** `introspect_runtime.py:101-115`
  does NOT call `_walk(pxr, ...)`. It does `out.add("pxr")` then enumerates submodules via
  `pkgutil.iter_modules(pxr.__path__)` + each submodule's depth-1 members. It does NOT
  enumerate `dir(pxr)` itself — any non-submodule top-level attribute (a function,
  constant, or dynamically-attached name) is absent from the table. The 41 pxr depth-1
  names are ALL submodules (Ar, Sdf, Tf, Usd, UsdGeom, ...). A depth-1 lint on
  `pxr.<attr>` would FALSE-PHANTOM a real `pxr.<non-submodule-attr>`.

  **Practical impact is low and the reach is near-zero:** SYNAPSE production code never
  uses `pxr.<attr>` Attribute access — it uses `from pxr import Usd` then `Usd.Attribute`
  (so `node.value.id` is the submodule name, not `pxr`; the depth-1 lint never fires on
  real pxr usage). The only `pxr.<Capital>` tokens in source are in docstrings, comments,
  test-mock string literals, and the introspect self-check — all non-Attribute AST nodes
  the lint ignores. The FORGE implementation extends the lint to pxr ANYWAY (the task
  asked for it), documents the soundness gap inline, and unions NO allowlist (no real
  false-phantom fires in current code; the CTO's "only if a real false-phantom would
  otherwise fire" condition is not met). Closing the gap for real requires a table-build
  change: add `_walk(pxr, "pxr", 0, 0, ...)` to capture non-submodule top-level attrs.

---

## 2. What FORGE already shipped (the lint extension — DONE, not awaiting ratification)

The AST lint extension is **already implemented** in `harness/verify/checks.py` and
pinned by extended tests in `tests/test_phantom_guardrail.py` (24 tests pass). This is
a NOW-probe improvement to the existing guardrail and does NOT require SPEC ratification
— it closes the "scanner doesn't cover pdg/pxr the table already authorizes" gap inside
the existing `check_phantom_clean` gate, preserving its current gate-down=WARN
semantics.

- `_hou_phantoms_in_source` — KEPT INTACT (existing tests pin it).
- `_module_depth1_phantoms(src, table_syms, module_name)` — NEW generalized depth-1
  scanner for any module the table dir()-walks at depth 0 (pdg). Documents the pxr
  soundness gap inline.
- `_phantoms_in_source(src, table_syms)` — NEW unified scan = hou + pdg + pxr.
- `check_phantom_clean` — wired to call `_phantoms_in_source`; detail message updated to
  `phantom hou.*/pdg.*/pxr.* introduced`.

**What this did NOT change:** the gate-down posture. `check_phantom_clean` still returns
`ok:None` (WARN, never a false block) when the symbol table is missing/stale. That
clearance-semantics change is what P5.1 ratifies — see §3.

---

## 3. The P5.1 predicate (the ratification ask)

**P5.1 — production code is phantom-clean across hou/pdg/pxr, with clearance
semantics: a down authority gate is a FAIL, not a WARN.**

Two halves, both required for P5.1 to PASS:

1. **Coverage.** The sprint's changed `.py` introduces no table-proven-absent
   `hou.<attr>` / `pdg.<attr>` / `pxr.<attr>` depth-1 access. The authority is the
   introspected dir() symbol table (`h<major>_symbol_table.json`); the scanner is
   `_phantoms_in_source` (hou + pdg + pxr depth-1). (SHIPPED by FORGE — the lint now
   covers all three.)

2. **Clearance semantics.** A missing/stale/mismatched symbol table is a **FAIL**, not
   a WARN. Today `check_phantom_clean` returns `ok:None` (WARN) on a gate-down,
   reflecting "cannot prove absence ⇒ do not false-block." P5.1 inverts this for the
   CLEAR bar: a down authority gate means the phantom defense is **off**, and a sprint
   that cannot prove its code phantom-clean does not clear. `ok:None` → `ok:False` with
   a detail naming the gate-down reason (missing/stale/build-mismatch).

   **Why this is a ratification, not an auto-fix:** the WARN posture is the deliberate
   single-user-localhost default (auto-approve on a down gate, never a false block). The
   CLEAR clearance bar is a stricter posture — it says "if you can't prove it's clean,
   you don't ship." That is a posture decision, Joe's to make, not FORGE's to flip. The
   FORGE implementation keeps WARN so the existing harness behavior is unchanged until
   Joe ratifies.

### Soundness caveat carried into the predicate

The pxr branch is NOT dir()-complete (§1). P5.1's pxr coverage is therefore
**submodule-scoped in practice**: it catches a phantom `pxr.<BadSubmodule>` (absent
from the 41-name submodule list) but cannot soundly catch a `pxr.<non-submodule-attr>`
(the table doesn't enumerate `dir(pxr)`). This is documented inline in
`_module_depth1_phantoms` and accepted because (a) zero `pxr.<attr>` depth-1 accesses
exist in production code, and (b) the alternative — silently unioning a blanket pxr
allowlist — would defeat the lint for the case that DOES matter (phantom submodules).
A future table-build change (`_walk(pxr, "pxr", 0, 0, ...)`) closes the gap and makes
P5.1's pxr coverage fully dir()-complete.

---

## 4. SPEC.md amendment diff (NOT applied — for ratification)

Against the ratified `harness/clear/SPEC.md` "Acceptance Predicates" table. This adds
P5.1 as a new row without altering any existing predicate.

```diff
 ## Acceptance Predicates

 The bar. These IDs are canonical — used verbatim in PLAN, CHAMPION, verify.py, and the progress bar.

 | ID | Predicate | Check |
 |---|---|---|
 | **P1.1** | Latency-relay files are committed at `<sha>` OR dropped via a logged human gate | `git log --all` finds all 6 files, OR a DECISIONS/flywheel entry marks the set dropped |
 | **P2.1** | Board is non-stale (regenerated <24h) AND cycle C.0 has a recorded human decision (ratified OR explicitly deferred) | `python harness/decisions.py --count` runs + read `harness/state/flywheel_queue.json` C.0 |
 | **P3.1** | F6 fixed: SessionStart pings before reporting "connected" | `tests/test_sessionstart_ping.py` collects + passes |
 | **P3.2** | CI mcp drift resolved (mcp pinned OR `mcp_server.py:899` updated) | `python -m pytest tests/test_passthrough_hygiene.py --co -q` collects without the `list_tools` error |
 | **P3.3** | `websocket.py:471` cancel is reachable mid-frame | a cancel-injection test passes |
 | **P3.4** | husk render cure is parked behind a named gate (Indie-blocked) | a DECISIONS/flywheel entry exists; no agent claims to "fix" it |
 | **P3.5** | Latency report §1 addendum appended (Joe's gate) | addendum file exists OR a "gated, deferred" entry |
 | **P4.1** | v5.34–v5.40 have CHANGELOG entries OR a deliberate "not backfilling" decision | `CHANGELOG.md` grep for `## v5.34`..`## v5.40` + DECISIONS entry |
+| **P5.1** | Production code is phantom-clean across hou/pdg/pxr, with clearance semantics: a down authority gate is a FAIL, not a WARN | `harness/verify/checks.py::check_phantom_clean` over the sprint's changed `.py` returns `ok:True` (no table-proven-absent `hou.<attr>`/`pdg.<attr>`/`pxr.<attr>` depth-1 access) AND a missing/stale/mismatched symbol table yields `ok:False`, not `ok:None` |
```

And a matching row in the "Verification Strategy" table:

```diff
 | P4.1 | L1 (grep + entry) | No |
+| P5.1 | L1 (AST lint over changed .py) + L4 (crucible: inject a phantom pdg.*/pxr.* + a downed table, assert FAIL not WARN) | No |
 | All gates | L4 (crucible: tries to make an agent flip `ratified`, cross Gate C, narrate a false bar) | No |
```

---

## 5. verify.py snippet (NOT applied — for ratification)

The function P5.1's check would add to the ratified `harness/clear/verify.py`. It
calls the existing `check_phantom_clean` and judges BOTH halves: coverage (ok:True) AND
clearance semantics (a down gate is FAIL, not the WARN FORGE shipped). Until ratified,
this snippet is NOT wired into `PREDICATES` — it lives only in this proposal.

```python
# --- P5.1: phantom-clean across hou/pdg/pxr, gate-down=FAIL (proposed) ---
def p5_1():
    """PASS only if the sprint's changed .py is phantom-clean across hou/pdg/pxr AND a
    down/stale symbol table is a FAIL (not a WARN). Calls the harness guardrail
    (harness/verify/checks.py::check_phantom_clean) with the worktree as ctx.

    NOTE: the shipped check_phantom_clean returns ok:None (WARN) on a gate-down. P5.1
    ratification FLIPS that to ok:False at the CLEAR-bar layer (this function maps
    ok:None -> FAIL), without mutating the harness guardrail's own posture for the
    non-CLEAR run.ts path. The harness flip (ok:None -> ok:False inside
    check_phantom_clean itself) is a separate, follow-on ratification; this predicate
    enforces the CLEAR-bar posture regardless.
    """
    import importlib.util
    checks_path = REPO / "harness" / "verify" / "checks.py"
    spec = importlib.util.spec_from_file_location("harness_checks", checks_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.check_phantom_clean({"wt": str(REPO), "hython": os.environ.get("HYTHON", "")})
    ok = result.get("ok")
    detail = result.get("detail", "")
    if ok is True:
        return PASS, detail
    if ok is None:
        # P5.1 clearance semantics: a down authority gate is a FAIL, not a WARN.
        return FAIL, f"authority gate down (P5.1 treats WARN as FAIL): {detail}"
    return FAIL, detail


# When ratified, add to PREDICATES:
#     ("P5.1", "phantom-clean hou/pdg/pxr (gate-down=FAIL)", p5_1),
```

---

## 6. The ratification ask

**Joe —** ratify P5.1 to make the CLEAR clearance bar treat a down phantom-authority
gate as a FAIL instead of a WARN. The coverage half (lint scans hou + pdg + pxr) is
already shipped and tested; ratification flips the posture:

- **If you ratify:** apply the §4 SPEC.md diff (add the P5.1 row) and the §5 verify.py
  snippet (add `p5_1` + register it in `PREDICATES`). The harness guardrail
  (`check_phantom_clean`) can keep its WARN for the run.ts path; the CLEAR bar maps
  `ok:None -> FAIL` at the bar layer, OR you can ratify the deeper flip (warn → fail
  inside `check_phantom_clean` itself) as a follow-on.
- **If you defer:** P5.1 stays PROPOSED. The FORGE lint extension (hou + pdg + pxr
  coverage, WARN on gate-down) remains in place — the gap "scanner doesn't cover
  pdg/pxr the table already authorizes" is closed either way; only the stricter
  gate-down posture waits for you.

**One open question for you:** the pxr branch is submodule-scoped (not dir()-complete).
Do you want a follow-on table-build change — `_walk(pxr, "pxr", 0, 0, ...)` in
`host/introspect_runtime.py` — to make P5.1's pxr coverage fully sound, or is the
documented submodule-scoped acceptance (zero production `pxr.<attr>` accesses today)
good enough? FORGE recommends the table-build follow-on before any future pxr-heavy
sprint, but it is not blocking P5.1.