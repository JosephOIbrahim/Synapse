# BATTLEPLAN — wave BP1 · operator's card

Sibling harness to AUTOREVISE / APEXFORGE, cloned from `harness/apexforge/` on 2026-08-31
(Fable 5 scaffolds, Opus 4.8 executes — the AM_BATTLE_PLAN precedent). Executes the AGENT
lane of `docs/BATTLEPLAN.md`. Own bus (`bus/bp1/`), own worktree prefix (`bp1-*`), own
branch family (`bp1/*`). Zero writable overlap with the memory board (`mem/*`), the loop
board (`harness/loop/`), reach, flow, or rope.

## What it is

Four legs, Opus 4.8, dispatched by `harness/orchestrate.ps1` into git worktrees, talking on
an append-only bus. Dependency gating is the dynamic workflow: HONESTY starts the moment
TRIAGE's receipt lands; CRUX starts when all three builders have receipts.

    BP1-TRIAGE   TRUTH  rw   Gate 0 hython half — four gates, bucket posted on the bus
    BP1-RAILS    BUILD  rw   budget cap + hard stop + spend ledger + execution seam
    BP1-HONESTY  BUILD  rw   recall-honesty contract + fix for TRIAGE's bucket   (deps: TRIAGE)
    BP1-CRUX     TRUST  ro   adversarial re-verification, verdict per leg        (deps: all)

## How to run it (real terminal, or DC via the detached arm — never foreground-dispatch agents from DC)

    1  ARM      powershell -NoProfile -ExecutionPolicy Bypass -File harness\battleplan\arm_bp1.ps1
                builds waves\bp1.live.json from bp1.rows.json, launches the orchestrator
                detached, writes harness\notes\h22\orchestrator-bp1.{pid,log,err}
    2  SEE      python harness\battleplan\dashboard_bp1.py
                terminal board every 10s + harness\battleplan\board.html (open it in a
                browser on the second monitor; it refreshes itself)
    3  STATUS   python harness\battleplan\status_bp1.py          one-pass, for a receipt
    4  BUS      python harness\battleplan\bus.py read bp1        what the team is saying
    5  WATCH    powershell -File harness\battleplan\watch_bp1.ps1   balloon when CRUX lands

Burn discipline (AM_BATTLE_PLAN §BURN ORDER): TRIAGE + RAILS dispatch as pair 1 on arm;
HONESTY and CRUX gate themselves. Check /status between pairs. Watch the meter, not a guess.

## What you'll see

Board: TRIAGE and RAILS go `ready → RUNNING` within a minute of arm; HONESTY stays
`blocked on TRIAGE` until a TRIAGE receipt exists in its worktree; CRUX stays blocked until
three receipts. Bus: a `claim` from each builder before it edits, a `finding` from TRIAGE
naming the bucket (`env|plugin|layer|recall|UNKNOWN`), `status release` lines at the end.
Receipts: `harness/notes/receipts/BP1-<LEG>.json` inside each worktree, committed as the
leg's closing commit. Done = four receipts, CRUX verdicts SOUND or SOUND-WITH-NITS.

## When it breaks

- Orchestrator `DEAD` on the board → read `orchestrator-bp1.err`; re-arm (arm kills a stale pid).
- A leg `branch, no worktree` → the orchestrator pruned it or a launch failed; log names it.
- TRIAGE reports G3/G4 `UNAVAILABLE` under hython → expected (headless Moneta is
  UNAVAILABLE by construction). The GUI half is your hands: paste
  `harness/battleplan/notes/probe_silent_recall.py` into the Houdini Python shell.
- HONESTY receipt `blocked` with `AMENDMENT_recall_honesty.md` → a goalpost needs a §4
  change; that is a ratification flip, your word. The leg stopped correctly.
- CRUX `BROKEN` on a leg → that leg does not ride. Nothing merges.

## Human words (per act, never banked)

merge `bp1/*` legs (after CRUX) · push · v5.57.0 tag · ratify the three contracts ·
the Tue 18:00 branch decision · anything in `harness/state/drop.json`.

## Where it lives

    harness/battleplan/            missions/ prompts/ waves/ bus/ runs/ notes/ — this card
    docs/BATTLEPLAN.md             the plan (one card per system: update, don't multiply)
    .synapse/contracts/            memory-recall-honesty · harness-budget-rails · demo-round-trip
    harness/notes/h22/             orchestrator-bp1.{pid,log,err} · orchestrator-bp1-control.log (RAILS baseline)
    harness/notes/receipts/        BP1-*.json (land via worktree commits)
