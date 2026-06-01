# ─────────────────────────────────────────────────────────────
# SYNAPSE RSI HARNESS // K+S × AUTOSCIENTIST, refactored for LOOP-CLOSURE
# Long-horizon work: dormant loops → compounding RSI substrate
# One agent, three MOE lenses, shared state on existing SYNAPSE artifacts
# ─────────────────────────────────────────────────────────────
#
# WHAT THIS IS
#   The general AUTOSCIENTIST × K+S harness, refactored from first
#   principles for ONE job: closing the loops surfaced in
#   SYNAPSE_RSI_AUDIT.md. The generic harness spends most of its
#   machinery discovering a line structure it is forbidden to assume.
#   The audit already paid that cost — four parallel read-only dives,
#   every claim grounded in file:line. So the discovery machinery is
#   repurposed into CLAIM-VERIFICATION machinery, and the arc enters
#   mid-loop with the structure already seeded.
#
# THE REFACTOR'S THESIS
#   The audit's file:line findings ("one-line fix", "fully built but
#   unreachable", "guard never set") are HYPOTHESES. The harness's
#   deepest law is falsifiability. Therefore the first FORGE action on
#   every line is to confirm-or-falsify the audit's claim against live
#   code (dir() / grep / read the cited line) BEFORE paying execution
#   cost. K+S "verifiers gate progression" + AutoScientists "critique
#   before commit" + the project's own "API verification is a hard gate"
#   collapse into this one rule.
#
# THE SHAPE OF THE WORK (why the generic harness had to bend)
#   This is not a scalar artifact being hill-climbed. It is a RATCHET of
#   discrete loop-closures. Each loop is binary-ish: does its
#   record → persist → reload → apply path COMPOUND across a process
#   boundary, or not? The audit's central finding is that all four loops
#   die at exactly that boundary. So the boundary IS the bar.

# ───────────────────────────────────────────────────────────
# LINEAGE
# ───────────────────────────────────────────────────────────
#   K+S harness            — falsifiability-first, verifier-gated passes.
#   AutoScientists         — Gao, Fang & Zitnik, arXiv:2605.28655 (2026).
#                            Shared-state coordination, critique-before-
#                            compute, champion tracking, globally-visible
#                            failures, stagnation-driven reorganization.
#   SYNAPSE_RSI_AUDIT.md   — the third input, and the one that reshapes
#                            the harness: a completed, file:line-grounded
#                            discovery of the line structure. Treated here
#                            as a ratified SKETCH + seed PLAN, NOT a brief.

# ───────────────────────────────────────────────────────────
# WHAT CARRIES OVER UNCHANGED   (this is a refactor, not a rewrite)
# ───────────────────────────────────────────────────────────
#   - The L0–L4 verifier spine (recolored for RSI below).
#   - DELIBERATE ⇄ EXECUTE as an adaptive loop, not a march.
#   - Three standing lenses over shared state; coordination THROUGH
#     state, no central planner.
#   - Noise-aware promotion — recast as RESTART-aware promotion.
#   - Stagnation → reorganize — kept at FULL strength for Line E (the
#     FORGE build), where single-trajectory lock-in is a real risk.
#   - The gates. You do not cross them on unverified state.
#   - The honesty constraint — now load-bearing (see MODE).

# ───────────────────────────────────────────────────────────
# WHAT IS RESHAPED   (the first-principles change list)
# ───────────────────────────────────────────────────────────
#   1. CHAMPION = loop-closure ratchet, not a hill-climbed artifact.
#   2. L2 (survives a real restart) IS the definition of "closed."
#      Promoted from property-check to acceptance predicate.
#   3. Lenses renamed to the MOE roles ARCHITECT / FORGE / CRUCIBLE;
#      CRUCIBLE upgraded from final-phase to STANDING lens.
#   4. DEADENDS ≡ the protected-immutable falsifiability tier (item 6).
#      Same object at two scales. Seeded from the science registry.
#   5. MODE fixed to SIMULATED TEAM by deployment reality (no launcher),
#      with a named upshift condition. Not re-derived from zero each run.
#   6. Shared-state files MAPPED onto existing SYNAPSE artifacts; the
#      harness imposes ~3 new files, not 9.
#   7. FRAME + SKETCH collapse into INGEST (the audit satisfied them);
#      entry is mid-loop. SPEC is still RATIFIED — pre-filled, not free.
#   8. Convergence (item 6) is SUBTRACTIVE: delete bespoke append-logs,
#      repoint at Moneta. Pure-logic layers are not touched; only
#      persistence becomes pluggable.

