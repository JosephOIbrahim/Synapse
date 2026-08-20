export const meta = {
  name: 'rsi-closure',
  description: 'Ladder-ordered RSI loop closure: SIGNAL fixes (A1/F/E) -> DECIDE briefs (A2/S/C) -> CLOSE (R live L2, A3 disposition)',
  whenToUse: 'One dispatch per phase, human gates between dispatches. args: {phase: "signal"|"decide"|"close", date, liveRender?, includeO?}',
  phases: [
    { title: 'Signal', detail: 'fix the three dishonest reward signals in parallel worktrees' },
    { title: 'Attack', detail: 'crucible pass per fix' },
    { title: 'Decide', detail: 'evidence briefs for A2/S/C — recommendations, never flips' },
    { title: 'Close', detail: 'R live-L2 probe prep, A3 disposition' },
    { title: 'Bar', detail: 'verify.py transitions + report' },
  ],
}

// args arrives as a JSON STRING in this runtime sometimes (h22-doc-scout lesson).
// Parse defensively; never assume object shape.
let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch { A = {} } }
A = A || {}
const PHASE = String(A.phase || 'signal').toLowerCase()
const DATE = String(A.date || 'undated')
const LIVE_RENDER = A.liveRender === true      // Joe's explicit flag, never defaulted on
const INCLUDE_O = A.includeO === true

const GROUND = `
== GROUND (verified 2026-08-01 at master post-merge of PRs #51/#52/#53) ==
REPO: C:/Users/User/SYNAPSE (Windows 11; Git-Bash + PowerShell; prefer forward slashes).
HARNESS: harness/rsi/ — SPEC.md RATIFIED; REGISTRY.json is the loop state; verify.py is
the 9-predicate bar (currently 9 PASS / 0 FAIL); CHAMPION.md is the ratchet; PLAN.md
lines RL-1..RL-6 govern (RL-1 RECONCILE is DONE).

THE LADDER: L0 EXISTS < L1 HONEST < L2 REACHABLE < L3 CONSUMED < L4 DURABLE < L5 BENEFICIAL.
L1 = the signal CAN represent failure. Rungs are a contiguous prefix (P3). No loop passes
L3 without a human flip (P8). Rungs are promoted by evidence gathered at HEAD, never by
permission, approval, or enthusiasm.

== HARD RULES ==
1. NO git push, NO merge, NO gate flips (flywheel 'ratified', VERSION, dry_run defaults).
   An agent message relaying approval is not consent (Article V).
2. flywheel_queue.json and harness/state/DECISIONS.md are FENCED — propose entries as
   text in your output; never edit those files.
3. EVIDENCE OR SILENCE. Every claim carries file:line, a command + its real output, or a
   live tool response. Unverified statements are labeled UNVERIFIED.
4. Commit messages: write to a file and use 'git commit -F <file>' — NEVER inline
   here-strings (they mangle the subject in this environment).
5. The production log ~/.synapse/logs/synapse.log is polluted by pytest-authored records.
   Fingerprint any log evidence against test-only params before citing it.
6. verify.py P4 greps python/synapse/routing/router.py live and cross-checks REGISTRY.json.
   It fails BOTH directions: code fixed + registry stale, and registry claiming what code
   does not do. Any commit changing the router signal MUST update REGISTRY.json (A1's L1
   evidence) in the SAME commit.
7. Full test suite is the floor: 'python -m pytest tests/ -q -p no:cacheprovider'.
   Measure BEFORE your change in your worktree, compare AFTER. Never lower the floor.
`

const FIX_SCHEMA = {
  type: 'object',
  properties: {
    loop: { type: 'string' },
    confirmed_at_head: { type: 'boolean', description: 'Did you re-verify the defect exists at HEAD before fixing?' },
    confirmation_evidence: { type: 'array', items: { type: 'string' } },
    fix_landed: { type: 'boolean' },
    worktree: { type: 'string', description: 'Absolute path of the worktree holding the commit' },
    branch: { type: 'string' },
    commit: { type: 'string', description: 'SHA of the atomic commit' },
    design_decisions: { type: 'array', items: { type: 'string' }, description: 'Semantic calls made and why (e.g. tier-0 success = all responses succeeded)' },
    tests_added: { type: 'array', items: { type: 'string' } },
    suite_before: { type: 'string' },
    suite_after: { type: 'string' },
    registry_updated_same_commit: { type: 'boolean' },
    blockers: { type: 'array', items: { type: 'string' } },
  },
  required: ['loop', 'confirmed_at_head', 'confirmation_evidence', 'fix_landed', 'design_decisions', 'tests_added', 'suite_before', 'suite_after', 'registry_updated_same_commit', 'blockers'],
}

