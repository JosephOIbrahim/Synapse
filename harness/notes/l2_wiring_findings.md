# CTO-RELAY-01 · LEG 2 — Solaris wiring findings

**Build** Houdini 22.0.368 / Python 3.13.10 (hython, live). Live SYNAPSE WS bridge is DOWN
(L1-verified); every live result below comes from `hython.exe`, not the bridge.
**Branch** `feat/cto-relay-01`. **Gate** ALLOW / MODE B, verifiers-only — no Solaris source
was repaired. Every defect below is deposited for the ruling block.

---

## 1 · Seam-gate re-run

`python scripts/run_live_probes.py` against HEAD `a66048d`, on 22.0.368.

```
RESULT: 6/6 passed
negative control MISSING: probe_phase3_layout
VERDICT: PASS
```

**GO.** All six probes pass: `probe_b1_render_tier_ordering`, `probe_b4_build_idempotency`,
`probe_loop_composed`, `probe_m10_section_boxes`, `probe_phase3_layout`,
`probe_pr47_fast_follows`.

Note the count: the runner grades **6 probes**, not 13 attacks. The "13/13" figure in the
dispatch is an assertion-level tally from the PR #48 write-up, not a runner-reported number;
`run_live_probes.py` has no notion of 13. Recorded so the next census does not hunt a
discrepancy that is only a units mismatch.

## 2 · Residual disposition

| # | Residual | Disposition | Reason |
|---|---|---|---|
| R1 | `probe_phase3_layout` has no paired negative control (runner-reported) | **PROMOTED to debt** | Not cosmetic. Without a negative control the probe cannot show the layout fix is *real* rather than vacuously true, and `run_live_probes.py --strict-companions` fails the gate today. It is a gate-integrity gap. |
| R2 | `harness/notes/mile2_loop_closure.md` Part 3: stale `forge_mile2.md:32` instruction text; merged `feat/graph-synth-mile2` branch undeleted | **CLOSED** | Genuinely cosmetic and load-bearing for nothing. The prompt line has no code importer and is explicitly retained as a record of the pivot; the branch is a local-only nit. Neither affects any gate. |

---

## 3 · Findings

Severity: **CRITICAL** = tool cannot work at all · **HIGH** = silently wrong output ·
**MED** = correctness gap with a workaround · **LOW** = hygiene.

### F1 · All five Solaris tools are unreachable from the live MCP registry — **CRITICAL**
- **Claim** RELAY-SOLARIS Phase 3 delivered five Solaris tools.
- **Truth** REFUTED-LIVE. None of `synapse_solaris_{component_builder,scene_template,
  import_megascans,create_variants,set_purpose}` appears in
  `python/synapse/mcp/_tool_registry.py`. They live in `synapse/mcp/tools/solaris/`, a tree
  **outside** the installable `python/synapse/` package. That tree's own conftest concedes it:
  *"tools that live outside the installable python/synapse/ package tree."*
- **Anchor** `python/synapse/mcp/_tool_registry.py` (no match); `synapse/mcp/tools/solaris/__init__.py`;
  `synapse/tests/solaris/conftest.py:5-7`.
- **Consequence** No `/mcp` or `/synapse` path can invoke any of them. They are dead code.

### F2 · `tool_audit` is not a tool — **LOW (scope correction)**
- **Claim** Six Solaris tools, of which five need verifiers.
- **Truth** REFUTED. `tool_audit` has no implementation module, no `validate/plan/execute`,
  and is absent from the package `__all__`. What exists is `schema_tool_audit.py`, a Phase-2
  design dict mapping 8 NodeFlow patterns to intended tools. Five tools + one design document.
- **Anchor** `synapse/mcp/tools/solaris/schema_tool_audit.py`; `.../__init__.py:21-33`.

### F3 · `import_megascans` orphans the material reference LOP — **HIGH**
- **Truth** REFUTED-STATIC. `mtl_ref_<asset>` (a `reference` LOP) is created and its
  `filepath1`/`primpath`/`destpath` parms are set, then never wired. `componentmaterial` gets
  only `setInput(0, geo_node)`; input 1 — the material input — is left open. Imported Megascans
  materials never reach the component. The graph still *composes*, which is exactly why an
  existence-only check misses it.
- **Anchor** `synapse/mcp/tools/solaris/import_megascans.py:240-255`.

### F4 · `create_variants` material branch emits unwired `componentmaterial` nodes — **HIGH**
- **Truth** REFUTED-STATIC. Duplicated variant materials never receive `setInput`.
  `hou.copyNodesTo` does not carry input connections to nodes outside the copied set, so each
  variant lands with 0 wired inputs against a catalogued `min_inputs=1` — live, the
  "Not enough sources specified." node error.
- **Anchor** `synapse/mcp/tools/solaris/create_variants.py:152-169`.

### F5 · `create_variants` geometry branch dead-ends the variant set — **HIGH**
- **Truth** REFUTED-LIVE. `componentgeometryvariants` collects the variants but is never wired
  downstream into the component's material/output chain. Live on 22.0.368 the component
  presents **two** terminal LOPs: `.../component/geo_variants` and `.../explore_component`.
  The variant set never reaches the rendered terminal.
- **Anchor** `synapse/mcp/tools/solaris/create_variants.py:186-195`.

### F6 · Silent false-success via bare `except Exception: pass` — **MED**
- **Truth** Both the `componentgeometryvariants` creation and the `explorevariants` creation
  are wrapped in bare `except Exception: pass`, after which `execute()` returns
  `status="created"` regardless. A total failure is indistinguishable from success.