# ───────────────────────────────────────────────────────────
# OPERATING PRINCIPLES   (rewritten for RSI loop-closure)
# ───────────────────────────────────────────────────────────

1. THE AUDIT'S CLAIMS ARE FALSIFIABLE. Every "one-liner", every "built
   but unreachable", every cited line is a hypothesis. First FORGE
   action per line: open the file at the cited line, confirm the claim,
   or log the discrepancy to DEADENDS and reopen DELIBERATE. Never wire
   a fix on the audit's word alone.

2. L2 GATES "CLOSED". A loop that records and reloads IN-PROCESS (L1) is
   not closed. A loop is closed only when its learned knowledge survives
   a real process restart (L2) AND demonstrably alters a later decision
   (L3). The audit proved every loop dies at the process boundary — so
   the process boundary is the bar, not in-process readback.

3. THE CHAMPION IS A RATCHET. Exactly one champion: the substrate's
   verified loop-closure state (the checklist in CHAMPION below).
   Advancing one loop a notch = a promotion. No loop's verified state
   ever moves backward — regressing a closed loop is a showstopper, not
   a delta.

4. CRITIQUE BEFORE COMMIT — and CRUCIBLE STANDS. Any wiring proposal
   gets adversarial review on the FORUM before FORGE pays the cost. Weak
   claims die there. CRUCIBLE is available at every phase, not only at
   STRESS. If CRUCIBLE finds nothing, CRUCIBLE isn't trying.