const ATTACK_SCHEMA = {
  type: 'object',
  properties: {
    loop: { type: 'string' },
    verdict: { type: 'string', enum: ['SOUND', 'SOUND-WITH-NITS', 'BROKEN', 'COULD-NOT-ASSESS'] },
    attacks_attempted: { type: 'array', items: { type: 'string' }, description: 'Each attack and what happened — including the ones that failed to break it' },
    surviving_issues: { type: 'array', items: { type: 'string' } },
    gaming_check: { type: 'string', description: 'Could the fixed signal still be gamed or saturated? How did you try?' },
  },
  required: ['loop', 'verdict', 'attacks_attempted', 'surviving_issues', 'gaming_check'],
}

const BRIEF_SCHEMA = {
  type: 'object',
  properties: {
    loop: { type: 'string' },
    recommendation: { type: 'string', description: 'One line. The single option you would pick.' },
    options: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          what_it_means: { type: 'string' },
          evidence_for: { type: 'array', items: { type: 'string' } },
          evidence_against: { type: 'array', items: { type: 'string' } },
          effort: { type: 'string' },
          risk: { type: 'string' },
        },
        required: ['name', 'what_it_means', 'evidence_for', 'evidence_against', 'effort', 'risk'],
      },
    },
    proposed_flywheel_entry: { type: 'string', description: 'The entry text Joe would paste into flywheel_queue.json if he ratifies — proposed only, the file is fenced' },
    what_this_unblocks: { type: 'array', items: { type: 'string' } },
  },
  required: ['loop', 'recommendation', 'options', 'proposed_flywheel_entry', 'what_this_unblocks'],
}

const REPORT_SCHEMA = {
  type: 'object',
  properties: {
    phase: { type: 'string' },
    bar_before: { type: 'string' },
    bar_after: { type: 'string' },
    p4_reason: { type: 'string', description: 'verify.py P4 reason line verbatim — it names whether the router signal carries an outcome' },
    rung_transitions: { type: 'array', items: { type: 'string' } },
    human_gates_now_open: { type: 'array', items: { type: 'string' }, description: 'Exactly what Joe must do next, one action per line' },
    warnings: { type: 'array', items: { type: 'string' } },
  },
  required: ['phase', 'bar_before', 'bar_after', 'p4_reason', 'rung_transitions', 'human_gates_now_open', 'warnings'],
}

