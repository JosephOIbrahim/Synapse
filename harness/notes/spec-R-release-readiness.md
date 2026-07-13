# R TRACK — frozen spec (H22 release-readiness graft)

Repo: `C:\Users\User\SYNAPSE`. All paths repo-relative. Sixth additive track on the
EXISTING harness (`harness/run.ts` loop — DO NOT rebuild it).

## Mission

Wrap the 2026-07-10 external H22 readiness review
(`docs/reviews/synapse-h22-readiness-2026-07-10.md` — verdict: "H22 RC0, do not label
stable") into **durable regression gates**, exactly the S-track pattern: each finding
becomes a deterministic check that reads RED while the finding's fingerprint is live in
the code and flips GREEN only when the review's required fix lands (and stays green, so
the finding can never silently regress). The capstone (`R.R`) computes the release label
the review demands — **STABLE-READY** only when every machine gate is green AND every
live-Houdini gate has a human receipt; anything less is honestly labeled **RC**.

## Ground truth (verified 2026-07-10 — 11-agent adversarial sweep; do not re-litigate)

All review claims CONFIRMED against the live tree, with refinements the gates encode:

- **P0.2 has THREE fail-open sites**, not two: `python/synapse/panel/tool_executor.py:420-431`
  and `python/synapse/mcp/tools.py:119-128` (identical `except ImportError → handler.handle`),
  plus `python/synapse/panel/bridge_adapter.py:338-341` (`if bridge is None → handler.handle`).
  The lookalike at `mcp/server.py:604` is the read-only resources path (hdefereval import) —
  NOT a defect site; gates must exclude it. The live fail-open path in practice is site (b):
  `_BRIDGE_AVAILABLE=False → get_bridge()→None → silent direct dispatch`.
- **P0.3 is worse than lost coverage**: `synapse_panel.py:350` parents the 1s beat QTimer to
  the widget; `closeEvent` (1795) never pauses the Watchdog, so after ≥1 beat + panel close the
  monitor thread (resilience.py:606) reads dead-beat-source as a freeze and ~35s later
  `FreezeChain._escalate()` force-opens the breaker + emergency halt on a healthy session —
  a false-positive escalation. A process-lifetime beat owner must also handle deliberate
  beat-source detach. No `SynapseRuntime` exists anywhere (grep: zero hits).
- **P0.4 has TWO loaders**: `houdini/python_panels/synapse_panel.pypanel:36-38` (var `_m`) and
  `python/synapse/panel/synapse_chat.pypanel:31-33` (var `_mod_name`), both column-0
  unconditional. `SYNAPSE_DEV_HOT_RELOAD` appears nowhere in the repo.
- **P0.1**: the single activation gate is `python/synapse/__init__.py:51-57`
  (`_synapse_sys.version_info[:2] == (3, 11)` + win); the cp312/cp313 wheel cache is INERT
  (zero runtime references); on cp312/cp313 the brain dies at `daemon.py:457` with a
  manual-sidecar RuntimeError. **gate-0.1 is DECIDED → sidecar (2026-07-10,
  `docs/studio/DROP_DAY.md:6`)**, built first post-release cycle; the drop-window contingency
  is the UPGRADE.md Step-2a re-vendor. The gate greens on EITHER mechanism.
- **P0.5**: `scripts/install_synapse_package.py` auto-detect globs only existing pref dirs
  (line 75) and silently drops a set-but-uncreated `$HOUDINI_USER_PREF_DIR` (line 79); argparse
  is `--pref-dir`/`--dry-run` only; NO post-install host verification (the stamp at line 154
  is runtime-doctor telemetry). Legacy `install.py` hardcodes majors `[21, 20, 19]`.
- **P0.6**: `.github/workflows/ci.yml` is the only workflow; matrix
  `os: [ubuntu-latest, macos-latest]` × py 3.11/3.14, stock pytest. Four panel modules
  skip-exit-0 without PySide (`test_docking.py:80` etc. — the documented goalpost trap).
  `tests/test_vendored_deps.py` checks the cp311 binary BY FILENAME, never loads it.