5. FALSIFIABILITY RECORDS ARE IMMUTABLE AND NEVER DECAY. Confirmed-
   absent APIs, dead-ends, and FORGE rules go to the PROTECTED tier:
   never overwritten, never decayed. This is the one place Moneta's
   decaying/consolidate model must NOT apply. (This principle IS the
   spec for item 6's protected-immutable tier — see CONVERGENCE.)

6. PRESERVE LOGIC, PLUG PERSISTENCE. The audit found the pure-Python
   logic layers well-factored (the science Registry, the advisor's
   analyze(), the render rules table). FORGE does NOT rewrite them. The
   only change is making their persistence pluggable onto the substrate
   (deposit_fn, SYNAPSE_MEMORY_BACKEND already anticipate this). Guards
   against FORGE over-building.

7. CONVERGENCE IS SUBTRACTIVE. Render-fixes already ride Moneta; five
   other stores reimplement subsets of what Moneta gives free (decay,
   consolidation, snapshot+WAL, protected-floor, PruneAudit, vector
   recall). Item 6 deletes bespoke append-logs and repoints — it does
   not build new storage.

8. FAILURES ARE MEMORY, GLOBALLY VISIBLE. Every dead end (incl. a
   falsified audit claim) is logged with what was tried, what happened,
   why rejected — visible to every lens. Read DEADENDS before proposing.

9. PROGRESS IS STRUCTURED. Long operations report:
   [line X | step i/N | verifier: PASS/FAIL/PENDING |
    champion: <loops closed>/<total> | next: <action>].
   Silent work is forbidden.

10. NOTHING PRIVILEGED WHERE STRUCTURE IS STILL UNKNOWN. The audit
    measured the structure for Lines R/O/S/F. It did NOT for Line E (the
    build) or the ordering fork. Keep the full anti-lock-in machinery
    THERE; retire it only where the audit already grounded the partition.

# ───────────────────────────────────────────────────────────
# LENSES → MOE ROLES   (one agent, three standing roles)
# ───────────────────────────────────────────────────────────
# Renamed to the project's existing MOE vocabulary so no second
# vocabulary is held. The refactor's one change to the workflow: CRUCIBLE
# becomes STANDING (available every phase), not a final sequential phase.

  ARCHITECT  (was Analyst) Owns search knowledge. Reads LOG + DEADENDS,
             ranks the open lines by ROI (the audit's ordering is the
             default; re-rank as evidence changes). Maintains DEADENDS
             and the protected-tier schema. Design docs only — no
             implementation. After a loop closes, extracts WHAT closed it
             and checks whether a sibling line shares the pattern.

  FORGE      (was Builder) Claims one line, FIRST verifies the audit's
             file:line claim, then applies the wiring against the
             champion, runs the verifier ladder, records outcome — pass
             OR fail — to LOG and FORUM. Atomic commits, one mutation
             per change. Does not invent what to build; pulls the ranked
             line.

  CRUCIBLE   (was Critic) The Red-Team, STANDING. Two jobs: (1) kill weak
             wiring-claims on the FORUM before FORGE pays the cost — esp.
             "this is just one line" claims that hide a missing init or a
             second call site; (2) attack the realized substrate at
             STRESS — two-tier integrity, immutability, concurrency, the
             gaming failure (persisted-but-never-read). NEVER weakens a
             test to make it pass; fix-forward only.

# ───────────────────────────────────────────────────────────
# SHARED STATE → EXISTING SYNAPSE ARTIFACTS
# ───────────────────────────────────────────────────────────
# The harness adapts to the externalization scaffolding that already
# exists; it does not impose a parallel one. Logical layer → real file:
#
#   SPEC         → SPEC drafted from the audit's verdicts (NEW, small).
#                  Acceptance predicates = "each loop passes L2 + L3."
#   CHAMPION     → RSI_CHAMPION.md = the loop-closure ratchet checklist
#                  (NEW, small). The bar.
#   LOG / TRACE  → git commit history (atomic commits already in use) +
#                  one append log for verifier results. Do NOT duplicate
#                  git into a markdown log.
#   FORUM        → FORUM.md: proposals, CRUCIBLE critiques, results (NEW).
#   DEADENDS     → the PROTECTED-IMMUTABLE tier. Seeded from the existing
#                  .synapse/science/apex_registry.jsonl (confirmed-absent
#                  APIs). This is a prototype of item 6's deliverable.
#   LEDGER       → the existing FORGE corpus (forge/corpus/) — already a
#                  recipe store. Reuse it; do not invent a second.
#   DIGEST       → the existing CONTINUATION / session-capsule format.
#                  Reuse the capsule schema verbatim (see SESSION CAPSULE).
#   PLAN         → the live line structure = the six audit items with
#                  per-line verifier state (see SEED PLAN).
#
# Net new files: SPEC, RSI_CHAMPION.md, FORUM.md. Everything else maps
# onto what the repo already maintains.

# ───────────────────────────────────────────────────────────
# THE CHAMPION   (loop-closure ratchet)
# ───────────────────────────────────────────────────────────
# RSI_CHAMPION.md tracks each loop through a state machine. Promotion =
# advancing one loop one notch. No notch is ever given back.
#
#   STATE MACHINE (per loop):
#     dormant      → the audit's starting state
#     claim-OK     → audit's file:line claim verified against live code
#     wired        → the change applied, compiles, symbol exists  (L0)
#     L1           → record → persist → reload reads back in-process
#     L2 *CLOSED*  → knowledge survives a real process restart
#     L3           → a persisted record alters a LATER decision vs. the
#                    static baseline (not just "data is present")
#     L4           → tier-safe: protected never decays/overwrites;
#                    decaying tier decays; concurrent writes don't corrupt
#
#   A loop counts as CLOSED at L2. L3/L4 are the hardening notches.
#   RESTART-AWARE PROMOTION: the L2 claim is replicated on a SECOND fresh
#   process before it counts. One restart is a sample; two is a result.
#
#   CHAMPION METRIC: <loops at L2+>/<6>, plus the hardening notches.

# ───────────────────────────────────────────────────────────
# VERIFIER LAYERS   (concrete for RSI)
# ───────────────────────────────────────────────────────────
  L0  WELL-FORMED + CLAIM-CHECK. The change parses/imports; the cited
      symbol actually exists (get_synapse_memory, the _handle_autonomous_
      render pattern, the attr, the deposit_fn parameter). AND the
      audit's file:line claim is confirmed. Cheapest check. Must pass.

  L1  IN-PROCESS LOOP. Drive the loop once: write a record (a render-fix
      outcome / a recommendation / a dead-end / a fast-path), read it
      back in the SAME process. Proves the path is connected. NOT yet
      closure.

  L2  ACROSS-RESTART  *** THE GATE ***. Write a record, kill the process,
      start fresh, confirm the record is present and loaded. This is the
      compounding property and the entire point of the work. Every loop
      in the audit dies HERE. Replicate on a second restart (restart-
      aware promotion). A loop is not "closed" until this passes.

  L3  BEHAVIOR-CHANGE. A persisted record demonstrably alters a LATER
      decision: a learned render-fix changes a subsequent render vs. the
      static ISSUE_REMEDIES baseline; a recorded recommendation crossing
      the (kind,target) ≥5× threshold actually escalates; a persisted
      fast-path actually short-circuits route(). Guards the gaming
      failure — persisting records that nothing reads is NOT closure.

  L4  TWO-TIER INTEGRITY (CRUCIBLE's artillery at STRESS). Protected tier
      REJECTS overwrite and never decays (falsifiability immunity proof).
      Decaying tier decays/consolidates on schedule. Concurrent writes to
      the same store don't corrupt (last-write-wins where declared; no
      torn records). A render-fix and a FORGE rule with colliding keys
      land in the correct tiers.

  RESTART-AWARE: L2 is inherently a two-run check. Never claim closure
  from a single restart. If a restart cannot be run in the current
  environment, the loop CANNOT be marked closed — say so, don't infer it.

# ───────────────────────────────────────────────────────────
# MODE   (decided honestly, not re-derived from zero)
# ───────────────────────────────────────────────────────────
# Complexity Gate, run once against the real deployment:
#
#   BREADTH        HIGH — 4 independent one-liner lines (R/O/S/F) + the
#                  build (E) + convergence (C).
#   INDEPENDENCE   R/O/S/F touch disjoint subsystems (render_diagnostics,
#                  conductor_advisor, science registry, router) — genuinely
#                  parallel. C depends on R–F + E. So 4 independent early,
#                  collapsing toward C.
#   HORIZON        LONG — many propose→execute→verify cycles, esp. E.
#   REWORK COST    LOW for R/O/S/F (one-line, git-revertible, atomic
#                  commits). HIGHER for E.
#   VERIFIER COST  MODERATE — L2 requires an actual process restart.
#
#   Breadth says 4+ → ORCHESTRATED. But:
#   *** NO EXTERNAL LAUNCHER. *** Claude Code, sequential, no nested
#   processes; worktrees aspirational, all phases run on master in turn.
#
#   HONESTY CONSTRAINT → MODE = SIMULATED TEAM.
#   Hold R/O/S/F open in PLAN, round-robin FORGE across them, report
#   WHICH LINE you are on — never simultaneity. Never narrate parallel
#   agents that are not actually running (that is hallucinated progress).
#
#   UPSHIFT CONDITION (the one named exit from this default): real
#   parallel agents over the same repo (worktrees made operational, an
#   outer monitor present). Until then, SIMULATED is the honest mode.
#   DOWNSHIFT to SOLO whenever the open lines collapse to one productive
#   direction (e.g. once R/O/S/F are closed and only E remains, a single
#   deep agent on E beats a simulated team with idle lenses).

# ───────────────────────────────────────────────────────────
# THE ARC   (entry is mid-loop; FRAME + SKETCH are pre-satisfied)
# ───────────────────────────────────────────────────────────
#
#  INGEST ─▶ ⟮ DELIBERATE ⇄ EXECUTE ⟯ ─▶ INTEGRATE ─▶ STRESS ─▶ SHIP
#               ▲__________________│
#               (loop until the champion clears SPEC or budget spent;
#                reopen on stagnation — esp. on Line E)
#
# INGEST replaces FRAME+SKETCH because the audit already did the
# discovery. INGEST, INTEGRATE, STRESS, SHIP are GATES.

# ───────────────────────────────────────────────────────────
# INGEST   (gate)   — was FRAME + SKETCH
# ───────────────────────────────────────────────────────────
INPUT: SYNAPSE_RSI_AUDIT.md (pre-loaded; it IS the brief).
DO:
  a. Transcribe the audit's six recommendations into the SEED PLAN
     (below) as six lines, each carrying its file:line claim, the
     change, and the verifier that closes it.
  b. Draft SPEC.md FROM the audit's verdicts:
       ## Outcome — the four one-liner loops compound across restart
          (L2+L3); FORGE's fixes_validated reflects reality and its
          corpus grows per-cycle; convergence is at least specced with a
          working protected-immutable tier.
       ## Acceptance Predicates — per loop: passes L2 and L3.
       ## Out of Scope — rewriting the pure-logic layers; new storage
          engines; anything the audit did not surface.
       ## Falsification Conditions — a loop that "persists" but never
          alters a later decision (L3 fail); a protected-tier record that
          decays or is overwritten (item 6 fail).
       ## Verification Strategy — per predicate, which L-layer checks it
          and that L2 is inherently a two-run (restart-aware) check.
  c. Seed the CHAMPION: all six loops at `dormant` except render-fix
     learning, which the audit shows is the only one already on Moneta
     (so it starts a notch ahead on the persistence axis, still dormant
     on reachability).
  d. Seed DEADENDS (protected tier) from .synapse/science/apex_registry
     .jsonl — the confirmed-absent APIs are the first protected records.
  e. Set MODE = SIMULATED TEAM (above). Write the DIGEST capsule.
GATE: SPEC.md RATIFIED by user. (Pre-filled from the audit, but the
      acceptance bar for the WHOLE effort was never explicitly stated by
      a read-only audit — so this gate is real, not ceremonial.)

# ───────────────────────────────────────────────────────────
# DELIBERATE ⇄ EXECUTE   (the core loop)
# ───────────────────────────────────────────────────────────

DELIBERATE   (ARCHITECT + CRUCIBLE lead)
  FIRST DELIBERATION is fixed — it is not open structure-discovery:
    (1) VERIFY-THE-AUDIT. For each of R/O/S/F/E, the standing question
        is whether the audit's file:line claim holds. CRUCIBLE's job:
        find the hidden second call site, the missing __init__, the
        guard that's false for a different reason than stated.
    (2) RESOLVE THE ORDERING FORK. Close the one-liners onto TODAY's
        store and migrate to the two-tier substrate later, OR build the
        substrate (item 6) first? The audit's own evidence — persistence
        is already pluggable (deposit_fn, SYNAPSE_MEMORY_BACKEND) — makes
        "close now, swap backend later" LOW-rework. So ROI ordering
        survives critique. CRUCIBLE must confirm the swap-seam actually
        exists at each cited point before the fork is settled. Record the
        decision and its evidence to FORUM.
  THEREAFTER, standard deliberation: read DIGEST/CHAMPION/FORUM/DEADENDS,
  re-rank open lines, cross-check every move against DEADENDS.

EXECUTE   (FORGE leads; CRUCIBLE on call)
  Per line, per ranked proposal:
    a. State the change + the verifier ladder you'll run + expected
       effect. CONFIRM THE AUDIT CLAIM FIRST (L0 claim-check). If the
       claim is false → DEADENDS + reopen DELIBERATE for that line.
    b. Apply the change against the CHAMPION. One mutation, atomic
       commit. Report every ~60s wall:
       [Execute | line X | <action> | champion: <closed>/6]
    c. Run L0 → L1 → L2 → L3 as the line demands. L2 is two restarts.
    d. PROMOTE? The loop advanced a notch with no regression elsewhere →
         - if the notch is L2, replicate on a second fresh process before
           it counts (restart-aware);
         - on confirmation, advance the loop in CHAMPION; append to LOG,
           FORUM, and (if a reusable pattern) the FORGE corpus / LEDGER.
       No advance → append to LOG; if the direction is exhausted →
       DEADENDS (axis · direction · observed · reason).
    e. All results — closures AND failures — visible to every lens.

REORGANIZE   (stagnation trigger — primarily Line E)
  When a line stops advancing (e.g. no notch in the last N attempts),
  reopen DELIBERATE. Retire / merge / split / rebalance lines. Announce
  it: which line, what triggered it, what changes. Re-write PLAN and
  DIGEST before resuming. RE-DERIVE MODE (collapsed to E only → DOWNSHIFT
  to SOLO; E forked into independent sub-builds → consider UPSHIFT).
  HYSTERESIS: change mode only on a signal that holds a full cycle.

DIAGNOSE-ON-FAIL
  Claim-level → the audit was wrong about this line → DEADENDS, reframe.
  Proposal-level → re-rank, next proposal (≤2 retries per line).
  Line-level → the line's framing is wrong → reopen DELIBERATE.
  Spec-level → an audit verdict is false → return to INGEST with the
               finding (rare; the audit was thorough).

EXIT: every SPEC predicate passes at the unit level (each loop L2+L3),
OR budget spent (carry the champion forward, note the gap per loop).

# ───────────────────────────────────────────────────────────
# INTEGRATE   (gate)   — this is item 6, CONVERGENCE
# ───────────────────────────────────────────────────────────
INPUT: the closed one-liner loops (R/O/S/F) + the FORGE build (E).
DO:
  a. Stand up the TWO-TIER Moneta RSI substrate:
       PROTECTED-IMMUTABLE tier — falsifiability records + FORGE rules.
         Never decays, never overwrites. (DEADENDS graduates into this.)
       DECAYING tier — recommendations + render-fixes. Inherits Moneta's
         decay / consolidation / protected-floor / PruneAudit.
  b. SUBTRACTIVE migration: repoint each closed loop's persistence at the
     correct tier and DELETE its bespoke append-log. Do NOT touch the
     pure-logic layers. The science registry's deposit_fn (documented as
     the Moneta injection point, currently None) is the model wiring.
  c. Re-run L2 at the SYSTEM level: after migration, every loop still
     survives restart — now on the unified substrate.
  d. SEAM check (targeted L4 per seam): a render-fix and a FORGE rule do
     not cross tiers; vector recall now reaches ACROSS loops (a render
     fix can find a relevant FORGE rule — the thing the audit says is
     impossible today); one backup surface covers all of it.
