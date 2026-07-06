# SYNAPSE v6 → Houdini 22 — the build plan, reconciled against repo truth

> Reconciled 2026-07-04 on branch `feat/harness-v6-track`. Every plan item below is mapped to
> the harness task that executes it (`harness/tasks.json`, phase `v6`) or to the already-shipped
> task that made it moot. The plan's voice and ordering are preserved; only repo facts changed.

## You are here

The harness loop (fresh Generator → checks → adversarial Evaluator → PASS/repair, completion
ledger, worktrees, no merge) is built, proven, and grinding Phase 0. Blueprints BP00–BP08
exist **only on paper** — nothing matching them is in the repo, so the entire v6 track below
is HELD until you drop them per `docs/v6/INTAKE.md`. The one thing the plan thought was
future work that's already done: the probe (Session E). H22 drops ~mid-July.

## RIGHT NOW — Sessions A–E (pre-drop, Mode A)

| Session | Plan said | Repo truth |
|---|---|---|
| **A — scaffold the skeleton** | stub every module in the BP00 manifest | task **V.1** — arms on blueprint drop; stubs land exactly where BP00's `## Module Manifest` table says, pass bodies, zero `hou` in pure layers |
| **B — write BP09** | Iteration Controller spec at BP00–08 fidelity | task **V.2** — propose→build→evaluate→decide→iterate, convergence/stop logic, max-iteration handling, pulls active strategies from BP07. Spec only |
| **C — spec + build BP10** | Global Knowledge Base | task **V.3** — pure Python, zero hou; recipe store + failure DB + vector schema (spec'd; JSONL is the shipped store) + query API. The one spine piece shippable before H22 |
| **D — pure-Python layers, test-first** | gsplat_compare interpretation, scoring rubrics, meta-cognitive stats | task **V.4** — tests FIRST (each blueprint specifies them) so drop day is "make them pass" |
| **E — arm the probe** | build the H22 API-delta probe | **DONE — do not redo.** Task 0.2 PASSED 2026-07-02: probe chain built (`scripts/h22_api_delta.py`), Mode-A identity diff EMPTY on 21.0.671 (`check_probe_runs`/`check_probe_clean`), 15 product phantoms surfaced and fixed along the way |

## DROP DAY — the probe gate

The plan's post-drop probe gate **is** existing tasks **1.4** (fire the probe → API delta
report) and **2.1** (patch the deltas — probe truth over pinned constants). It is a real
go/no-go: the 1.4 report re-ranks V.5–V.7 before any mile starts. Build to survive "feature X
shipped differently", not to assume it shipped as the paper said.

## POST-DROP — the miles (Mode B)

- **Miles 1–2 → task V.5:** BP01 Perception + BP02 G-Splat against *shipped* H22. Highest
  uncertainty first. (Expect V.5's first round to honest-fail `probe_clean` — the delta
  artifact lives in task 1.4's worktree, so the Generator re-fires the probe in its own.
  That's the check doing its job, not a bug.)
- **Miles 3–4 → task V.6:** BP08 three-tier evaluator — the keystone; 01+02 become the engine.
- **Miles 5–7 → task V.7:** BP09+BP10 integration — the **first autonomous cycle, PYRO ONLY**.
  Prove pyro end-to-end before any branch (BP07: G-Splat convergence tracks pyro at r=0.78,
  characters at r=0.31).
- **Miles 8+:** branches 03–07, **production-ordered after V.7, not corpus-ordered**.
  Deliberately not tasks yet — they get cut into the queue only after the pyro cycle closes.

Cadence: **run → merge passed V-worktrees → re-run.** Each task's worktree branches from
HEAD, so V.6 only sees V.5's modules (and V.7 only sees V.3's KB) after *you* merge them.
V.5–V.7 are designed to span separate invocations with your merges between — see
`docs/v6/INTAKE.md` §(f), including the completion-ledger caveat that unmerged V-tasks
re-run every invocation.

## WATCH

- **BP06's APEX Script MCP assumption is the most likely thing to break.** That risk is
  already fenced: task **1.7** probes the SHIPPED native MCP tool surface and auto-quarantines
  absent/renamed endpoints, and `docs/SYNAPSE_H22_BOUNDARY.md` is enforced as per-sprint
  guardrails. Pre-release prose is not ground truth; the 1.7 probe is.
- **The probe is a real go/no-go** — not a formality. An ugly 1.4 delta re-orders everything
  after it.
- **Meta-work check:** "editing this plan more than acting on it is the avoidance pattern"

This reconciliation was **one-shot**. The next edit to `docs/v6/` should be a blueprint drop,
not a plan edit.
