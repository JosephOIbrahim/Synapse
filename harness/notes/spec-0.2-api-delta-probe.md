# Task 0.2 spec — the H22 API-delta probe

> Condensed from the release-runway design §1.1 (2026-07-01). This is the spec
> `harness/tasks.json` task 0.2 executes against. **One drop-day command
> produces one machine-readable delta report from three probes.**

## Deliverable A — `scripts/extract_emitted_node_types.py` (pure Python, no hou)

- Statically scans `python/synapse/**/*.py` for `createNode("...")` /
  `createNode('...')` literals (raw-text scan — the recipes emit *generated
  code strings* an AST walk would miss; placeholders like `'{geo_type}'` are
  excluded by the node-type character class), plus the verified-spelling
  lists already pinned in `tests/test_apex_recipe_names.py` (`APEX_SEED`
  nodetypes) and `tests/test_setdressing_recipe.py` (`VERIFIED_NODE_TYPES`).
- Output: `python/synapse/cognitive/tools/data/emitted_node_types.json` —
  `{schema: "emitted_node_types/v1", generated_from_commit, entries:
  [{category, type_name, source_files}]}`. Committed after one human review
  pass.
- Check: deterministic — re-running on the same commit produces an identical
  file; `tests/test_emitted_node_types.py` asserts both verified lists are
  fully present.

## Deliverable B — `host/introspect_nodetypes.py` (hython-only, zero-synapse-import)

- Mirrors `host/introspect_runtime.py`'s pattern (host layer never imports
  the package). For each `emitted_node_types.json` entry: resolve via
  `hou.nodeTypeCategories()` + `hou.nodeType(category, name)` + a
  deterministic component-scan for namespaced/versioned spellings; record
  existence and, for existing types, the parm-template-group fingerprint —
  ordered `[(parm_name, template_type, default)]` + a BLAKE2b of it.
- For LOP light/camera types, additionally instantiate one node in a
  throwaway `/stage` network (headless-safe) and walk `node.parmTuples()` to
  capture the live punycode `xn__` names — the same probe method that
  produced `harness/notes/verified_usdlux_encodings_21.0.671.json`. Includes
  the camera-LOP probe for the six aliases pinned UNVERIFIED at
  `usd_punycode.py:82-87`.
- Output: `harness/notes/verified_nodetype_catalog_<build>.json` —
  version-stamped like the symbol table (`houdini_version`, `blake2b`).
- Check (Mode A): run under H21.0.671 hython → every emitted type exists,
  zero probe errors; the punycode section byte-matches
  `verified_usdlux_encodings_21.0.671.json` for every key they share.

## Deliverable C — `scripts/h22_api_delta.py` (the drop-day command)

- Usage: `hython scripts/h22_api_delta.py [--baseline-table <path>]
  [--baseline-catalog <path>] [--baseline-encodings <path>] [--out
  .claude/probe_delta.json]` — defaults to the committed H21 artifacts.
- Steps: (1) regenerate the symbol table in-memory via
  `host/introspect_runtime.build_table()` — **touch the lazily-loaded
  `hou.qt`/`hou.text`/`hou.secure` namespaces first** (the `dir()` blind spot
  from `docs/H22_READINESS_REPORT.md`; note `importlib.import_module`
  can NEVER load them — `hou` is a module, not a package); (2) **symbol
  diff**: `added` / `removed` / `moved_candidates` (leaf reappears under a
  different parent — heuristic, always human-triaged), ranking `removed` by
  SYNAPSE call-site usage (static grep index over `hou.`/`pdg.`/`pxr.`
  attribute chains — getattr chains and hscript strings are invisible, the
  report says so); (3) **node-type diff** vs the baseline catalog: missing
  types, parm renames, default changes; (4) **punycode re-probe**: regenerate
  the alias→encoded map from live nodes, diff vs
  `synapse.core.usd_punycode.PUNYCODE_PARMS`, and emit
  `harness/notes/verified_usdlux_encodings_<build>.json` (never overwriting
  an existing curated file) plus a ready-to-paste proposed `PUNYCODE_PARMS`
  block.
- Outputs: (a) `.claude/probe_delta.json` — `{schema: "h22_probe_delta/v1",
  baseline_build, live_build, symbols, node_types, punycode, unpatched}`
  where `unpatched` is the flat triage list; exactly what
  `harness/verify/checks.py::check_probe_clean` counts; (b)
  `.claude/probe_delta.md` — the human triage doc, grouped by consumer
  (scout table / punycode / recipes / rag corpus).
- The diff engine is a hou-free pure module
  (`python/synapse/cognitive/tools/api_delta.py`) so
  `tests/test_h22_api_delta.py` exercises every diff path on the stock-3.14
  suite with fixture tables — the full-suite pytest gate applies.
- Check (Mode A, the proof tasks.json 0.2's note requires): on H21 with
  defaults, `unpatched == []` → `probe_runs` AND `probe_clean` both green
  **before** the drop makes the diff real.

## Bonus folded into 0.2 — the camera punycode entries

The camera aliases at `usd_punycode.py:82-87` are flagged UNVERIFIED and
almost certainly wrong (standard UsdGeomCamera attrs are not in `inputs:` so
are not punycode-encoded at all). Deliverable B probes a real camera LOP;
correct or drop those six entries, updating
`tests/test_usd_punycode_single_source.py` +
`tests/test_corpus_encoding_conformance.py` in lockstep. Verification: full
pytest + a live hython set-parm smoke on a camera LOP.

## Status (Mode-A identity proof, 2026-07-01, H21.0.671)

- Full chain ran under hython: `unpatched == []`, symbols `+0/-0`, punycode
  27 pinned matches / 0 changed / 0 vanished; `check_probe_clean` → ok.
- Camera-LOP probe: all six camera attrs are **plain camelCase parms**
  (`focalLength`, `focusDistance`, `fStop`, `horizontalAperture`,
  `verticalAperture`, `clippingRange`) with **no `xn__` encoding** — the
  bonus fix should replace the six pinned punycode values with the plain
  names (human pass, lockstep tests).
- The catalog probe surfaced **9 pre-existing phantom node-type spellings**
  in product code (recorded `exists:false` in the catalog; identity-safe):
  `dilate_erode`/`halftone` (handlers_cops.py — live Cop name is
  `dilateerode`; `halftone` absent in every category),
  `oceanflat`/`popnet`/`rigidsolver`/`vellumcloth`/`vellumcollider`/
  `vellumhair` (planner.py + fx_recipes.py — live names: `oceansource`,
  none, `rigidbodysolver`, `vellumconstraints` presets), and
  `modifypointinstancers` in `tests/test_setdressing_recipe.py`'s verified
  list (live Lop name is `modifypointinstances`, no "r"). Fixing the
  emitters is follow-up work outside this task's file set.
