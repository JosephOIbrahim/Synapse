# SYNAPSE × Boris-Harness — Launch Runbook (Legs 2–3)

> Leg 0 (scaffold) and Leg 1 (Mile 1) are **done and green** in this bundle — built
> and gate-verified off-Houdini, because Mile 1 is mock-only by design. This runbook
> is the outer dev-loop you run on the Threadripper for the legs that need hython /
> graphical Houdini. It rides your existing constitutional dispatch (ARCHITECT →
> FORGE → CRUCIBLE); it does **not** add a second harness next to `autonomy/`.

---

## The relay, as harness rounds

| Boris phase | Here | State |
|---|---|---|
| Planner | ARCHITECT v3 + 7 amendments + the scaffold blueprint | **done** — do not re-plan (phantom) |
| Worktree | one per Leg | Leg 1 ✅ · Leg 2/3 below |
| Generator (WIP=1) | a fresh FORGE instance fills **one Mile's** stubs, atomic commit | Mile 1 ✅ · Mile 2 ✅ (merged `e6e989d`) |
| Evaluator (adversary) | `HARNESS/forge_evaluator_gate.py --mile N` (boundary + DoD + phantom + mutation) | ✅ runnable, Mile 1 PASS |
| Repair loop | gate FAIL → `remediation[]` → fresh FORGE, same worktree | wired (exit code + manifest) |
| Memory | `CHANGELOG.md` + `agent.usd` provenance + governing docs committed first (F3) | existing discipline |

The Evaluator's exit code is the loop's branch: **0 → merge, 1 → repair.** No stdout parsing required.

---

## Worktree plan

```
git worktree add ../syn-mile2 -b feat/graph-synth-mile2   # needs hython 21.0.631
git worktree add ../syn-mile3 -b feat/graph-synth-mile3   # needs graphical 21.0.671 (undo/connect)
```

Leg 1 carried **no** dependency on the bench — it shipped on mocks. Legs 2–3 converge once the bench preflights clear (below).

---

## The loop (one command per round)

```bash
# GENERATOR — fresh context, WIP=1, headless. Uses your logged-in Claude session,
# NOT the API key (see Auth guardrail). --append-system-prompt-file delivers the
# prompt; stdin avoids cmd.exe mangling multi-line args.
claude -p --permission-mode acceptEdits \
  --append-system-prompt-file HARNESS/prompts/forge_mile2.md  < /dev/null

# EVALUATOR — adversarial gate. Exit 0 merges; exit 1 emits remediation[].
PYTHONPATH=python python HARNESS/forge_evaluator_gate.py --mile 2
```

On FAIL, pipe the manifest's `remediation[]` into the next Generator boot as its only
ticket — same worktree, fresh context (this mirrors `autonomy/driver`'s re-plan-on-fail,
which you already ship).

---

## Per-Mile FORGE prompts (drop into `HARNESS/prompts/`)

**`forge_mile2.md`**
```
ROLE: FORGE. Fill ONLY Mile 2 of the graph-synthesis blueprint. Do not refactor
unrelated files. Do not touch cognitive/graph_proposal.py or interfaces.py (FINAL
contracts).

TARGET (this Mile, this worktree only):
  - host/graph_oracle.py: implement IConnectivityOracle via hou.* — but EVERY hou
    symbol must be dir()-confirmed against live H21.0.671 FIRST (§2.5). Confirmed
    absent: hou.pdg.*, hou.secure, hou.lopNetworks(), hou.updateGraphTick. If a
    needed symbol isn't in dir(), STOP and surface — do not write against priors.
  - cognitive/graph_validator.py: implement _phase3_connections (3a arity / 3b
    type-compat typed-only / 3c slot-label advisory / 3d occupied-input guard —
    3d HALTS, never degrades), _phase4_structural (DAG, name collisions),
    _phase5_context. Then flip live_phases_enabled default to True ONLY after the
    five §12 Mile-2 tests are written and green.
  - host/existence_adapter.py: wire to the confirmed scout surface (§2.6).

DONE = the five Mile-2 DoD tests green + boundary green + gate PASS:
  PYTHONPATH=python python HARNESS/forge_evaluator_gate.py --mile 2
Atomic commit. Then halt for the Evaluator.
```

