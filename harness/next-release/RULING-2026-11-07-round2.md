# Ruling — round two for the wave-1 branches (2026-11-07)

Wave 1 landed three branches and three attack verdicts. Two of the three were
**needs-work**, and both attacks named the same class of problem: the fix was
right inside its node and wrong at the seam the node did not own. This ruling
sets the scope for round two before any code is written, because two of the
corrections change ownership and a node's `owner_files` is a contract.

## R1 — The sparse-render seam is its own node

`NR-SPARSE-RENDER` is added (owner HANDS:
`server/handlers_render.py`, `server/render_farm.py`, `mcp/_tool_registry.py`).
The driver now grades the artist's sparse set, but the shipped handler reads only
`start_frame`/`end_frame`/`step`, the farm builds a contiguous range, and the MCP
schema exposes no `frames` — so a sparse request still renders the invented
frame. Stretching `NR-PLAN-TRUTH` across that seam would give a CONDUCTOR node a
HANDS file. A dependent node with its own predicate is the honest structure.

## R2 — `NR-PLAN-TRUTH` owns `models.py`

Keeping the artist's plan immutable was correct, but the executed validation
results and step status now live on a discarded copy, and `_record_autonomy_task`
reads the empty original. The report must carry the attempt's derived state.
`python/synapse/autonomy/models.py` joins the node; the out-of-surface comment
edit is no longer out of surface.

## R3 — `NR-WRITE-RECEIPT` owns every installed route

The contract says "survives every installed route". The attack proved it survives
one. The in-Houdini `/mcp` rewrap, `mcp_server.py`, and the panel executor each
drop `structuredContent`, and the registry filter drops `frame`, `queued`,
`expect` and `request_id` before the handler sees them. Those four files join the
node: `mcp/_tool_registry.py`, `mcp/server.py`, `mcp_server.py`,
`panel/tool_executor.py`.

## R4 — A predicate that cannot fail is retired

The attack demonstrated that `grep -q 'OUTPUT_MISSING'` still exits 0 with
`retry_targets` replaced by `return {}`. Both wave-1 predicates are greps and both
have the same weakness. From this ruling, a next-release node's closure predicate
is **behavioural**: a hermetic test file that can fail. A comment, a symbol name
or a dead branch must not satisfy it.

## R5 — Round two lands on the existing branches

One atomic commit per blocker cluster, failing-first tests, no merge, no push.
Each follow-up carries the head SHA, and the adversarial verdict names that SHA.

## R6 — The GPU lane closes B1, not the build

Round two adds one real probe: does nvcc 13.3 accept MSVC 19.44 (B1). It does not
clone sources or start a build. B2 (worker Python ABI) is the owner's decision and
stays open; the receipt records the two candidate runtimes rather than choosing.

---

## Addendum — round 2.5 (the attacks' ownership findings)

**R2b — `handlers.py` stays with NR-WRITE-RECEIPT.** NR-PLAN-TRUTH's round-two
commit edited `_record_autonomy_task` to read the new `executed` field. The file
belongs to NR-WRITE-RECEIPT. Plan-truth reverts that hunk; write-receipt applies
the reader repoint with a `getattr(report, "executed", None) or report.plan`
fallback, so it is correct whichever branch merges first, and pins it with a test.

**R3b — the panel consumers join NR-WRITE-RECEIPT.** The receipt is attached to the
exception in `panel/tool_executor.py`, but the only production consumers —
`panel/claude_worker.py`, `panel/direct_tool.py`, `panel/render_workspace.py` —
stringify the exception and drop it. "Survives every installed route" includes the
consumer that turns it into a tool result. Those three files join the node.

**R4b — pre-dispatch returns carry no executed checks.** A report that stopped
before dispatch must not present the planner's declared `passed=False` checks as
if they had run. `executed.validation_checks` is empty on gate_rejected and
unsupported_plan_shape, and the reader reports the absence honestly.

**R2c — merge order is part of the contract.** `report.plan` now means the
artist's declared request and `report.executed` the last attempt's state. The
installed `_record_autonomy_task` reads `report.plan` until NR-WRITE-RECEIPT
lands its repoint, so **NR-WRITE-RECEIPT merges before NR-PLAN-TRUTH**, or both
land in one window with the repoint installed before anything is pushed.
Merging plan-truth alone writes `checks=8 hard_fail=3` to `agent.usd` for every
successful render — a false receipt on the success path, worse than the one the
node fixed. NR-SPARSE-RENDER merges before NR-PLAN-TRUTH as its declared
dependency; plan-truth's predicate passes without it, so the order is enforced
here, not by the predicate.