- **P1-shelf**: `houdini/scripts/python/synapse_shelf.py:22` imports PySide2 only (H21 ships
  PySide6 only → clipboard ALWAYS returns False on target platform); line 113 tells users to
  run `python install.py` (the documented installer is `scripts/install_synapse_package.py`).
  CAVEAT: the repo-standard fix keeps PySide2 as fallback, so the PySide2 literal SURVIVES the
  fix — gate on `from PySide6` PRESENCE in that file, never on PySide2 absence.
- **P1-metadata is NOT covered by S.1**: `check_policy_single_source` fingerprints
  `shared/bridge.py`'s `OPERATION_GATES.get(..., GateLevel.REVIEW)` and its taxonomy list
  omits `panel/bridge_adapter.py`. The unsafe default
  `_TOOL_TO_OPERATION.get(tool_name, "set_parameter")` (bridge_adapter.py:344 — unknown tool
  → set_parameter → INFORM, the weakest gate) needs its own fingerprint (repo-unique literal).
- **P1-consent has a SECOND disarm site S.2 is blind to**: `shared/bridge.py:1946-1947` —
  `get_process_bridge()` constructs the singleton with `consent_callback=lambda op: True` and
  `bridge._gate = None`. S.2's regex covers only `bridge_adapter.py`; deleting the panel disarm
  alone would flip S.2 green while the process bridge stays gate-less.
- **P1-auth is ENTIRELY ungated today**: `auth.py:111-113` (no key → every token passes),
  `auth.py:153-154` (empty Origin → allow), `websocket.py:395-397` (handshake conditional on a
  key existing). No existing check references any of these.
- **P1-packaging**: dual-path PYTHONPATH in BOTH writers (`scripts/install_synapse_package.py:50`,
  `packages/synapse.json:13`) + a third in-package insertion the review missed
  (`integrity_envelope.py:48-51` climbs to repo root at import time). 19 top-level
  `from shared...` sites under python/synapse. Review's own scope call: fix AFTER H22
  stabilization → non-blocking hygiene gate.
- Harness seams: checks return `{"ok": bool|None, "detail": str}`, ctx =
  `{"wt", "hython", "mode"}`, DISPATCH registration, tests load checks.py by path and plant
  synthetic worktrees (`_plant`/`_ctx` style, test_s_track.py). guardrails.checks is frozen
  byte-for-byte — R adds TASK verifies, NEVER guardrails.

## FROZEN CONTRACT (critics may attack; builders may NOT change)

### 1. Trigger + run.ts additions

- Arming pattern: **JSON-predicate ratification flip**, the D.0 pattern. A human sets the
  `R.0` cycle's `ratified` to `true` in the git-tracked `harness/state/flywheel_queue.json`
  (the anti-runaway anchor — the harness reads it, never writes it). Until then every
  `blocked_on:"release_ratified"` task (R.1–R.10, R.R) is held and a read-only intake surface
  prints the exact flip. `--task R.n` cannot pierce the hold.
- run.ts: `const RELEASE_RATIFIED` mirroring `COOK_RATIFIED` (same loud-hold parsing, id
  `"R.0"`); queue filter
  `queue = queue.filter((t) => !(t.blocked_on === "release_ratified" && !RELEASE_RATIFIED));`
  after the cook filters; one dim status line (armed/held); `surfaceReleaseIntake()` called
  after `surfaceCookIntake()` — prints the flip line + a note that the verdict is computable
  on demand regardless of the hold via
  `python harness/verify/checks.py --task R.R --worktree . --mode A`.
- `--dry` stays mutation-free. `--drive` is untouched (it keys on the S-track verdict).

### 2. Second human state-file: release receipts