**`forge_mile3.md`**
```
ROLE: FORGE. Fill ONLY Mile 3. graphical Houdini required (undo + connect).

TARGET:
  - host/graph_builder.py: instantiate() from a VALIDATED proposal. Re-run Phase 5
    + recompute scene_fingerprint UNCONDITIONALLY before building (TOCTOU). ONE
    hou.undos.group() block: create NEW nodes in topological order → set parms (new
    only) → connect edges → close → emit provenance receipt to agent.usd. Truth
    contract: read back every parm you set; never claim an unobserved outcome.
    Reject unknown proposal_id (amendment 5).

DONE = novel-topology extend-existing build + single Ctrl+Z undo +
  delete-between-propose-and-instantiate halts with zero mutation. Gate PASS --mile 3.
HALT before merge to main (human gate).
```

---

## Headless permissions (`.claude/settings.json` → `permissions.allow`)

Pre-allow only the loop's verbs so it runs without modal prompts and **without**
`--dangerously-skip-permissions`. Confirm the exact pattern syntax against your
installed Claude Code version before committing.

```json
{
  "permissions": {
    "allow": [
      "Bash(python -m pytest:*)",
      "Bash(PYTHONPATH=python python HARNESS/forge_evaluator_gate.py:*)",
      "Bash(git add:*)", "Bash(git commit:*)", "Bash(git worktree:*)",
      "Bash(hython:*)"
    ],
    "deny": [
      "Bash(git push:*)",
      "Bash(rm -rf:*)"
    ]
  }
}
```

---

## `CLAUDE.md` block to paste (≤ the cache budget)

```
## Graph-synthesis relay (FORGE)
- WIP=1: fill ONE Mile per fresh instance; atomic commit; halt for the gate.
- cognitive/* imports ZERO hou — enforced by tests/test_cognitive_boundary.py.
- Gate before any merge: PYTHONPATH=python python HARNESS/forge_evaluator_gate.py --mile N
- Phantom discipline: dir()-confirm every hou.* against live H21.0.671 before use.
- Contracts (graph_proposal.py, interfaces.py) are FINAL. Do not edit.
- HUMAN GATES (never automate): (1) sidecar-vs-abi3 (D-0.1), (2) drop.json trigger
  after H22 installs, (3) merge to main.
```

---

## Auth guardrail (non-negotiable)

- The harness invokes **Claude Code under your logged-in session** — it does **not**
  read `SYNAPSE_ANTHROPIC_KEY`, and you must **never** export that as
  `ANTHROPIC_API_KEY` (that's the welded-env / bun-injection failure class that cost
  you the debugging saga). Keep `OCIO` and `WS_PORT` in `.env`; leave `HYTHON` as the
  User-scope var.
- `bun` auto-loads `.env` into every spawned process — so if the harness shells
  through bun, audit that `.env` carries no `ANTHROPIC_API_KEY`.

---

## Bench preflights that unblock Leg 2 (run in parallel, at the bench)

These are the human/runtime checks the harness **correctly refuses to fake** — they
need live introspection, not priors:

- **§2.5** — `dir()` the candidate `hou` connectivity symbols against H21.0.671;
  Appendix A is unverified until confirmed.
- **§2.6** — does `scout` return a structured exists-verdict or retrieval chunks?
  Determines whether `existence_adapter` is a pass-through or a wrapper.
- **§2.4 / Amd-6** — the remaining preflights named in the blueprint.

When these clear, Leg 2's Generator has real ground to stand on. Until then, Leg 1
stays the furthest green line — which is exactly where a relay hands off.
```