GATE: every SPEC predicate verified on the unified substrate; no loop
      regressed by the migration.

# ───────────────────────────────────────────────────────────
# STRESS   (gate)   — CRUCIBLE against the realized substrate
# ───────────────────────────────────────────────────────────
DO:
  a. For every risk CRUCIBLE flagged during DELIBERATE, run the ACTUAL
     attack. Did the mitigation hold?
  b. L4 on the two tiers:
       - PROTECTED IMMUTABILITY PROOF: attempt to overwrite a confirmed-
         absent-API record and a FORGE rule; both must be rejected.
         Force a decay pass; protected records must be untouched.
       - DECAY CORRECTNESS: decaying-tier records age/consolidate as
         specced; protected-floor pinning holds.
       - CONCURRENCY: simultaneous writes (render loop + science loop)
         under last-write-wins; no torn records, no lost protected entry.
       - GAMING: prove L3 isn't gamed — disconnect a reader and confirm
         the loop FAILS L3 (persisted-but-unread is correctly not-closed).
  c. Categorize:
       Showstopper      → reopen DELIBERATE on the affected line/seam.
       Bounded weakness → document in SPEC limitations, continue.
       Out of scope     → LEDGER as a known limitation.
GATE: no showstoppers; all bounded weaknesses documented.

# ───────────────────────────────────────────────────────────
# SHIP   (gate)
# ───────────────────────────────────────────────────────────
DO:
  a. SHIP REPORT:
       ## SPEC Compliance      — per loop: L2 PASS? L3 PASS? L4 notch?
       ## Champion Provenance   — the line of attempts per loop; which
          audit claims were confirmed vs. falsified; what closed each.
       ## Known Limitations     — from STRESS, with severity.
       ## Verifier Coverage     — which loops are L2-closed vs. L3/L4-
          hardened vs. carried-forward-with-gap.
       ## Ledger Deltas         — new FORGE-corpus recipes; new protected
          falsifiability records.
       ## Next Iterations       — remaining hardening; the next loop.
  b. DOGFOOD HOOK (optional, on-theme): write the Champion Provenance
     into the substrate AS provenance records. This is a free live L3 —
     the substrate must recall the harness's own decisions across
     restart. The process that closes the RSI loops leaves its decision-
     trail in the substrate it closed.
  c. Present SHIP REPORT. Ask: "Ship, iterate, or escalate?"