`harness/state/release_receipts.json` (runtime state, untracked, peer of drop.json) — the
human's record of the LIVE gates no machine check can decide (fresh-account graphical install,
panel-close lifecycle, restart, rollback drill, core smoke, undo receipt). Schema: an object
whose keys are `g1_clean_install`, `g5_lifecycle`, `g6_core_smoke`, `g7_reversibility`,
`g8_restart`, `g9_rollback`, each `{"result": "pass"|"fail", "build": str, "date": str,
"notes": str}`. Absent file / absent key / non-"pass" result ⇒ that gate is PENDING (never
faked). Example file: `harness/state/release_receipts.json.example`. The harness NEVER writes
receipts (human gate, like posture.json).

### 3. New tasks in harness/tasks.json (phase "release")

Appended after D.5. Add the 12 new check names to `checks_vocabulary`. All tasks mode A,
`blocked_on:"release_ratified"`. Order = the review's Phase-1 order.

- `R.1` crit true, layer "safety" — mutations fail closed when the bridge is unavailable
  (P0.2, all THREE sites). refs: tool_executor.py, mcp/tools.py, panel/bridge_adapter.py,
  server/handlers.py (the import-independent `_READ_ONLY_COMMANDS` a fix can gate on), spec.
  verify: ["mutation_fail_closed"].
- `R.2` crit true, layer "survival" — process-lifetime beat owner (P0.3). refs:
  panel/synapse_panel.py, server/freeze_chain.py, server/resilience.py, spec.
  verify: ["runtime_owns_heartbeat"]. Note: must ALSO handle deliberate beat-source detach
  (the false-positive escalation refinement).
- `R.3` crit true, layer "survival" — gate the production module purge behind
  `SYNAPSE_DEV_HOT_RELOAD` (P0.4, BOTH loaders). refs: the two .pypanel files, spec.
  verify: ["hot_reload_gated"].
- `R.4` crit true, layer "survival" — dependency isolation across Python minors (P0.1).
  refs: python/synapse/__init__.py, python/synapse/host/daemon.py, docs/studio/UPGRADE.md,
  docs/studio/DROP_DAY.md, spec. verify: ["deps_isolated"]. Note: direction DECIDED (sidecar,
  gate-0.1 2026-07-10); gate greens on either versioned vendor roots (drop-window minimum)
  or the sidecar landing. NOT a human gate — the decision is already committed.
- `R.5` crit true, layer "survival" — host-targeted installer + post-install host verify
  (P0.5). refs: scripts/install_synapse_package.py, install.py, tests/test_install_package.py,
  spec. verify: ["installer_host_targeted"].
- `R.6` crit true, layer "eval" — CI covers the shipping surface (P0.6): Windows lane +
  vendored-wheel LOAD probe. refs: .github/workflows/ci.yml, tests/test_vendored_deps.py,
  spec. verify: ["ci_covers_shipping_surface"]. Hosted-runner scope only; hython/graphical
  lanes are receipts territory (G6).
- `R.7` crit true, layer "hygiene" — shelf currency (P1-shelf): PySide6-first clipboard +
  current installer message. refs: houdini/scripts/python/synapse_shelf.py, spec.
  verify: ["shelf_current"].
- `R.8` crit false, layer "safety" — unknown-tool metadata fails closed (P1-metadata).
  refs: python/synapse/panel/bridge_adapter.py, shared/constants.py, spec.
  verify: ["tool_metadata_single_source"].