// ───────────────────────────────────────────────────────────────────────────
// PHASE: SIGNAL — RL-2. Three dishonest signals, three parallel worktree lanes.
// No file conflicts (verified 2026-08-01): A1 -> python/synapse/routing/router.py,
// F -> shared/router.py only, E -> forge/engine/.
// ───────────────────────────────────────────────────────────────────────────
const SIGNAL_LANES = [
  {
    loop: 'A1',
    brief: `FIX LOOP A1 — the router reward signal is a constant. Three defects, all verified
at HEAD f427320 lineage; RE-CONFIRM each at your HEAD before touching anything:

  (1) _record_metric is declared (self, tier, latency_ms, success: bool = True) at
      python/synapse/routing/router.py:917 and NONE of its eight call sites passes
      success — :285 :448 :515 :554 :584 :706 :742 :819. Fix: pass the real outcome at
      every site (result.success where a RoutingResult exists).
  (2) _try_tier0 hardcodes RoutingResult(success=True) at ~:537 WITHOUT consulting the
      responses it just collected, which can carry success=False. Fix: success must
      describe what HAPPENED, not what was attempted (Law 3). Recommended semantic:
      all responses succeeded => True; any failure => False. If you choose differently,
      say why in design_decisions.
  (3) The no_tier_matched fallback (~:367-373) returns success=False and never calls
      _record_metric at all — genuine failures never enter the sample. Fix: record the
      failure. There is no tier object there; record under a reserved literal key
      (e.g. "no_tier") and confirm EpochAdapter.record tolerates it (it takes tier.value
      strings). A failure the sample cannot see is the root defect of this whole loop.

FIX ALL THREE OR NONE. Fixing only (1) leaves tier-0 lying and failures invisible.

SAFETY FACT that makes this landable now: nothing consumes the adapter's output —
TierThresholds.get() has zero non-test callers, so honest recording changes NO routing
decision today. Verify that fact yourself before relying on it; if you find a consumer,
STOP and report it as a blocker instead of landing the fix.

TESTS (RL-5 ratchet — the rung must be pinned or it is one refactor from regressing):
  - a failing command_fn drives the router; assert the adapter was told False (kills the
    P7b defect class).
  - tier-0 with a failing response; assert RoutingResult.success is False AND the adapter
    was told False (kills P7a).
  - a no-tier-matched input; assert the sample gained a failure record (kills P5).
  - success path still records True (paired positive control — without it the suite
    passes vacuously if recording stopped entirely).

REGISTRY (same commit — Hard Rule 6): update harness/rsi/REGISTRY.json A1: add "L1" to
rungs_proven with evidence citing your new call-site lines + tests; move blocked_at to
"L2"; rewrite blocker to the L2 truth (router has recorded ZERO production requests —
live_metrics total_requests=0 on 2026-08-01 — so honest recording now needs production
traffic to matter). Update CHAMPION.md scoreboard row + LOG.md row. Run
'python harness/rsi/verify.py' — it must read 9 PASS with P4's reason flipped to "now
carries an outcome ... registry agrees". If P4 is red, you missed Hard Rule 6.`,
  },
  {
    loop: 'F',
    brief: `FIX LOOP F — fast-path promotion is failure-blind. STATUS: carried claim, registry
says verification="unverified" — so your FIRST job is confirmation, and if the claim is
wrong you report that instead of fixing a phantom.

CLAIMED DEFECT: shared/router.py MOERouter.route() auto-promotes any fingerprint hit
FAST_PATH_PROMOTION_THRESHOLD (default 3, shared/constants.py) times into
_session_fast_paths (:80, :121, :153, :155, :205), stamped with CONSTANTS_HASH.
Frequency cannot represent failure: a fingerprint that fails every time is promoted
identically to one that always succeeds. Confirm: does ANY outcome signal reach route()
or the promotion block? Also confirm the live-path TieredRouter
(python/synapse/routing/router.py) has NO session fast paths (believed true — grep
returned nothing on 2026-08-01) so your fix stays panel-side only.

FIX DIRECTION (adjust to what you find): gate promotion on outcome, not merely count.
Smallest honest design: add MOERouter.record_outcome(fingerprint, success) alongside the
existing external learn_fast_path() API; promotion requires threshold hits AND no
recorded failures (or a majority-success rule — justify your choice in design_decisions).
If no outcome signal can reach the panel layer at all, the honest fix is to DEMOTE
auto-promotion to advisory (log the candidate, promote nothing) and say so — a promotion
nothing can falsify is the defect, and removing it is a valid fix.

DO NOT persist _session_fast_paths to disk. That is the exact hazard the registry warns
about: persisting a failure-blind table makes it permanent. Persistence (L4) comes only
after honesty (L1) — the ladder order is the whole point of this harness.

TESTS: failing fingerprint never promotes; succeeding fingerprint still promotes at
threshold; CONSTANTS_HASH invalidation still works; panel tool_filter/routing_log
consumers unaffected (they read this router — run their tests).

REGISTRY (same commit): F verification -> "verified-at-head", add L1 to rungs_proven
with evidence IF your fix makes the signal honest; blocked_at -> "L2". CHAMPION + LOG
rows. If you instead REFUTED the claim, correct the registry to say what is actually
true — a refutation is a first-class result.`,
  },
  {
    loop: 'E',
    brief: `FIX LOOP E — the FORGE build loop authors its own success. CONFIRMED at HEAD
2026-08-01, exact lines:

  forge/engine/orchestrator.py:156  fixes_applied = 0
  forge/engine/orchestrator.py:177  fixes_applied += 1  # Optimistic — verification step catches failures
  forge/engine/orchestrator.py:214  fixes_validated=0,  # Set after verification phase
  forge/engine/metrics.py:44,:86,:166-167  (the fields + aggregation)
  forge/engine/reporter.py:65  renders "Validated: {metrics.fixes_validated}" — a
  hardcoded zero DISPLAYED TO A HUMAN as though it were a measurement.

RE-CONFIRM these lines at your HEAD first (the file may have moved since).

YOUR FIRST QUESTION shapes the whole fix: does a verification phase actually EXIST in
forge/engine (the :214 comment claims one sets the value "after")? Read the full
orchestrator flow before writing a line.
  - If it exists and its result is reachable: wire the REAL count into fixes_validated,
    and make fixes_applied count only fixes that actually applied (drop the optimism at
    :177 — count on confirmed application, not on attempt).
  - If it does not exist or cannot be reached: make the reporting HONEST instead of
    fabricating a validator — fixes_validated becomes None/"unvalidated", reporter.py
    renders "unvalidated" (never 0 pretending to be a measurement), and metrics
    aggregation tolerates the sentinel. A missing measurement stated plainly beats an
    invented number — that is Law 2 and it is also this repo's README convention.

TESTS: reporter never renders a numeric validated-count unless a real validation
produced it; applied-count does not increment on a failed application; aggregation
handles the sentinel.

REGISTRY (same commit): E gains L1 evidence IF the signal is now honest (either
direction — a real count or an honest "unvalidated" both satisfy L1, because L1 asks
whether the signal CAN represent failure, and "unvalidated" represents it truthfully);
blocked_at -> "L2". CHAMPION + LOG rows.`,
  },
]

