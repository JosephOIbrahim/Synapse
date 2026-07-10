# H22 Drop-Day Runbook (2026-07-15)

**One page, ordered. Drop day is verification, not surgery** — the risk was
front-loaded onto H21: Mode-B rehearsal PASSED 2026-07-02 (scratch worktree,
fake `drop.json`, full 1.1→3.3 queue in order); cp312+cp313 wheels pre-cached
at `harness/state/wheel_cache/`; gate-0.1 DECIDED **sidecar** 2026-07-10
(built first post-release cycle — the drop-day contingency is the Step 2a
re-vendor). The per-build API checklist this runbook leans on is
`docs/studio/UPGRADE.md` (conformance-pinned by
`tests/test_m3_upgrade_surface.py`).

## Order of operations

1. **Install H22 side-by-side** — keep H21. Dual-build support is designed
   in: per-major symbol tables, `SYNAPSE_TEST_HOUDINI_BUILD` test axis.
2. **Capture the three numbers** (H22's hython): Python
   `sys.version_info[:2]`, USD `from pxr import Usd; Usd.GetVersion()`
   (the live-verified idiom — there is no `pxr.__version__`), PySide major,
   plus the full build string `hou.applicationVersionString()`.
3. **Write `harness/state/drop.json`** with those numbers → Mode B arms,
   pointed at H22's hython. (Human gate #2 — the trigger is yours.)
4. **Vendor decision — DECIDED, execute the contingency if needed.** H22
   still cp311 → no-op. Anything else → `UPGRADE.md` Step 2a re-vendor from
   the pre-cached wheels: payloads into `_vendor/`, widen the activation
   gate, flip `tests/test_vendored_deps.py`'s ABI tag — **all in one commit**
   (rollback = `git revert`). The sidecar is the durable fix, scheduled
   first post-release cycle, not inside the drop window.
5. **Regenerate the symbol table** — `hython host/introspect_runtime.py`
   writes `h22_symbol_table.json` **alongside** the H21 file (additive,
   never overwrite); scout auto-selects by running major. Commit the JSON.
6. **Run the API delta probe** — `hython scripts/h22_api_delta.py` →
   `probe_delta.json`/`.md` + the new punycode probe JSON.
7. **Punycode cutover** — paste the generated `PUNYCODE_PARMS` and repoint
   BOTH conformance tests in the **same commit** (code+corpus single-source
   rule — fixing one side re-teaches the phantom from the other).
8. **Delta triage** — probe truth beats pinned constants; confirmed-absent
   symbols auto-quarantine; ledger deposits carry `against_build=<H22>`.
9. **Gates, in order** — full `pytest tests/` with
   `SYNAPSE_TEST_HOUDINI_BUILD=<H22>` → hython doctor / probe_clean /
   cook_existing / install checks → `python audit_panel.py --strict`.
10. **Walk `UPGRADE.md` Steps 1–4 end-to-end** — symbol table · vendor ABI ·
    installer re-run (the new build's pref dir doesn't exist until first
    launch and auto-detect silently skips missing dirs — launch once first
    or pass `--pref-dir`) · final scout gate proof (`gate_armed: true`,
    `stale: false`, table stamp == new build).
11. **Let Mode B run the 1.x→2.x queue.** Merges stay human gate #3 —
    the harness commits in worktrees only; promotion is yours.

## Already banked — don't redo

- Mode-B trigger machinery validated (rehearsal PASS 2026-07-02; `--dry`
  no longer mutates).
- Wheel pre-cache cp312 + cp313 (`harness/state/wheel_cache/`).
- Pre-drop guardrail flips: `scout_no_apex_corpus=True`,
  `no_rigging_drift=True` (verified live 2026-07-10);
  `provenance_not_bypassed` stays warn-only by design (0a′ track).
- The 0.2 proof: Mode-A identity diff EMPTY on 21.0.671
  (`check_probe_clean ok=True`).

## If something refuses

Scout raising on a stale table is **correct** (fail-closed default). Do not
set `SYNAPSE_SCOUT_DRIFT_POLICY=warn` to make drop-day errors go away — run
step 5 first. A red gate on drop day means the checklist found the drift it
exists to find.