- `R.9` crit false, layer "safety", **human_gate** — fail-closed security defaults
  (P1-consent + P1-auth): arm the process bridge (`get_process_bridge` disarm) + fail-closed
  auth (no-key/no-Origin/conditional-handshake). human_gate: { decision: "arm the process
  bridge's consent path (non-blocking approval surface) + fail-closed auth defaults",
  why: "Security-critical, human-authored, harness-gated (S.2/S.3 precedent). Closes the
  shared-bridge disarm S.2 cannot see and the auth surface no check covers. Under a solo
  posture these stay accepted trade-offs; the gates keep them visible + regression-proof." }
  refs: shared/bridge.py, python/synapse/server/auth.py, python/synapse/server/websocket.py,
  python/synapse/panel/bridge_adapter.py, spec.
  verify: ["process_bridge_armed", "auth_fail_closed"].
- `R.10` crit false, layer "hygiene" — packaging self-containment (P1-packaging; review's
  own scope: AFTER H22 stabilization — non-blocking). refs:
  scripts/install_synapse_package.py, packages/synapse.json,
  python/synapse/server/integrity_envelope.py, pyproject.toml, tests/test_install_package.py,
  spec. verify: ["packaging_self_contained"].
- `R.R` crit true, layer "review" — capstone release-readiness review: aggregate every
  R-check + receipts + posture, compute the G1–G10 map, emit
  `harness/state/release_readiness_verdict.json`. refs: spec, the review doc,
  harness/state/release_receipts.json.example. verify: ["release_readiness_review"].

### 4. New checks in harness/verify/checks.py

Return shape/DISPATCH/honest-false/local-import/stdlib rules identical to the S block.
Register all 12 under a `# R — release-readiness (H22 RC) track` comment after the S rows.
Module-level seams for tests: `_receipts_path()` and `_drop_path()` (main-repo files, like
`_posture_path()`). Fingerprints below are VERIFIED live (they read RED today); a builder who
finds one not matching must STOP and report, never invent a passing check.

- `mutation_fail_closed` — RED while ANY of: `panel/tool_executor.py` or `mcp/tools.py`
  matches `except ImportError:\s*\n\s*response = handler\.handle\(command\)` (re.M-free,
  whitespace-tolerant); `panel/bridge_adapter.py` matches
  `if bridge is None:[\s\S]{0,80}?return handler\.handle\(command\)` (bounded — must NOT
  match get_session_report's `if bridge is None: return None` nor the bridge-routed
  handler.handle at line 371). detail names live sites + the fix criterion (fail-closed
  error for non-read-only tools; classification must come from an import-independent source).
  GREEN only when all three are gone.
- `runtime_owns_heartbeat` — two legs. RED while `panel/synapse_panel.py` matches
  `self\._freeze_timer = QTimer\(self\)` (the panel-parented beat source). When that literal
  is gone, still RED unless a non-panel owner exists: some file under `python/synapse/server/`
  carries the `# RUNTIME_BEAT_SOURCE` sentinel marker or a `def ensure_beat_started`
  definition — so deleting the panel timer WITHOUT a replacement (no freeze protection at
  all) can never green the gate. detail explains both legs + the detach requirement.
- `hot_reload_gated` — per loader file (`houdini/python_panels/synapse_panel.pypanel`,
  `python/synapse/panel/synapse_chat.pypanel`): RED if the column-0 purge is live
  (`^for _m in sorted\(` / `^for _mod_name in sorted\(` with the sys.modules body, or
  `^sys\.modules\.pop\("synapse", None\)` at column 0), OR if the file still contains
  `del sys.modules[` with NO `SYNAPSE_DEV_HOT_RELOAD` literal (catches re-nesting under an
  always-true block). A loader file that no longer exists auto-greens its leg. GREEN = both
  legs clear (purge deleted entirely, or indented under the env gate).
- `deps_isolated` — RED while `python/synapse/__init__.py` matches
  `_synapse_sys\.version_info\[:2\] == \(3, 11\)` (the strict single-ABI equality) AND no
  sidecar def/class exists under `python/synapse/host/` (regex on def/class lines:
  `^\s*(def \w*sidecar\w*|class \w*Sidecar\w*)` — never prose/comments; the daemon's
  RuntimeError MESSAGE mentions "sidecar" and must not satisfy this). GREEN = the strict
  equality replaced by a version-derived root (versioned vendor) OR a sidecar
  implementation landing. detail cites gate-0.1's decided direction.
- `installer_host_targeted` — PRESENCE gate on `scripts/install_synapse_package.py`:
  RED while `--houdini-exe` is absent from the file OR no verification symbol exists
  (neither regex `def verify_(install|host)` nor an `add_argument("--verify"` line).
  detail names the missing leg(s) + the derive-from-exe fix shape.
  FIX_IS_REAL_PROBE (PRESENCE-gate standard): the fixing sprint must extend
  tests/test_install_package.py with a behavioral case driving the verify step against a
  tmp pref dir — named in the R.5 task note, enforced at review, not by this check.
- `ci_covers_shipping_surface` — RED while `.github/workflows/ci.yml` lacks
  `windows-latest` OR lacks a vendored-load probe (no `pydantic_core` literal anywhere in
  the workflow — the Windows lane must IMPORT the vendored binary, not just list filenames).
  detail names the missing lane/probe. Host (hython/graphical) lanes are NOT this gate —
  they are receipts (G6).
- `shelf_current` — RED while `houdini/scripts/python/synapse_shelf.py` lacks
  `from PySide6` OR lacks `install_synapse_package.py`. (PRESENCE gate by necessity — the
  PySide2 literal legitimately survives a fallback-style fix.)
- `tool_metadata_single_source` — RED while `panel/bridge_adapter.py` contains
  `_TOOL_TO_OPERATION.get(tool_name, "set_parameter")` (repo-unique literal; unknown tool →
  INFORM, the weakest gate). detail explains the unknown-capability danger + fix shape
  (single policy source + fail-closed unknown handling).
- `process_bridge_armed` — RED while `shared/bridge.py` matches `bridge\._gate = None`
  (the `bridge.`-prefixed literal is unique to get_process_bridge — never matches
  `self._gate`) OR contains `consent_callback=lambda op: True`. The S.2 blind spot, closed.
- `auth_fail_closed` — RED while ANY of: `server/auth.py` matches
  `if expected_key is None:\s*\n\s*return True` (token-always-passes) or
  `if not origin:\s*\n\s*return True` (empty-Origin allow); `server/websocket.py` contains
  `auth_required = auth_key is not None` (handshake conditional on a key existing).
  detail lists live legs.
- `packaging_self_contained` — RED while `packages/synapse.json` matches
  `"\$SYNAPSE_ROOT/python",\s*"\$SYNAPSE_ROOT"` (the dual-path PYTHONPATH; the two-element
  sequence never matches the SYNAPSE_ROOT env-var definition) OR
  `server/integrity_envelope.py` contains `from shared.bridge import IntegrityBlock`
  (top-level `shared` import in packaged product code). Non-blocking hygiene.
- `release_readiness_review` — CAPSTONE. Runs the other 11 R-checks directly (global names,
  monkeypatch-able), reads posture (`_read_posture()`), receipts (`_read_receipts()`), and
  drop (`_drop_path()`), and computes:
  - **machine blockers** (block STABLE always): the 7 review-Phase-1 gates
    {mutation_fail_closed, runtime_owns_heartbeat, hot_reload_gated, deps_isolated,
    installer_host_targeted, ci_covers_shipping_surface, shelf_current} that are not ok:true.
  - **security legs** {process_bridge_armed, auth_fail_closed}: posture-scoped exactly like
    S.R — solo ⇒ ACCEPTED (listed in `accepted_under_posture`, non-blocking, snap back to
    blockers under studio/farm/undeclared).
  - **open hygiene** (never blocks): {tool_metadata_single_source, packaging_self_contained}.
  - **receipts**: the six live gates (g1, g5, g6, g7, g8, g9) — each PENDING unless its
    receipt says result:"pass". PENDING receipts block STABLE.
  - **G3 host truth**: mode A ⇒ "pending-drop" (blocks STABLE, honestly — no H22 exists);
    mode B ⇒ green iff `python/synapse/cognitive/tools/data/h<major>_symbol_table.json`
    exists in the worktree, where `<major>` comes from drop.json's houdini field.
  - **G10 documentation truth**: `claim_ok = (README.md makes no H22-verified/H22-ready
    claim) OR (machine blockers empty AND receipts all pass AND G3 green)`. A premature
    README claim is itself a named blocker. Claim regex (case-insensitive):
    `H22[\s-]*(ready|verified)|Houdini\s*22[\s-]*(ready|verified)`.
  - **verdict**: `STABLE-READY` iff machine blockers empty AND security satisfied-or-accepted
    AND all receipts pass AND G3 green AND G10 ok. Else `RC — <the honest reason class>`
    (machine gates red / receipts pending / pending-drop), blockers listed. ok:true ONLY on
    STABLE-READY — R.R is the stable-promotion gate, un-bankable until the drop is verified.
    That is by design ("review at the end").
  - Emits `harness/state/release_readiness_verdict.json`:
    `{generated, per_check, receipts, g_map, blockers, accepted_under_posture, open_hygiene,
    verdict, posture, mode, studio_readiness_crossref}` — the crossref reproduces
    `studio_readiness_verdict.json`'s verdict string read-only if present (never recomputed
    here; no double-aggregation of S checks).