const signalLane = (lane) =>
  agent(`${GROUND}

You are the FORGE for one lane of the RSI closure relay, phase SIGNAL (PLAN line RL-2).
You are in an ISOLATED WORKTREE — work only there. One atomic commit:
'fix(rsi): <loop> honest signal — <what>' via git commit -F. NO push. NO merge. Leave the
branch in place and report its absolute worktree path + SHA so the crucible can attack it
and Joe can merge it.

${lane.brief}

Sequence: confirm defect at HEAD -> measure suite baseline in your worktree -> implement
-> add the pinning tests -> re-run the targeted tests AND the full suite -> update
REGISTRY/CHAMPION/LOG in the same commit -> run 'python harness/rsi/verify.py' and record
its P4 line -> commit -> report. If ANY step refutes the premise, stop, report honestly
with evidence, land nothing. An honest refusal beats a plausible fix.`,
    { label: `signal:${lane.loop}`, phase: 'Signal', agentType: 'general-purpose', isolation: 'worktree', effort: 'high', schema: FIX_SCHEMA })

const attackLane = (fix, lane) =>
  fix == null
    ? Promise.resolve(null)
    : agent(`${GROUND}

You are the CRUCIBLE attacking a just-landed signal fix for RSI loop ${lane.loop}. You
did not write it; you are motivated to break it. The forge reported:
${JSON.stringify(fix)}

Attack surface (minimum — add your own):
  1. HONESTY: drive the fixed code with real failures. Does the recorded signal actually
     go False, or did the fix move the hardcode somewhere subtler? Re-run the forge's
     tests AND write one probe the forge did not anticipate.
  2. SATURATION/GAMING: can the signal still pin at a constant under realistic traffic
     (e.g. failures recorded but drowned, sentinel treated as success downstream)?
  3. REGRESSION: run the relevant existing test files in the worktree. Did the fix change
     behaviour something else pinned?
  4. REGISTRY TRUTH: does the registry claim in the commit match the code exactly? A
     rung claimed without the code to back it is a BROKEN verdict even if the code is fine.
  5. Run 'python harness/rsi/verify.py' in the worktree — 9 PASS required; quote P4.

Work read-only against the forge's worktree path. Verdict BROKEN requires a reproducible
demonstration, not an aesthetic objection. SOUND requires that your attacks actually ran.`,
      { label: `attack:${lane.loop}`, phase: 'Attack', agentType: 'crucible', effort: 'xhigh', schema: ATTACK_SCHEMA })

