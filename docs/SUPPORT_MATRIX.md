# SUPPORT MATRIX · SYNAPSE

Support claims name exact tested builds (W9 acceptance). Rows are dated
receipts; the newest row is the live claim. Unmeasured renders as *pending*,
never as a pass.

| Build | Symbol table | E2E | Node-type assay | Punycode | Dated |
|---|---|---|---|---|---|
| H22.0.400 | 35,908 · stamped · gate armed (verified-runtime, hython) | **pending** | open — 2 missing types (`instancer`, `layout` → `test_setdressing_recipe.py`) + 266 parm deltas (predominantly `apex::autorigbuilder`; rigging domain, refused without re-litigation) | 27 match / 0 changed / 0 vanished / **99 new, adoption pending** (lockstep rule) | 2026-08-09 |
| H22.0.368 | 35,903 · superseded | verified | — | 27 match | 2026-08-06 |
| H21.0.671 | 33,255 (`h21_symbol_table.json`) · H21 authority, untouched | verified | baseline catalog | — | — |

Probe of record: `.claude/probe_delta.json` (`h22_probe_delta/v1`) — 268
unpatched drift items, all inside the deferred node-type assay; counted by
`harness/verify/checks.py::check_probe_clean` (red until the assay lands —
declared here rather than silently absorbed).

## A4 pin census — 2026-08-09 (scope-declared)

Scope: `python/synapse/` · `fixtures/` (1 file, 0 matches) · `docs/`.
Counts: `22.0.368` ×469 · `22.0.397` ×35 · `22.0.382` ×7
(adoption baseline 422 / 18 / 2 — growth is the documents written *about*
the pins, counted honestly rather than excluded).

Classification: **live claims moved to 22.0.400** — `README.md:9` banner,
`CLAUDE.md:3` target, and the README e2e line amended to declare pending
rather than imply re-verification. **Everything else is dated historical
receipts, retained** per A4: review / adjudication / ticket documents,
provenance stamps in knowledge data (`lop_solaris_knowledge_22.json`),
probe-truth annotations in code (`handlers_cops.py`), and illustrative
constants (`scene_memory.py:243`, `canonical.py:96`, `scout.py:470`).
Zeroing provenance is prohibited.
Test-side: `tests/solaris/test_live_wiring.py::PINNED_BUILD` stays `22.0.368` —
its expected-red set was observed on that build; re-pinning requires the live
tier re-run inside 22.0.400 (part of e2e pending), never a string swap.

Re-stamp ritual: run `hython host/introspect_runtime.py` inside the target
build → commit the table → scout's stamp check does the rest
(`python/synapse/panel/gate_stamp.py`). Pin of record: `harness/state/drop.json`
(human file-write, single-writer).


## `lastCookTime()` cook-time contract — 2026-08-09 (observed, both contexts)

`hou.OpNode.lastCookTime()` on 22.0.400, live-assayed same day from both sides:

- **GUI session** (`hou.isUIAvailable()` true): returns **milliseconds**, wall-clock-accurate
  to ~0.2%. Receipt: `harness/notes/cache_h22_gui_assay_22.0.400.json`
  (wall 0.1714 s → raw 171.14; wall 0.1473 s → raw 147.17; run via `houdini -waitforui`).
- **Headless hython**: returns **0.0 unconditionally** for real cooks — perfMon on or off
  (wall 67–96 ms while `cookCount` increments normally). Receipt:
  `harness/notes/cache_h22_contract_assay_22.0.400.json` item 3, held as a **declared
  delta**: the assay expects 0.0 headless and fails loudly only if that behavior changes.

Probe consequence (R-CACHE-1 / M3b): `host/cache_host_probe.py` converts ms→s exactly
once, and classifies any non-positive reading that carries cook evidence as **UNKNOWN**
with provenance `lastCookTime_unreported` — never a fabricated zero. Farm, test, and
hbatch contexts therefore report UNKNOWN cook time by design; in-session GUI use is the
verified measurement path.