### 5. New tests — tests/test_r_track.py

Load checks.py by path (alias `harness_checks_r`); test_s_track.py's `_plant`/`_ctx` style;
NEVER sys.modules fakes; monkeypatch ONLY the `_receipts_path`/`_drop_path`/`_posture_path`
seams and capstone sub-check stubs (both attr and DISPATCH row). ~20 cases:
- conformance: every R id matches `^R\.(\d{1,2}|R)$`; every R task carries
  `blocked_on:"release_ratified"`; R.9 carries human_gate; every R verify name in DISPATCH +
  checks_vocabulary; guardrails.checks unchanged (pin the frozen 5-name list byte-for-byte).
- per-check RED/GREEN pairs with synthetic worktrees (fixture pair per check; substring
  assertions on detail, never exact-string).
- runtime_owns_heartbeat: deletion-without-replacement stays RED (the two-leg case).
- hot_reload_gated: indented purge + env literal ⇒ GREEN; purge deleted ⇒ GREEN; col-0 ⇒ RED;
  indented purge WITHOUT env literal ⇒ RED.
- capstone: all-green stubs + all-pass receipts + mode B + symbol table + no README claim ⇒
  STABLE-READY ok:true; one machine red ⇒ RC naming it; machine green + missing receipts ⇒
  RC "receipts pending"; mode A ⇒ pending-drop blocks; README premature claim ⇒ G10 blocker;
  solo posture ⇒ security legs accepted + listed, studio ⇒ blocking.
