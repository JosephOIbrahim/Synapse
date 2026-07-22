# Solaris wiring hardening — fast-follows

Tracking doc for the deferred items from the Solaris wiring + node-recognition
hardening effort (merged to master at `98386cd` and `599e2ef`, 2026-07-21).

**None of these are blockers.** Every recon blocker (B1–B6, B9), the Phase-3
layout, M10 section boxes, and the two composed regressions the verification
gates caught are closed and shipped; suite 4683/0 on live H22.0.368. These are
the things that were consciously scoped out or left as known limitations, with
enough grounding to pick each up cold.

Full context: `docs/reviews/solaris-wiring-gap-ledger-2026-07-21.md` (the recon
ledger) and `docs/reviews/netbox-implementation-contract-2026-07-21.md` (M10).

---

## 1. Per-network section-box identity — *cosmetic*

**Where:** `python/synapse/server/handler_helpers.py` → `_apply_section_boxes`
(already carries a `KNOWN LIMITATION` note in its docstring).

**What:** M10 section-box names are stage-global (`synapse_sec_scene` /
`_lighting` / `_render`). Building a **second** independent network into the same
`/stage` sweeps the first network's boxes (the unconditional prefix sweep) and
draws only the second's. The nodes and wiring of both networks are untouched —
only the first's *visual grouping* disappears.

**Why deferred:** the common case is one network per `/stage`; no corruption,
purely cosmetic.

**Fix direction:** namespace the box names by the build's `display_node` (e.g.
`synapse_sec_<display>_scene`) and scope the sweep to that namespace, so each
network keeps its own boxes. Add a multi-network case to
`scripts/live_probes/probe_m10_section_boxes.py`.

---

## 2. M2 — extend an existing network via the structured tools — *major*

**Where:** `python/synapse/server/handlers_solaris_graph.py` (`build_graph`
rejects any connection endpoint not in the payload);
`python/synapse/server/handlers_solaris_assemble.py` (`assemble_chain` only
wires *unwired* nodes).

**What:** the most common Solaris op after the initial build — "add two more
asset variants to this merge" — has no clean structured path. `build_graph`
can't reference a live scene node, and `assemble_chain` only tidies unwired
nodes, so extension falls through to raw `execute_python` (ungated on the live
`/synapse` path).

**Why deferred:** the recon flagged it (M2); it needs a schema change, not a
bug fix, and the initial-build path was the priority.

**Fix direction:** an `existing_nodes` field on the `build_graph` schema so a
graph can name live scene nodes as connection endpoints, reusing the B4
`_ensure_node` + the cross-network conflict guard (`599e2ef`) so an extend that
would clobber an existing input is refused rather than silent.

---

## 3. `.gitattributes` LF pin — *hygiene*

**What:** the repo has no `.gitattributes`, so with `core.autocrlf` git prints
`LF will be replaced by CRLF` on every commit touching the committed JSON
catalogs (`connectivity_*.json`, `h22_lop_catalog_live_*.json`) and Python. It's
cosmetic churn, but it also risks a real CRLF round-trip on the byte-identical
drift-guarded catalogs (`harness/verify/checks.py` compares the packaged copy
byte-for-byte against the harness note).

**Fix direction:** add a `.gitattributes` pinning `*.py`, `*.json`, `*.md`, and
the probe scripts to `text eol=lf`, and confirm the drift-guard catalogs stay
byte-identical after normalization.

---

## 4. `status='unchanged'` after a parameter change — *nitpick*

**Where:** `python/synapse/server/handlers_solaris_graph.py` (the status
selection: `unchanged` when `nodes_reused and not nodes_created`).

**What:** on a rebuild that reuses every node but changes a parameter value, the
response reports `status='unchanged'` even though a parm moved. Misleading, not
harmful.

**Fix direction:** track whether any `_set_parm` actually changed a value during
the reuse and report `updated` when it did.

---

## 5. Advance the ratchet floor — *decision, not a fix*

**Where:** `harness/verify/suite_baseline.json` (still pins `passed=4275`,
`failed=0`); live is `4683/0`.

**What:** the ratchet guardrail (`harness/verify/checks.py::check_suite_baseline`)
reads the floor at `merge-base(master, HEAD)`. Leaving it at 4275 means a future
regression that dropped to, say, 4400 passing would still clear the floor — a
weaker protection than the ~400 new tests could provide.

**Why deferred:** advancing the floor is explicitly a **human-promoted** step
(the ratchet's own rule), and it locks a higher bar that the macOS CI matrix's
known timing flakes could trip. Deliberate, not forgotten.

**Fix direction:** a one-line bump of `passed` to the live green count in a
commit whose subject makes the promotion explicit, after a clean CI run on the
matrix.

---

*Ordered by leverage: 2 (real capability gap) and 5 (protection) are the ones
worth doing; 1, 3, 4 are polish.*