- **Anchor** `synapse/mcp/tools/solaris/create_variants.py:193-203`.

### F7 · `set_purpose` is a no-op that reports success — **HIGH**
- **Truth** REFUTED-LIVE. The tool sets `geo_node.parm("purpose")`. On 22.0.368
  `componentgeometry` exposes **no** `purpose` parm — a live `dir`/`parms()` sweep finds no
  parm whose name contains "purpose" at all. Execution therefore always takes the fallback
  branch, which returns `status="set"` with only an advisory `note`. Caller cannot distinguish
  applied from not-applied. The tool's own comment concedes the mechanism is unverified
  ("may need live Houdini verification").
- **Anchor** `synapse/mcp/tools/solaris/set_purpose.py:129-156`; live probe
  `harness/notes/l2_live_verify.py` → `set_purpose.purpose_parm` FAIL.

### F8 · Inconsistent parent-parameter name across the tool family — **LOW**
- **Truth** `scene_template.execute` reads `params["parent"]`; `import_megascans` and
  `component_builder` read `params["parent_path"]`. A caller using one convention silently
  builds into the default `/stage` instead of the requested network — no error is raised.
- **Anchor** `scene_template.py:167` vs `import_megascans.py:~150`.

### F9 · `import_megascans` raises `hou.PermissionError` unconditionally — **CRITICAL**
- **Truth** REFUTED-LIVE. The tool calls `geo_node.createNode("usdimport", ...)` where
  `geo_node` is a `componentgeometry` — a **locked HDA**. Live traceback:
  `hou.PermissionError: Cannot create a node inside a locked asset`. The tool cannot complete
  on 22.0.368 under any parameters. The correct target is the interior `sopnet/geo` subnet,
  which live-probes as writable (`createNode inside sopnet/geo: OK`).
- **Anchor** `synapse/mcp/tools/solaris/import_megascans.py:172`; reproducer
  `harness/notes/l2_mega_trace.py`.
- **Aggravator** the failure occurs inside `hou.undos.group`, after the subnet and
  componentgeometry are already created — partial state.

### F10 · `componentbuilder` is absent from the live 22.0.368 LOP catalogue — **MED**
- **Truth** REFUTED-LIVE. `component_builder.py:227` attempts
  `parent.createNode("componentbuilder", ...)`. That type is not among the 218 live-probed LOP
  types. The tool does have a `subnet` fallback (`:244`), so this degrades rather than breaks —
  but the native path is a phantom and the try/except hides it.
- **Anchor** `harness/notes/h22_lop_catalog_live_22.0.368.json` (no `componentbuilder`);
  `synapse/mcp/tools/solaris/component_builder.py:227,244`.

### F11 · The orphan tree's own tests are never collected — **MED**
- **Truth** `pyproject.toml` sets `testpaths = ["tests"]`. The five test files under
  `synapse/tests/solaris/` are outside that root and have **never** run in the gate suite.
  They also drive `MagicMock` `hou`, so even if collected they assert nothing about real
  Houdini behaviour — which is how F7 and F9 survived.
- **Anchor** `pyproject.toml:102`; `synapse/tests/solaris/conftest.py`.

---

## 4 · Live verdicts (hython 22.0.368)

| Verifier | Tier | Verdict | Evidence |
|---|---|---|---|
| `scene_template` | static + live | **PASS** | terminal `render_settings` composes **14 prims**, no node errors |
| `set_purpose` (host chain) | static + live | **PASS** | terminal `l2_out` composes **4 prims**, no node errors |
| `set_purpose` (purpose parm) | live | **FAIL** | no `purpose` parm on `componentgeometry` → F7 |
| `import_megascans` | static | **FAIL** | `dead_end[mtl_ref_asset]` → F3 |
| `import_megascans` | live | **ERROR** | `hou.PermissionError` at `:172` → F9 |
| `create_variants` (geometry) | static + live | **FAIL** | 2 terminal LOPs, `dead_end[geo_variants]` → F5 |
| `create_variants` (material) | static | **FAIL** | `mat_red`/`mat_blue` `min_inputs` 0 < 1 → F4 |
| `create_variants` (explore) | static | **PASS** | `explorevariants` correctly fed by the component |
| `tool_audit` (structure) | static | **PASS** | document shape intact |
| `tool_audit` (registration) | static | **FAIL** | 5/5 claimed tools unregistered → F1 |

Runners: `harness/notes/l2_live_verify.py` (full live tier),
`harness/notes/l2_mega_trace.py` (F9 reproducer).

---

## 5 · FOR_RULING

1. **F1 + F11 together decide whether this tool family is alive.** Five unregistered tools with
   uncollected mock-only tests is not a wiring bug, it is an undelivered feature. Ruling needed:
   register and repair, or quarantine the tree and delete the claim from the Phase-2 audit.
   Building verifiers for permanently-dead code is waste; this leg's verifiers are the evidence
   that forces the choice, not a vote for either branch.
2. **F9 is a hard blocker on `import_megascans`** and must be ruled before any registration:
   the tool cannot run once, ever, on 22.0.368.
3. **F7 raises a doctrine question beyond this tool** — a tool that returns `status="set"` when
   it set nothing violates the fidelity-or-stop rule in CLAUDE.md §11.6. Ruling on whether
   "advisory note on a success status" is ever acceptable would bind more than Solaris.
4. **R1 (probe_phase3_layout negative control)** — promoted to debt; needs an owner before
   `--strict-companions` can become the default gate.
5. **F8** is a one-line convergence but touches three tool signatures; ruling on which name wins.
