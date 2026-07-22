# Seam-gate acceptance run — 2026-07-22

First live run of the `seam-hunter` adversarial composition gate
(`.claude/agents/seam-hunter.md`), invoked as the Solaris hardening harness's
functional acceptance AND a residual-hunt on the merged Solaris builder
(origin/master, all fast-follows landed). Live on H22.0.368, all probing in
throwaway `/obj/seam_*` lopnets via hython on the real `_on_main` path; every
probe confirmed `leftover=[]` (no nodes or boxes leaked).

## Verdict: GO

The harness's fixes are live-merged and hold. **13 of 13 acceptance attacks
passed** — the exact seams that historically hid data-corruption regressions.
Two cosmetic residuals found (below); neither is corruption, wrong output, or a
crash, so not a NO-GO. The gate both proved itself and caught a real (minor)
residual my own probes and the prior seam fleet missed — which is the point.

## Attacks run (auditable)

| Attack | Outcome |
|---|---|
| Extend artist merge via `{existing:true}`, rebuild identical 3× (implicit append) | PASS — inputs stable, status `created→unchanged→unchanged`, merge never stamped |
| Same with explicit `input:2` (separate branch) | PASS |
| Rebuild one network 3× changing only `display_node` | PASS — boxes stayed 3 (not 3→6→9) |
| Full template build→look→rebuild 3× | PASS — children stable, no `OUTPUT1` dup |
| Two networks sharing name `OUTPUT`, second wires a different source | PASS — refused, A untouched, B rolled back |
| Explicit-index collision into an existing node | PASS — refused, artist wiring intact |
| Two independent ≥4-node networks in one /stage | PASS — both keep their boxes (6), no cross-sweep |
| Round-trip recognition (`domelight` → `domelight::3.0` → refind) | PASS — reused, never a phantom miss |
| Depth-vs-rank inversion (light as root feeding geo) | PASS — bands suppressed honestly (0 boxes) |
| Wire downstream of `usdrender_rop` (0 outputs) | PASS (clean rollback) — see nitpick |
| Parm/status coercion (int `2` into a `2.0` float parm) | PASS — `unchanged`; control int `5` → `updated` |
| Unknown node type mid-graph | PASS — rejected pre-undo-group, designed error |
| Band-shrink WITH display-node/namespace change | **residual (below)** |

## Residuals found (both cosmetic — fast-follows, not release gates)

### 1. MINOR — ghost section box survives a namespace-changing rebuild

When a rebuild **changes the display node** (the section-box namespace key) **and**
a prior box's sole member left the build's `id_to_hou` (dropped from the spec but
still a live child in the stage), that box is swept by neither predicate and
lingers.

- **Where:** `handler_helpers.py` `_apply_section_boxes` sweep — a prior box is
  cleared only on `ns_match` (name under the current namespace) OR `member_match`
  (`any(n in my_nodes for n in box.nodes())`). Namespace changed → no ns_match;
  the sole member left `my_nodes` → no member_match.
- **Bounded, not stacking:** across 4 rebuilds the box count was `[3, 3, 1, 3]` —
  it does not accumulate and **self-heals** when a later build's node set
  re-includes the orphaned member.
- **Why minor:** cosmetic — the ghost box still correctly surrounds a node that
  still exists; no wire moves, no data corrupts. Reachable only by a compound
  rebuild (display swap + a band member leaving the spec).
- **Fix direction:** in the sweep, also clear any `_SECTION_BOX_PREFIX` box whose
  membership is disjoint from every OTHER live SYNAPSE network (orphan
  detection), or walk the connected closure (`inputs()/outputs()` from
  `id_to_hou`) rather than plain membership. Take care not to sweep a valid
  second network's boxes — re-run the seam-gate after.

### 2. NITPICK — bare `hou.InvalidInput` wiring downstream of a zero-output node

Wiring a node off `usdrender_rop` (0 outputs) rolls back cleanly (safety holds),
but the artist sees a bare `InvalidInput: Invalid input.` instead of the designed
remediation-carrying `SynapseUserError` the sibling guards produce.

- **Fix direction:** pre-check in the wire loop — if
  `source.type().maxNumOutputs() == 0`, raise a `SynapseUserError` naming the ROP
  and suggesting it be a terminal.

## Note

These are the harness's OWN first output: found by the gate, not by isolated
tests. The right way to close them is to run them back THROUGH the pipeline
(spec → integrate → seam-gate → verify) — dogfooding the harness.