// ───────────────────────────────────────────────────────────────────────────
// PHASE: DECIDE — RL-3. Evidence briefs. Agents recommend; only Joe decides.
// ───────────────────────────────────────────────────────────────────────────
const DECIDE_LANES = [
  {
    loop: 'A2',
    q: `WIRE OR DELETE OutcomeTracker (python/synapse/agent/learning.py). Facts to verify
then build on: AgentExecutor has ZERO non-test constructions — the only occurrence is
inside the module docstring at python/synapse/agent/__init__.py:12; OutcomeTracker has
never recorded a single outcome; success_rate() returns a hard 0.0 on empty history
(learning.py:191-192). Investigate BOTH directions honestly: (WIRE) what live call path
would construct AgentExecutor, what would its reward signal feed, does anything need
per-agent outcome history that render-learning (loop R) and Moneta do not already cover?
(DELETE) what imports/exports/tests die, what capability is genuinely lost? Weigh against
the harness-updating≠harness-benefit lens: a second unfed recorder is bookkeeping, not
benefit.`,
  },
  {
    loop: 'S',
    q: `WIRE OR DELETE the science deposit seam. Facts to verify then build on: the seam is
fully built (python/synapse/science/deposit.py — LedgerDeposit, "the deposit_fn seam");
Registry accepts deposit_fn (registry.py:26, default None at :28); the ONLY construction
passing a real deposit_fn is at deposit.py:58 INSIDE the LedgerDeposit docstring's
Usage:: block. Same defect class as A2 — second docstring-only construction in this
registry. Investigate: (WIRE) where does run_apex_verify (or whatever the live probe
entry is now) construct Registry, what is the one-line change, where do deposits land
(note: agent.usd provenance writers are DORMANT per CLAUDE.md status table — does the
Ledger target actually accept writes today?); (DELETE) is the science registry itself
still driven by anything?`,
  },
  {
    loop: 'C',
    q: `DECIDE THE MEMORY SUBSTRATE — the ground every other loop persists onto. Facts to
verify then build on (all from synapse_doctor 2026-08-01 + store code): Moneta imports
(moneta_available()=True) but SYNAPSE_MEMORY_BACKEND defaults to "jsonl" at store.py:810
and is UNSET on this machine; .synapse/config.yaml:17 says memory_backend:"flat" — a key
the store selector NEVER reads (do not cite it as configuration); the MonetaMemory USD
schema is NOT registered (FindConcretePrimDefinition returned None; PXR_PLUGINPATH_NAME
unset; nothing in packages/synapse.json sets it — and registration is process-global so
it must be in the Houdini package env, not runtime); SYNAPSE's Moneta store is
MockUsdTarget-backed (moneta_store.from_storage_dir builds MonetaConfig WITHOUT
use_real_usd=True) so it authors NO USD AT ALL; a "shadow" backend value exists
(SYNAPSE_MEMORY_BACKEND=moneta|shadow per the integration notes — verify in code).
Options to develop: (a) staged flip — shadow mode first, schema registration in the
package env, use_real_usd decision, then default flip; (b) stay jsonl and formally
retire the Moneta-is-the-substrate claim (which then argues A3's converter stays); (c)
full flip now. For each: what breaks, what migrates existing data, rollback lever
(env flag back), and which OTHER loops' persistence story it changes (R, F-L4, A3, O).
This is the sequencing keystone — say explicitly what order the other decisions should
land relative to this one.`,
  },
]

const decideBrief = (lane) =>
  agent(`${GROUND}

You are an EVIDENCE-BRIEF writer for the RSI closure relay, phase DECIDE (PLAN line
RL-3). This is a DECISION for Joe, not an engineering task: you investigate, you weigh,
you recommend ONE option — you change NOTHING. Read-only throughout (Bash for git/grep/
python -c introspection only; no file writes, no env changes, no live mutations).

${lane.q}

Every factual claim in the brief carries file:line or command output. Where the two
prior efforts (docs/rsi/ June, RSI_SURFACE_AUDIT July) disagree with what you find at
HEAD, HEAD wins and you say so. End with the proposed_flywheel_entry Joe would ratify —
proposal text only; the queue file is fenced.`,
    { label: `brief:${lane.loop}`, phase: 'Decide', agentType: 'general-purpose', effort: 'high', schema: BRIEF_SCHEMA })