- Tests run under stock pytest, no hou, tmp_path only.

### 6. Queue + docs (orchestrator-owned)

- `harness/state/flywheel_queue.json`: cycle `R.0`, status "candidate", `ratified:false`,
  evidence = this spec + the review doc + checks.py + tests/test_r_track.py. A NEW cycle
  CLASS — RELEASE truth (does the shipping product still carry each verified release-blocking
  defect, and is every release-label claim receipt-backed) — a different axis from
  WIRING/CONTEXT/CAPABILITY/READINESS/DIAGNOSTIC truth.
- `harness/README.md`: release-readiness track section (sixth trigger — ratification flip;
  receipts file; R.1–R.R one-liners) + Files rows.
- `harness/state/claude-progress.md`: MODE RULE line + one LOG delta.
- `harness/state/release_receipts.json.example`: the six receipt keys with a commented
  example (mirror drop.json.example).

## Style & traps (binding)

- Match checks.py/run.ts comment voice: first-person rationale, why-not-what, dense.
- Surgical, additive; never reformat existing code; LIVE TREE (no worktrees, no commits —
  promotion is the human's).
- Do NOT touch: guardrails.checks, any existing check or task, VERSION, product code under
  python/synapse (R-checks READ product code; the fixes are the armed loop's / human's
  separate sprints).
- Fingerprint honesty: every gate reads RED today (verified); GREEN only when the SPECIFIC
  defect is gone. PRESENCE gates (installer/shelf/CI legs) carry the FIX_IS_REAL_PROBE
  obligation in their task notes.
- tasks.json valid JSON, 2-space indent; checks stdlib-only, no hython anywhere in R.