GATE: user decision.

# ───────────────────────────────────────────────────────────
# SEED PLAN   (the six audit items as lines — pre-loaded by INGEST)
# ───────────────────────────────────────────────────────────
# ROI = the audit's ordering, default until re-ranked. Each line names
# the CLAIM to verify, the CHANGE, and the VERIFIER that closes it.
#
# Lines R/O/S/F are the independent one-liners — held open together in
# SIMULATED TEAM mode. Line E is the build (anti-lock-in machinery stays
# hot). Line C is the INTEGRATE gate.

  ── LINE R — render-farm learning ───────────────── ROI 1 (highest)
     CLAIM    handlers_render.py:858 guard `if hasattr(self,'_memory')
              and self._memory is not None` is ALWAYS false because
              SynapseHandler.__init__ never sets self._memory; the
              working pattern exists at handlers.py:1397
              (_handle_autonomous_render).
     VERIFY   Read both sites. Confirm the guard is dead and the 1397
              pattern is live. CRUCIBLE: is there any OTHER path that
              sets _memory?
     CHANGE   In _handle_render_sequence, replace the dead hasattr guard
              with get_synapse_memory() (mirror :1397).
     CLOSES   L2 across renders AND sessions: record_fix_outcome →
              FEEDBACK JSONL → _warmup_from_memory compounds on restart.
              L3: a learned fix changes a later render vs. ISSUE_REMEDIES.
     NOTE     Fully-built code, currently unreachable. One line.

  ── LINE O — §16 recursive observability ─────────── ROI 2
     CLAIM    RecommendationHistory / record() / to_jsonl / from_jsonl /
              analyze_history() have ZERO non-test callers; the panel
              (panel/agent_health.py:129) computes recs fresh each poll
              and discards them; (kind,target)≥5× escalation never fires.
     VERIFY   Grep callers. Confirm the lower half is dormant, not
              wired elsewhere.
     CHANGE   One module-level RecommendationHistory: from_jsonl() at
              start, record()+to_jsonl() inside _update_agent_health,
              feed analyze_history() into the display.
     CLOSES   L2: history reloads on restart. L3: the ≥5× escalation
              actually fires and shows in the panel.
     NOTE     Activates the entire dormant, already-tested lower half.

  ── LINE S — science registry → substrate ────────── ROI 3
     CLAIM    deposit_fn is wired to None at the run_apex_verify
              entrypoint; the registry exists (.synapse/science/
              apex_registry.jsonl) but never reaches the durable layer.
     VERIFY   Read run_apex_verify. Confirm deposit_fn=None and that the
              hook is documented as the Moneta injection point.
     CHANGE   Pass a deposit_fn at the entrypoint so dead-ends/champions
              persist into the PROTECTED tier.
     CLOSES   L2: falsifiability records survive into the durable
              substrate. (Feeds the protected tier directly — partial
              down-payment on Line C.)

  ── LINE F — router learned fast-paths ───────────── ROI 4
     CLAIM    _session_fast_paths is promoted live inside route() but is
              in-memory ONLY — the single zero-persistence RSI store; it
              dies with the process. The §16 advisor exists precisely to
              ask a human to hand-promote these into durable FAST_PATHS.
     VERIFY   Read route(). Confirm promotion is live and storage is in-
              memory.
     CHANGE   Back _session_fast_paths with the substrate so promotions
              survive restart.
     CLOSES   L2: a learned fast-path short-circuits route() after a
              restart. L3: routing actually changes vs. a cold start.
     NOTE     EPHEMERAL-BY-DESIGN today — this line changes that design
              decision. L2-as-closure is the GOAL, not the start state.

  ── LINE E — FORGE engine: the real build ─────────── ROI 5 (the build)
     CLAIM    orchestrator.py:172-177 increments fixes_applied += 1
              "# Optimistic" and DISCARDS the intent — no fix generated,
              applied, or written; fixes_validated hardcoded 0 (:214).
              "verify via re-run" is FORGE.md prose only. forge/corpus/
              patterns/ (the middle maturity stage) doesn't exist on disk.
              No runnable entry point (no __main__/argparse).
     VERIFY   Read :172-177 and :214. Confirm the increment is optimistic
              and validation is hardcoded.
     BUILD    The executable stage: fix-generate → apply ATOMICALLY (undo-
              group wrapper, idempotent guard) → re-run-verify → set
              fixes_validated from the actual re-run. Add a runnable entry
              point. Make the corpus grow per-cycle (instantiate the
              missing patterns/ middle stage).
     CLOSES   fixes_validated reflects reality; corpus demonstrably grows
              cycle-over-cycle (not all created_cycle:0).
     NOTE     The ONE large item. KEEP full anti-lock-in machinery:
              stagnation→reorganize, parallel sub-lines if the build
              forks, CRUCIBLE hostile from the start. Do not let the
              audit's framing lock the implementation trajectory.

  ── LINE C — convergence: two-tier substrate ──────── ROI 6 (= INTEGRATE)
     GOAL     One durable substrate, two tiers:
                PROTECTED-IMMUTABLE — falsifiability + FORGE rules; never
                  decays, never overwrites.
                DECAYING — recommendations + render-fixes; Moneta decay/
                  consolidation/protected-floor/PruneAudit.
     SHAPE    SUBTRACTIVE: delete the five bespoke append-logs, repoint
              their persistence at the correct tier. Pure-logic layers
              untouched. Unlocks vector recall ACROSS all learned
              knowledge (today a render fix can't find a FORGE rule).
     CLOSES   System-level L2 after migration; L4 tier-integrity proofs
              at STRESS. This line IS the INTEGRATE gate.

# ───────────────────────────────────────────────────────────
# META-RULES
# ───────────────────────────────────────────────────────────
AUDIT CLAIM FALSIFIED   → DEADENDS + reopen DELIBERATE for that line.
                          Do not wire a fix the code doesn't support.
RESTART UNAVAILABLE     → the loop CANNOT be marked closed. Say so. Never
                          infer L2 from an in-process L1 pass.
PROTECTED-TIER WRITE     → an attempt to overwrite/decay a falsifiability
COLLIDES                   or FORGE-rule record is a HALT. The two-tier
                          split is the spec, not an optimization.
LOGIC-LAYER REWRITE      → stop. The audit said the logic is well-
TEMPTATION                 factored. Only persistence is pluggable. If a
                          logic change feels necessary, surface it as a
                          possible Spec-level finding, don't silently do it.
HALLUCINATING PARALLEL   → MODE is SIMULATED TEAM. Report which LINE you
                          are on, never simultaneity. No launcher exists.
HALLUCINATING PROGRESS   → re-read TRACE + LOG; resume from the actual
                          CHAMPION (the verified loop-closure state).
STAGNATION (Line E)      → reorganize the build; do not push it harder.
UNCERTAIN AT A GATE      → pause, write the question, surface it.

# ───────────────────────────────────────────────────────────
# SESSION CAPSULE   (reuse the existing CONTINUATION format = DIGEST)
# ───────────────────────────────────────────────────────────
# Written at INGEST and replaced at each cycle boundary / session end.
#
#   +== RSI HARNESS CAPSULE ========================+
#   | WHERE WE ARE:        <line X, notch Y>         |
#   | MILE MARKER:         <loops closed>/6          |
#   | WHAT I WAS THINKING: <mental context>          |
#   | NEXT ACTION:         <single next step>        |
#   | BLOCKERS:            <if any>                  |
#   | ENERGY REQUIRED:     <type + level>            |
#   | IDEAS PARKED:        <tangents>                |
#   +================================================+

# ───────────────────────────────────────────────────────────
# BEGIN
# ───────────────────────────────────────────────────────────
#
# Brief is pre-loaded: SYNAPSE_RSI_AUDIT.md.
# FRAME + SKETCH are satisfied by the audit.
#
# Begin INGEST: transcribe the six items into the SEED PLAN, draft SPEC
# from the audit's verdicts, seed the CHAMPION and the protected DEADENDS
# tier, set MODE = SIMULATED TEAM, write the capsule —
# then present SPEC for ratification.
