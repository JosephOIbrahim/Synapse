# Solaris wiring hardening — fast-follows (RESOLVED)

The deferred items from the Solaris wiring + node-recognition hardening effort,
now resolved (PR #47). Kept as a record of what shipped and why.

Original context: `docs/reviews/solaris-wiring-gap-ledger-2026-07-21.md` (recon
ledger), `docs/reviews/netbox-implementation-contract-2026-07-21.md` (M10).

**How this was closed:** a 3-agent SPEC fleet ground each item's live API and
produced exact hunks; the CTO integrated (reconciling the shared-file overlaps
the parallel agents couldn't); a 4-agent adversarial SEAM fleet then attacked
the integrated result and found a real corruption blocker the isolated probes
missed — fixed before merge. Every item is live-verified on H22.0.368.

---

## 1. Per-network section-box identity — DONE

Section boxes are namespaced by the build's display-node name
(`synapse_sec_<display>_<band>`), and the sweep is scoped so a second network no
longer sweeps the first's. Identity is **membership-based as well as
name-based** — a network whose display node changes between rebuilds is still
recognized by the nodes its boxes contain, so a display-node swap refreshes in
place instead of stacking duplicates (the seam fix). A genuinely disjoint second
network shares no members and is left intact. Artist boxes are never touched.

`python/synapse/server/handler_helpers.py::_apply_section_boxes` (+ the call
namespaces by `id_to_hou[display_node_id].name()`). Tests:
`tests/test_solaris_layout.py::TestSectionBoxNamespacing`. Live:
`scripts/live_probes/probe_m10_section_boxes.py`,
`scripts/live_probes/probe_pr47_fast_follows.py`.

## 2. Extend an existing network via build_graph — DONE

A node spec may be marked `{"existing": true, "name"|"path": ...}`: it resolves a
live node instead of creating one, and connections into it **append to the next
free input** (reusing `assemble._next_free_input`) instead of clobbering input 0.
The existing node is never created, moved, stamped, re-parameterized, or
sectioned. An explicit index that would overwrite a different source is refused.

**Idempotency (the seam fix):** appending a source already wired to the target is
a no-op, so build → look → rebuild never duplicates a wire. Without this the
merge grew unboundedly (`[a,b,c]` → `[a,b,c,c]` → …) — caught by the seam fleet,
not the single-append probe.

`python/synapse/server/handlers_solaris_graph.py` (`_resolve_existing_node`,
`existing_nids`, the append/guard wiring). Tests:
`tests/test_solaris_graph.py::TestExistingNodeReference` /
`TestNextFreeInputAppend` / `TestExtendAppendIdempotency`. Live:
`scripts/live_probes/probe_pr47_fast_follows.py`.

*Known minor (documented, deferred):* `detect_order_ambiguities` does not warn
that an appended input lands at the strongest merge index. `connections_made`
reports the exact index, so it is visible; an explicit "appended at input N
(strongest)" advisory is a future polish.

## 3. `.gitattributes` LF pin — DONE

`.gitattributes` pins text to LF in both the repo and the working tree, stopping
the `LF will be replaced by CRLF` churn and protecting the byte-identical
drift-guarded catalogs (their blake2b is computed over parsed JSON, so line
endings never affect the guard; both catalog copies stay in lockstep). Policy is
**forward-looking** — no repo-wide `git add --renormalize` was run, since that
would be a large, noisy diff touching hundreds of pre-existing CRLF files. A
one-time renormalize remains an optional, separate cleanup.

## 4. `status='unchanged'` after a parameter change — DONE

`_set_parm` now returns `(landed, changed)`, comparing the post-set eval to the
prior (coercion-proof). A full-reuse rebuild that moves a parm value — or a wire
— reports `status='updated'`; a genuine no-op rebuild reports `unchanged`; a
build referencing only existing nodes never reports `created`.

`python/synapse/server/handlers_solaris_graph.py` (`_set_parm`, `parms_changed`,
`connections_changed`, the status selection). Tests:
`tests/test_solaris_graph.py::TestSetParmChanged`. Live:
`scripts/live_probes/probe_pr47_fast_follows.py`.

## 5. Advance the ratchet floor — DECISION MADE: do NOT advance from a local count

`harness/verify/suite_baseline.json` stays at `passed=4275`. Investigation
settled the decision the original item flagged:

`check_suite_baseline` requires `passed_now >= passed_base`. The floor is 4275,
not the local green count (now 4701), **because CI runs on Linux** where many
Houdini/Windows-gated tests skip. Setting the floor to a local Windows count
would break the ratchet on the very next CI run. Advancing therefore requires a
**CI-observed Linux green count**, which cannot be derived from a local run — it
is a post-merge, observed number. The guardrail already holds as-is (0 failures,
passes far above floor), so leaving 4275 is correct and non-breaking. This is the
"human-promoted after a clean CI run on the matrix" the item anticipated.

---

*All five resolved. Items 2 and 5 carried the real substance; the seam fleet's
catch on item 2's rebuild-idempotency is the reason this shipped correct rather
than corrupting-on-rebuild.*
