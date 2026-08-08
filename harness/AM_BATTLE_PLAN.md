# BATTLE PLAN - FINISH WAVES - 2026-08-08

*Constructed by Fable 5 (recon + scaffold). Executes on Opus 4.8.
v5.43.0 is shipped; this board is finish-work. Nothing here is urgent.*

STATE   master 1f18ab46 · CI0 unmerged (+2, honest-green-with-exception)
        8 new legs on the manifest: VER1 STAT BASE WARN GUARD DOCS CLOCK M6
        4 ready · 4 held by rulings

---

## STEP 0 - RULINGS (you, ~25 min, no agents)

Rule from the two sheets that already exist:

    harness/NEXT_SESSION.md      R-CI0-1..5   (R-CI0-1 is the real one)
    harness/tidy/GATES.md        5 commits · 2 drops · legs flip ·
                                 gitignore · 2 prunes

Then flip what you ruled, in harness/legs.json:

    STAT   held -> ready   if R-CI0-5 = fix
    DOCS   held -> ready   if R-CI0-4 = direct the correction
    CLOCK  held -> ready   if R-CI0-3 = fix   (LEAVE retires it unrun)
    M6     held -> ready   after Step 1 merge AND the ruling slot in
                           harness/prompts/m6.md is checked (exact | aliases)

## STEP 1 - GATE C (you)

    $env:SYNAPSE_GATE_C=1
    git merge ci/ci0-honest-green
    git checkout master        # dispatch base until BASE lands

---
## STEP 2 - WAVE 0 · instrument + gaps  (REAL TERMINAL - hard constraint:
##          DC-headless agents stall with no session log. Never dispatch
##          agents through Desktop Commander.)

STAT and BASE edit harness/ files that relay-settings denies by omission -
run each in a CTO-session terminal, on Opus 4.8, reading its brief:

    claude --model claude-opus-4-8 --permission-mode acceptEdits
      > Read harness/prompts/stat.md in full and execute it end to end.
      > Read harness/prompts/base.md in full and execute it end to end.

VER1 is read-only and dispatches fine as-is:

    powershell -File harness\orchestrate.ps1        # picks up VER1 (ready)

Merge STAT + BASE to master when their receipts land (your gate).

## STEP 3 - WAVES 1-2 · via the patched orchestrator

After BASE is merged the orchestrator honors per-leg base + manifest
model (claude-opus-4-8) on every launch:

    powershell -File harness\orchestrate.ps1
    # dispatches: WARN GUARD, then DOCS CLOCK M6 as you flip them ready
    # (DOCS/CLOCK/M6 carry deps:["BASE"] - they wait for its receipt)

## METERS - what you watch, both worktree-honest after STAT

    python harness/progress.py --watch      # the all-harness board
    statusline                              # already wired in settings.json
    python harness/board.py --watch         # browser meter, no terminal:
                                            # open harness/notes/board.html

Meters render observed states and counts only. UNKNOWN renders as
UNKNOWN - never zero, never an estimate, meters included.

## STANDING RULES

    Gate C, merges, pushes, ratify flips - yours, never an agent's.
    held = held by RULING; the orchestrator never auto-dispatches it.
    Receipts land in harness/notes/receipts/<ID>.json - claims need paths.

## STILL YOURS, OUTSIDE THE BOARD

    ROPE L3-2 (video) · L3-5 (Apprentice) - GATE A human tasks
    MONETA P0-1..5 ratification · CLEAR L1 · PHANTOM SWEEP · RSI advances

## BURN ORDER - weekly-pool discipline (advisor pass 2026-08-08)

    Pool: shared weekly plan, reset last night. Opus legs draw it fastest.
    Throttle = the state field you already own: flip ready in PAIRS.

    free      STEP 0 rulings + Gate C          zero model tokens
    pair 1    WARN (1-line) + BASE (528-ln ps1)
    pair 2    STAT (340 ln)  + VER1 (read-only probe)
    pair 3    GUARD (474 ln + 1 test) + DOCS (216-ln html + 2 sentences)
    solo      CLOCK  - fenced to 2 subsystems; repo has 91 time.time()
              sites total, the fence IS the cost control
    solo      M6     - largest leg, last on purpose: if the pool tightens,
              deferring it is a decision, not a mid-leg strand

    Check the real gauge (/status) between pairs. Estimates are size
    classes from measured files; exact burn figures unavailable - watch
    the meter, not a guess.

## CLOSE PROTOCOL - standing, agreed 2026-08-08 14:15

    Constitution holds: merges and pushes are HUMAN; relayed approval is
    not consent (ratified 2026-08-01). Everything else is pre-approved.

    AUTO (Claude, when FID + PRST receipts land, no further asks):
      verify receipts -> read FRZ/PRST findings + drift notes
      reconcile per-branch commit state (FRZ closed with uncommitted work)
      write harness/notes/CLOSE_2026-08-08.ps1 - merges, twin discard,
        staged commits + drafted messages, ordered + commented
      stage main-tree scaffold (TIDY-style: add only, never commit)
      regenerate board - deliver teach-down + Operator's Card update

    HUMAN (one moment): read CLOSE_2026-08-08.ps1 top to bottom, paste it.