// ───────────────────────────────────────────────────────────────────────────
// PHASE: CLOSE — R's L2 evidence, A3's disposition. Only runs usefully AFTER
// the DECIDE ratifications; the legs check gate state and degrade honestly.
// ───────────────────────────────────────────────────────────────────────────
const closeR = () =>
  agent(`${GROUND}

You are the R-CLOSURE leg. Loop R (render-farm learning) sits at L0+L1 — the ONLY loop
with an honest signal (render_farm.py:249 success=True / :280 success=False). It is
blocked at L2 REACHABLE solely for want of PRODUCTION evidence: the mechanism has never
demonstrably fired outside eval conditions (live_metrics showed total_commands=0).

liveRender flag for this run: ${LIVE_RENDER}.

IF liveRender is FALSE (the default): DO NOT render anything. Produce the probe PACKAGE
for a Joe-supervised run instead: (1) a minimal scene recipe + the exact bounded-render
invocation ('render' command routes to _handle_render_bounded — poll-token flow,
wait_budget_s, tiny resolution 64x64, and a deliberately-failing validation setting so
BOTH record_fix_outcome branches fire); (2) the exact memory-store query that proves the
FEEDBACK records landed, with the pytest-pollution fingerprint check (Hard Rule 5); (3)
what to record in REGISTRY evidence for L2 (and L3/L4 — the eval script
tests/rsi/eval_line_r_closure.py already demonstrates those properties under eval
conditions; run it directly with 'python', NOT pytest — its eval_ prefix collects zero
tests, a trap already burned once). Write the package to harness/rsi/briefs/R-l2-probe-${DATE}.md.

IF liveRender is TRUE: Joe has explicitly authorized ONE bounded live probe. Ping first
(mcp__synapse__synapse_ping via ToolSearch). Use ONLY the bounded render path with
wait_budget_s=0 + polling, 64x64, on a throwaway scene node you create and then leave
for the artist's Ctrl+Z (never delete). If ANYTHING stalls — ping latency spikes, poll
token errors — STOP immediately and report; do not retry a render. This machine's
history: renders have hard-frozen Houdini. Capture the memory records, then write the
L2 evidence into the same briefs file. You still do NOT update REGISTRY.json — report
the evidence; the orchestrator applies registry changes after Joe reviews.`,
    { label: 'close:R', phase: 'Close', agentType: 'general-purpose', effort: 'high', schema: BRIEF_SCHEMA })

const closeA3 = () =>
  agent(`${GROUND}

You are the A3-DISPOSITION leg. Loop A3 (memory evolution charmander/charmeleon) sits at
L2 — the highest rung in the registry. CLOSED (RETIREMENT agent, refactor/memory-v51-substrates,
${DATE}): C ratified toward Moneta, so the manual/human-token-gated evolution path was retired
in favor of THE LOOP v5.1's decay-driven lifecycle. Removed: the synapse_evolve_memory MCP tool
(mcp/_tool_registry.py), the _handle_evolve_memory / _handle_evolve_consolidate handlers
(server/handlers_memory.py), and apply_consolidation's approval_token string-gate
(memory/consolidation.py) — deleted outright once its only caller (_handle_evolve_consolidate)
was gone, rather than left reachable-but-ungated. The sanctioned mutator is the decay-driven
_handle_sleep_pass / store.run_sleep_pass() path, which carries a real consent gate via the
execution bridge, not a copy-pasted approval string. plan_consolidation / is_protected (the
pure, read-only preview half) were never the interactive part and were left in place.

FIRST: confirm the registry entry still carries the A3 id with this disposition (P9 requires all
nine ids present) — read harness/rsi/REGISTRY.json and harness/state/flywheel_queue.json
(READ ONLY). If the disposition field is missing or stale, write the update as a brief, not a
direct registry edit: harness/rsi/briefs/A3-disposition-${DATE}.md, with file:line evidence for
each removal above and confirmation that tests/test_w3_evolve_consolidation.py now guards the
retirement (TestEvolveConsolidationRetired) instead of testing the retired mechanism.
No code changes, no registry changes, no tool invocations that mutate memory.`,
    { label: 'close:A3', phase: 'Close', agentType: 'general-purpose', effort: 'high', schema: BRIEF_SCHEMA })

const auditO = () =>
  agent(`${GROUND}

You are the O-AUDIT stretch leg (only dispatched because includeO=true). Loop O
(section-16 observability) is blocked at L1: nobody has ever audited whether the
advisor's INPUTS can represent failure. The three inputs: (1)
LosslessExecutionBridge.operation_stats(), (2) MOERouter fingerprint counts — KNOWN
failure-blind pre-F-fix; if phase signal landed F, re-assess against the fixed code,
(3) LosslessEvolution EvolutionIntegrity failures. For EACH input: can it go "bad" when
reality goes bad? Trace the producer of every field the advisor reads
(shared/conductor_advisor.py) to its source. Output: per-input verdict HONEST /
FAILURE-BLIND / MIXED with file:line, and what O's registry entry should say. Read-only;
write nothing but your structured result.`,
    { label: 'audit:O', phase: 'Close', agentType: 'cartographer', effort: 'high', schema: BRIEF_SCHEMA })

