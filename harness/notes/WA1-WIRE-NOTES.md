# WA1-WIRE — C2 wire-typing matrix + @/$ resolution table (notes)

Wave: `wavea1` · Leg: `WA1-WIRE` · Build probed: **H22.0.400** (Python 3.13.10) ·
Blueprint anchor: `docs/APEX_H22_BLUEPRINT.md` §5 C2 · Contract: `.synapse/contracts/apex-wire-matrix.yaml`.

## What this leg built

Two new autoresearch probe kinds (in `harness/autoresearch/probes.py`), a mission that
wires them (`harness/autoresearch/missions/apex_wire.json`), runner + schema dispatch,
and tests. One artifact per build: `apex_wire_matrix_<build>.json`.

- **`apex_wire_matrix`** — for every ordered `(out,in)` port-type pair, script-build a
  two-node APEX graph and record `connect | coerce | reject(+exception) | UNKNOWN`.
- **`apex_token_resolution`** — one row per `(token, bind context)`: what `@x`/`$x`
  resolves to in each context. A table, not an explanation.

## Type-set source (crucible criterion)

The crucible required the type set to come from **TRUTH's artifact OR a declared fixture** —
"a matrix over a typed-from-memory set is the phantom class in matrix clothing."

**Decision: a DECLARED FIXTURE** (21 types, in the mission JSON). Reason, with receipt:

> TRUTH's `apex_port_signature` artifact reports **null port types** on this build. Its
> `_ports()` reads `_safe_str(p.name)` / `_safe_str(p.type_name)`, and `_safe_str(fn)`
> does `str(fn())` — it *calls* its argument. `p.name`/`p.type_name` are string
> **properties**, so `fn()` raises and the value is recorded `null`. Every port in
> `apex_truth_22.0.400.json` carries correct **arity** but `"type": null`
> (e.g. `Add<Matrix4>`, lines ~3232-3266). So the type set **cannot** be harvested from
> that artifact as-is.

Every fixture entry is nonetheless **catalog-proven, not memory**: each has a live
`Value<T>` in `apex.callbackRegistry().callbackDefinitions()` (2286 names, TRUTH artifact
`apex_basic_20260817_122650/apex_truth_22.0.400.json`). The probe re-checks each type's
`Value<T>` existence live and records `type_present` — an absent constructor renders that
row/column `UNKNOWN`, never a silent omit. All 21 were present → 0 UNKNOWN cells.

The wire probe reads port types from the **graph** via `g.portTypeName(port_id)` (the
correct surface), not from `getSignature` — sidestepping the null-type bug entirely.

## Grounded APEX wiring API (live dir()/doc introspection on 22.0.400 — no memory)

```
apex.Graph()                          -> in-memory graph object (NO scene mutation)
g.addNode(name, callback) -> int      (arg0=name, arg1=callback)  [confirmed]
g.getOutputPorts(nid)/getInputPorts(nid) -> list[int]
g.portTypeName(pid) -> str            (the real port type string)
g.addWire(src_pid, dst_pid) -> int    STRUCTURAL: never type-checks
g.resolveTypes() -> bool ; g.errors() -> list[str]   the TYPE-verdict surface
```

The wire method existed **nowhere in the repo** before this leg (the blueprint's
"addNode + wire, both champion-confirmed" was aspirational; only `apex.Graph`/`addNode`
were presence-confirmed by TRUTH). It was resolved live here.

## Finding: APEX wire typing is EXACT-match; there is NO implicit wire coercion

`addWire` is purely structural — it always succeeds (returns 0, wire physically added).
Type checking happens at `resolveTypes()`. Observed verdict rule on 22.0.400:

- exact type match → `resolveTypes()==True`, `errors()==[]` → **connect**
- ANY mismatch — *even `Int -> Float`* → `resolveTypes()==False` +
  `"Mismatched type: /s:value:Int -> /d:parm:Float"` → **reject**

Full 21×21 product = **441 cells: 21 connect (the diagonal) + 420 reject**, 0 coerce.
**Coercion in APEX is explicit** via `Convert<A,B>` callbacks (present in the catalog),
not via a direct port-to-port wire. The probe still derives `coerce` from the runtime
(it would fire if a cross-type wire ever resolved clean) — the zero is the honest result.

Idempotence: in-artifact `repeat=2` sample (81 pairs) identical; **cross-run** matrix
hash identical across two independent hython sessions
(`8bde4bb5df92a7c95b88b1e2563211c2593ff1bbf3f81f071bb47cf37402ea94`).

## @/$ resolution table — findings per context

| context | `$` forms | `@` forms | note |
|---|---|---|---|
| `hscript_global` (`hou.text.expandString`) | **expand** (`$HIP`→path, `$OS`→"Director", `$E`/`$PI`→constants) | **literal** | session-global |
| `scene_node_parm` (scratch `font.text` eval) | **expand**, node-context (`$OS`→"font1" = node name) | **literal** | genuine node-context; differs from global for `$OS` |
| `apex_graph_parm` (`setNodeParm`/`getNodeParms`) | **literal** | **literal** | APEX parms are typed data — no hscript expansion |
| `apex_invoke_binding` (`apex::invokegraph` `@attr`) | **UNKNOWN** | **UNKNOWN** | resolving `@attr` needs a cooked geometry+graph invoke; not measurable headless. Structural binding parms recorded: `inputbindings`, `outputbindings`, `dictbindings`, `bindoutputgeo`, … |

68 rows (17 tokens × 4 contexts), 0 missing, every UNKNOWN carries a reason.
Session-dependent rows (`$HIP`/`$OS`/`$F`/…) are flagged — the table is a per-run snapshot.

## Merge-awareness (shared seam this wave)

`probes.py`, `runner.py`, `mission_schema.py` are the WA1-TRUTH-released shared seam
(bus-serialized; TRUTH released before this leg claimed). Edits here are **additive**:
new `apex_wire_matrix` / `apex_token_resolution` kinds + dispatch branches, and the
`artifact_prefix` mechanism replicated **verbatim** from TRUTH so those specific lines
auto-merge. My helper functions are `_wm_`/`_tok_`-prefixed to avoid colliding with
TRUTH's `_apex_registry`/`_apex_log_capture`. VALID_KINDS / dispatch-chain additions
will need a trivial human union at merge.
