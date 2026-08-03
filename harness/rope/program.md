# rope harness · program.md
Methodology after karpathy/autoresearch (fetched 2026-08-03): the human programs
THIS file, not the Python; the agent edits only in-scope files; fixed budget per
task; a mechanical verdict decides keep-or-discard; everything logs; the loop
does not stop to ask. Adapted from open-ended research to closed task execution:
"invent next experiment" becomes "take next eligible task from STATE.json", and
val_bpb becomes each task's Accept commands.

## The two modes
- **Mode 1 (primary): `python harness/rope/runner.py run`** — deterministic
  Python orchestrator. Zero-token dispatch, zero-token verification. The LLM is
  invoked ONLY at the edit step, one fresh headless session per task.
- **Mode 2 (interactive): open Claude Code in this repo** and say
  "read harness/rope/program.md and take the next eligible task." Uses the
  .claude/agents/rope-executor subagent. For supervised sessions only.

## The Axiom (governs every edit)
Synapse is measured by what the artist can do without it. A rope gives reach
you haven't earned and safety while you earn it — load-bearing, never
self-propelling.

## The Laws, compressed
- L1 It holds — no claim may exceed what code observably does. Red suite = freeze.
- L2 It frays visibly — failure announces itself; empty ≠ unchecked.
- L3 Tie in alone — a stranger reaches a working prompt unaided.
- L4 Your rope — models discovered from the user's endpoints, never curated;
  NO ComfyUI/diffusion surface ever (Comfy-Cozy's domain, absolute).
- L5 Pays out at your pace — 3 designs, 1 widget library + manifests +
  compositor; identical capability in every profile; expert == v5.42.0 exactly.
- L6 Never climbs for you — explanation may rise, automation may not;
  notify on change, switch only on user action.

## What you CAN do (per task)
- Read and edit ONLY the files named in the task's `files` list, plus create
  the new files the task's `change` text names (tests included).
- Run the task's own accept commands locally to self-check before finishing.

## What you CANNOT do
- Explore the repo. The task card names every file; the codebase is ~450k
  lines and you are on a token budget. No directory walks, no "context" reads.
- Touch `harness/rope/**` (except reading STATE), `.env`, anything in
  `python/synapse/_vendor/`, or any file not named by the task.
- Modify accept commands, STATE.json statuses, or this file. The verdict
  machinery is ground truth (karpathy: "do not modify the evaluation harness").
- Refactor beyond the task. Simplicity criterion applies: a small win that
  adds ugly complexity is not worth it; deleting code for equal results is.
- Commit. The runner commits after verification, never you.

## Anchor rule (blueprint §4)
Edits target exact strings from the task card. If an anchor does not match the
file as it exists, STOP: print `BLOCKED:<task-id> anchor miss: <anchor>` and
end the turn with zero edits. Never improvise a nearby match.

## Token discipline (/token-saver — installed locally in .token-saver/)
Read only listed files, and only the relevant ranges of big ones. Redirect any
command output to a file and grep the one line you need — never flood context
(`cmd > out.log 2>&1` then grep). One bounded repair attempt if your own
self-check fails; then stop and report. Print `DONE:<task-id>` plus a one-line
receipt when finished.

## The loop (Mode 1 does this for you; Mode 2 agents follow it manually)
next eligible task -> edit -> self-check -> DONE -> runner verdict:
all accepts pass -> commit + verified | any fail -> reset --hard, attempts+1,
2 strikes -> blocked, move on. Loop until no eligible tasks. Never pause to ask.