// ───────────────────────────────────────────────────────────────────────────
// BAR — every phase ends by reading the bar and naming Joe's next actions.
// ───────────────────────────────────────────────────────────────────────────
const barReport = (phaseName, payload) =>
  agent(`${GROUND}

You are the BAR reporter closing phase ${phaseName} of the RSI closure relay. Phase
output (verbatim, from the other legs):
${JSON.stringify(payload)}

Do, in the MAIN repo tree (not a worktree):
  1. Run 'python harness/rsi/verify.py' — capture all 9 lines; quote P4's reason verbatim.
  2. Run 'python harness/progress.py --fast' — capture the board.
  3. Derive rung_transitions by diffing what the legs claim against harness/rsi/REGISTRY.json
     as it stands on THIS tree (unmerged worktree claims are PENDING-MERGE, not landed —
     say which).
  4. List human_gates_now_open as concrete actions: branches to merge (worktree path +
     SHA), flywheel entries to ratify (paste-ready text), flags to grant (liveRender),
     decisions to make. One action per line, no vagueness.
  5. Warnings: anything a leg reported as blocker/surviving_issue, plus any lane where
     the crucible said other than SOUND, plus the falsification watch — if this phase
     produced more bookkeeping than rung movement, SAY SO in warnings; two consecutive
     phases like that and the SPEC says stop.
Never mark anything done that is not observable in a file, a SHA, or a bar line.`,
    { label: `bar:${phaseName}`, phase: 'Bar', agentType: 'general-purpose', effort: 'high', schema: REPORT_SCHEMA })

// ───────────────────────────────────────────────────────────────────────────
// EXECUTION
// ───────────────────────────────────────────────────────────────────────────
if (PHASE === 'signal') {
  phase('Signal')
  log('RL-2: three dishonest signals, three parallel worktrees (no file overlap — verified).')
  const results = await pipeline(
    SIGNAL_LANES,
    lane => signalLane(lane),
    (fix, lane) => attackLane(fix, lane).then(atk => ({ lane: lane.loop, fix, attack: atk })),
  )
  phase('Bar')
  const report = await barReport('signal', results.filter(Boolean))
  return { phase: 'signal', lanes: results, report }
}

if (PHASE === 'decide') {
  phase('Decide')
  log('RL-3: three evidence briefs in parallel — agents recommend, Joe decides.')
  const briefs = (await parallel(DECIDE_LANES.map(l => () => decideBrief(l)))).filter(Boolean)
  // Barrier is correct here: the contradiction check needs ALL briefs (C's substrate
  // call changes what A2/S should recommend), and the scribe writes them as one set.
  const scribe = await agent(`${GROUND}

You are the SCRIBE + CONTRADICTION CHECK for phase DECIDE. The three briefs:
${JSON.stringify(briefs)}

  1. CROSS-CHECK: do the recommendations compose? (If C says "flip to Moneta" and A2
     says "wire OutcomeTracker onto jsonl", that is a contradiction — flag it and say
     which brief should bend.) Sequencing: C is the keystone; state the required order.
  2. WRITE each brief to harness/rsi/briefs/<loop>-decision-brief-${DATE}.md — complete,
     ADHD-friendly (short blocks, bold anchors, scannable), every number with its
     producer path, options table + ONE recommendation up top.
  3. Append one row to harness/rsi/LOG.md: phase DECIDE run, briefs written, gates open.
  4. Do NOT touch REGISTRY.json, CHAMPION.md, flywheel_queue.json, or DECISIONS.md.
Return the contradiction findings + the exact ratification actions for Joe.`,
    { label: 'scribe:decide', phase: 'Decide', agentType: 'general-purpose', effort: 'high', schema: REPORT_SCHEMA })
  return { phase: 'decide', briefs, scribe }
}

if (PHASE === 'close') {
  phase('Close')
  log(`Closure legs: R (liveRender=${LIVE_RENDER}), A3 disposition${INCLUDE_O ? ', O audit (stretch)' : ''}.`)
  const legs = [() => closeR(), () => closeA3()]
  if (INCLUDE_O) legs.push(() => auditO())
  const results = (await parallel(legs)).filter(Boolean)
  phase('Bar')
  const report = await barReport('close', results)
  return { phase: 'close', legs: results, report }
}

throw new Error(`Unknown phase ${JSON.stringify(PHASE)} — use "signal", "decide", or "close".`)
